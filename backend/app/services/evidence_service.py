import logging
import tempfile
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.types import AuditEventType, DocumentType, EvidenceSourceType
from app.errors import ConflictError, NotFoundError
from app.models.evidence import Evidence
from app.repositories.case_repository import CaseRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.security.file_validation import FileValidator
from app.services.audit_service import AuditService
from app.storage.base import ObjectStorage
from app.utils.hashing import sha256_file

logger = logging.getLogger(__name__)

DOCUMENT_TYPE_BY_EXTENSION = {
    ".eml": DocumentType.EMAIL,
    ".pdf": DocumentType.PDF,
    ".xls": DocumentType.EXCEL,
    ".xlsx": DocumentType.EXCEL,
    ".csv": DocumentType.CSV,
    ".doc": DocumentType.WORD,
    ".docx": DocumentType.WORD,
    ".jpg": DocumentType.IMAGE,
    ".jpeg": DocumentType.IMAGE,
    ".png": DocumentType.IMAGE,
    ".txt": DocumentType.TEXT,
}


class EvidenceService:
    def __init__(
        self,
        session: AsyncSession,
        case_repository: CaseRepository,
        evidence_repository: EvidenceRepository,
        audit_service: AuditService,
        storage: ObjectStorage,
        validator: FileValidator,
    ) -> None:
        self.session = session
        self.case_repository = case_repository
        self.evidence_repository = evidence_repository
        self.audit_service = audit_service
        self.storage = storage
        self.validator = validator

    async def _require_case(self, case_id: uuid.UUID) -> None:
        if await self.case_repository.get(case_id) is None:
            raise NotFoundError("CASE_NOT_FOUND", "Case not found")

    async def upload_evidence(
        self,
        case_id: uuid.UUID,
        upload: UploadFile,
        source_type: EvidenceSourceType,
        created_by: str | None = None,
        parent_evidence_id: uuid.UUID | None = None,
    ) -> Evidence:
        await self._require_case(case_id)
        cleaned_name, extension = self.validator.validate_metadata(
            upload.filename, upload.content_type
        )
        evidence_id = uuid.uuid4()
        await self.audit_service.append(
            case_id=case_id,
            event_type=AuditEventType.EVIDENCE_UPLOAD_STARTED,
            resource_type="evidence",
            resource_id=str(evidence_id),
            operation="upload",
            actor_id=created_by,
            metadata={"filename": cleaned_name, "source_type": source_type.value},
        )
        await self.session.commit()

        temp_path: Path | None = None
        object_key: str | None = None
        stored = False
        try:
            with tempfile.NamedTemporaryFile(prefix="whale-evidence-", delete=False) as target:
                temp_path = Path(target.name)
                size = 0
                while chunk := await upload.read(1024 * 1024):
                    size += len(chunk)
                    if size > self.validator.max_size_bytes:
                        self.validator.validate_size(size)
                    target.write(chunk)
            self.validator.validate_size(size)
            digest = sha256_file(temp_path)
            if await self.evidence_repository.get_by_hash(case_id, digest):
                raise ConflictError("DUPLICATE_EVIDENCE", "Duplicate evidence in this case")
            await self.audit_service.append(
                case_id=case_id,
                event_type=AuditEventType.EVIDENCE_HASHED,
                resource_type="evidence",
                resource_id=str(evidence_id),
                operation="hash",
                output_hash=digest,
                actor_id=created_by,
            )
            await self.session.commit()

            object_key = f"cases/{case_id}/evidence/{evidence_id}/{cleaned_name}"
            await self.storage.put(
                object_key, temp_path, upload.content_type or "application/octet-stream"
            )
            stored = True
            evidence = Evidence(
                id=evidence_id,
                case_id=case_id,
                original_filename=upload.filename or cleaned_name,
                stored_filename=cleaned_name,
                object_key=object_key,
                mime_type=upload.content_type or "application/octet-stream",
                file_extension=extension,
                file_size=size,
                sha256=digest,
                source_type=source_type,
                document_type=DOCUMENT_TYPE_BY_EXTENSION.get(extension, DocumentType.UNKNOWN),
                parent_evidence_id=parent_evidence_id,
                metadata_json={},
                created_by=created_by,
            )
            evidence = await self.evidence_repository.create(evidence)
            await self.audit_service.append(
                case_id=case_id,
                event_type=AuditEventType.EVIDENCE_STORED,
                resource_type="evidence",
                resource_id=str(evidence_id),
                operation="store",
                actor_id=created_by,
                metadata={"object_key": object_key},
            )
            await self.audit_service.append(
                case_id=case_id,
                event_type=AuditEventType.EVIDENCE_CREATED,
                resource_type="evidence",
                resource_id=str(evidence_id),
                operation="create",
                output_hash=digest,
                actor_id=created_by,
            )
            await self.session.commit()
            return evidence
        except IntegrityError as exc:
            await self.session.rollback()
            await self._compensate_storage(object_key, stored)
            await self._record_failure(case_id, evidence_id, created_by, "duplicate evidence")
            raise ConflictError("DUPLICATE_EVIDENCE", "Duplicate evidence in this case") from exc
        except Exception as exc:
            await self.session.rollback()
            await self._compensate_storage(object_key, stored)
            await self._record_failure(case_id, evidence_id, created_by, type(exc).__name__)
            raise
        finally:
            await upload.close()
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

    async def _compensate_storage(self, object_key: str | None, stored: bool) -> None:
        if not stored or object_key is None:
            return
        try:
            await self.storage.delete(object_key)
        except Exception:
            # A future orphan-cleanup job can reconcile this explicit compensation failure.
            logger.exception(
                "evidence_storage_compensation_failed", extra={"object_key": object_key}
            )

    async def _record_failure(
        self, case_id: uuid.UUID, evidence_id: uuid.UUID, actor_id: str | None, reason: str
    ) -> None:
        try:
            await self.audit_service.append(
                case_id=case_id,
                event_type=AuditEventType.EVIDENCE_UPLOAD_FAILED,
                resource_type="evidence",
                resource_id=str(evidence_id),
                operation="upload",
                actor_id=actor_id,
                metadata={"reason": reason},
            )
            await self.session.commit()
        except SQLAlchemyError:
            await self.session.rollback()
            logger.exception("evidence_upload_failure_audit_failed")

    async def get_evidence(self, case_id: uuid.UUID, evidence_id: uuid.UUID) -> Evidence:
        await self._require_case(case_id)
        evidence = await self.evidence_repository.get(case_id, evidence_id)
        if evidence is None:
            raise NotFoundError("EVIDENCE_NOT_FOUND", "Evidence not found")
        return evidence

    async def list_evidence(self, case_id: uuid.UUID) -> list[Evidence]:
        await self._require_case(case_id)
        return await self.evidence_repository.list(case_id)

    async def delete_evidence(self, case_id: uuid.UUID, evidence_id: uuid.UUID) -> None:
        evidence = await self.get_evidence(case_id, evidence_id)
        await self.storage.delete(evidence.object_key)
        await self.evidence_repository.delete(evidence)
        await self.audit_service.append(
            case_id=case_id,
            event_type=AuditEventType.EVIDENCE_DELETED,
            resource_type="evidence",
            resource_id=str(evidence_id),
            operation="delete",
            input_hash=evidence.sha256,
        )
        await self.session.commit()

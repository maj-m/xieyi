"""证据标准化协调层：领取解析任务、校验证据完整性、调用解析器并持久化正文与附件血缘。"""

import hashlib
import json
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.types import (
    DocumentType,
    EvidenceProcessingStatus,
    EvidenceSourceType,
    NormalizedDocumentStatus,
)
from app.errors import ConflictError, NotFoundError
from app.models.evidence import Evidence
from app.models.evidence_processing import (
    EvidenceDerivative,
    EvidenceProcessingJob,
    NormalizedDocument,
)
from app.parsers.base import ParseResult
from app.parsers.registry import ParserRegistry
from app.repositories.case_repository import CaseRepository
from app.repositories.evidence_processing_repository import EvidenceProcessingRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.security.file_validation import BLOCKED_EXTENSIONS
from app.services.evidence_service import DOCUMENT_TYPE_BY_EXTENSION
from app.storage.base import ObjectStorage
from app.utils.hashing import sha256_file

SCHEMA_VERSION = "1.0"


class EvidenceProcessingService:
    def __init__(
        self,
        session: AsyncSession,
        cases: CaseRepository,
        evidence: EvidenceRepository,
        processing: EvidenceProcessingRepository,
        storage: ObjectStorage,
        parsers: ParserRegistry,
    ) -> None:
        self.session = session
        self.cases = cases
        self.evidence = evidence
        self.processing = processing
        self.storage = storage
        self.parsers = parsers

    async def enqueue(
        self, case_id: uuid.UUID, evidence_id: uuid.UUID, key: str, max_attempts: int
    ) -> EvidenceProcessingJob:
        await self._require_evidence(case_id, evidence_id)
        if existing := await self.processing.get_idempotent(evidence_id, key):
            return existing
        job = EvidenceProcessingJob(
            case_id=case_id,
            evidence_id=evidence_id,
            status=EvidenceProcessingStatus.QUEUED,
            idempotency_key=key,
            max_attempts=max_attempts,
        )
        await self.processing.create_job(job)
        await self.session.commit()
        return job

    async def list_jobs(
        self, case_id: uuid.UUID, evidence_id: uuid.UUID | None = None
    ) -> list[EvidenceProcessingJob]:
        if await self.cases.get(case_id) is None:
            raise NotFoundError("CASE_NOT_FOUND", "Case not found")
        return await self.processing.list_jobs(case_id, evidence_id)

    async def get_document(self, case_id: uuid.UUID, evidence_id: uuid.UUID) -> NormalizedDocument:
        await self._require_evidence(case_id, evidence_id)
        document = await self.processing.get_document(evidence_id)
        if document is None:
            raise NotFoundError("NORMALIZED_DOCUMENT_NOT_FOUND", "Normalized document not found")
        return document

    async def claim_and_process(self, worker_id: str, lease_seconds: int = 120) -> bool:
        job = await self.processing.claim_next(worker_id, lease_seconds)
        if job is None:
            await self.session.rollback()
            return False
        job_id = job.id
        await self.session.commit()
        try:
            await self._process(job_id, worker_id)
        except Exception as exc:
            await self.session.rollback()
            await self._record_failure(job_id, worker_id, exc)
        return True

    async def _process(self, job_id: uuid.UUID, worker_id: str) -> None:
        job = await self.processing.get_job(job_id)
        if (
            job is None
            or job.lease_owner != worker_id
            or job.status != EvidenceProcessingStatus.PROCESSING
        ):
            raise ConflictError(
                "PROCESSING_LEASE_LOST", "Evidence processing lease is no longer owned"
            )
        evidence = await self.evidence.get(job.case_id, job.evidence_id)
        if evidence is None:
            raise NotFoundError("EVIDENCE_NOT_FOUND", "Evidence not found")
        parser = self.parsers.find(evidence)
        if parser is None:
            status = (
                EvidenceProcessingStatus.OCR_REQUIRED
                if evidence.document_type == DocumentType.IMAGE
                else EvidenceProcessingStatus.UNSUPPORTED
            )
            document_status = (
                NormalizedDocumentStatus.OCR_REQUIRED
                if status == EvidenceProcessingStatus.OCR_REQUIRED
                else NormalizedDocumentStatus.UNSUPPORTED
            )
            job.status = status
            job.completed_at = datetime.now(UTC)
            await self.processing.add_document(
                NormalizedDocument(
                    case_id=job.case_id,
                    evidence_id=job.evidence_id,
                    job_id=job.id,
                    status=document_status,
                    schema_version=SCHEMA_VERSION,
                    parser_name="unavailable",
                    parser_version="0",
                    title=evidence.original_filename,
                    metadata_json={"document_type": evidence.document_type.value},
                )
            )
            await self.session.commit()
            return

        job.parser_name = parser.name
        job.parser_version = parser.version
        with tempfile.TemporaryDirectory(prefix="whale-processing-") as directory:
            source = Path(directory) / evidence.stored_filename
            stat = await self.storage.download_to(evidence.object_key, source)
            if stat.size != evidence.file_size or sha256_file(source) != evidence.sha256:
                raise ConflictError(
                    "EVIDENCE_INTEGRITY_FAILED", "Stored evidence integrity check failed"
                )
            result = parser.parse(source, evidence)
            await self._persist_result(job, evidence, result, Path(directory))
        job.status = EvidenceProcessingStatus.COMPLETED
        job.completed_at = datetime.now(UTC)
        job.lease_expires_at = None
        await self.session.commit()

    async def _persist_result(
        self, job: EvidenceProcessingJob, evidence: Evidence, result: ParseResult, temp_dir: Path
    ) -> None:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "source": {
                "evidence_id": str(evidence.id),
                "sha256": evidence.sha256,
                "filename": evidence.original_filename,
            },
            "document": {
                "type": evidence.document_type.value,
                "title": result.title,
                "text": result.text,
                "language": result.language,
            },
            "metadata": result.metadata,
            "attachments": [
                {
                    "filename": item.filename,
                    "content_type": item.content_type,
                    "size": len(item.content),
                }
                for item in result.attachments
            ],
        }
        normalized_path = temp_dir / "normalized.json"
        normalized_path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )
        normalized_key = f"cases/{job.case_id}/normalized/{evidence.id}/{job.id}.json"
        await self.storage.put(normalized_key, normalized_path, "application/json")
        await self.processing.add_document(
            NormalizedDocument(
                case_id=job.case_id,
                evidence_id=evidence.id,
                job_id=job.id,
                status=NormalizedDocumentStatus.READY,
                schema_version=SCHEMA_VERSION,
                parser_name=job.parser_name or "unknown",
                parser_version=job.parser_version or "0",
                title=result.title,
                text_preview=result.text[:2000],
                language=result.language,
                content_object_key=normalized_key,
                content_sha256=sha256_file(normalized_path),
                metadata_json=result.metadata,
            )
        )
        for index, attachment in enumerate(result.attachments, start=1):
            await self._persist_attachment(
                job,
                evidence,
                attachment.filename,
                attachment.content_type,
                attachment.content,
                attachment.metadata,
                index,
                temp_dir,
            )

    async def _persist_attachment(
        self,
        job: EvidenceProcessingJob,
        parent: Evidence,
        filename: str,
        mime_type: str,
        content: bytes,
        metadata: dict[str, object],
        index: int,
        temp_dir: Path,
    ) -> None:
        digest = hashlib.sha256(content).hexdigest()
        existing = await self.evidence.get_by_hash(parent.case_id, digest)
        object_key: str
        child_id: uuid.UUID
        if existing is not None:
            child_id = existing.id
            object_key = existing.object_key
        else:
            child_id = uuid.uuid4()
            attachment_path = temp_dir / f"attachment-{index}"
            attachment_path.write_bytes(content)
            object_key = f"cases/{parent.case_id}/evidence/{child_id}/{filename}"
            await self.storage.put(object_key, attachment_path, mime_type)
            extension = Path(filename).suffix.lower()
            child = Evidence(
                id=child_id,
                case_id=parent.case_id,
                original_filename=filename,
                stored_filename=filename,
                object_key=object_key,
                mime_type=mime_type,
                file_extension=extension,
                file_size=len(content),
                sha256=digest,
                source_type=EvidenceSourceType.EMAIL,
                document_type=DOCUMENT_TYPE_BY_EXTENSION.get(extension, DocumentType.UNKNOWN),
                parent_evidence_id=parent.id,
                metadata_json={
                    "extracted_from": str(parent.id),
                    "quarantined": extension in BLOCKED_EXTENSIONS,
                },
                created_by="evidence-worker",
            )
            await self.evidence.create(child)
        await self.processing.add_derivative(
            EvidenceDerivative(
                case_id=parent.case_id,
                source_evidence_id=parent.id,
                child_evidence_id=child_id,
                job_id=job.id,
                derivative_type="EMAIL_ATTACHMENT",
                filename=filename,
                object_key=object_key,
                mime_type=mime_type,
                file_size=len(content),
                sha256=digest,
                metadata_json=metadata,
            )
        )
        if await self.processing.get_latest_job(child_id) is None:
            await self.processing.create_job(
                EvidenceProcessingJob(
                    case_id=parent.case_id,
                    evidence_id=child_id,
                    status=EvidenceProcessingStatus.QUEUED,
                    idempotency_key=f"derived:{job.id}",
                    max_attempts=3,
                )
            )

    async def _record_failure(self, job_id: uuid.UUID, worker_id: str, exc: Exception) -> None:
        job = await self.processing.get_job(job_id)
        if job is None or job.lease_owner != worker_id:
            return
        job.error_code = getattr(exc, "code", type(exc).__name__)
        job.error_message = str(exc)[:2000]
        job.lease_owner = None
        job.lease_expires_at = None
        if job.attempt_count < job.max_attempts:
            job.status = EvidenceProcessingStatus.QUEUED
            job.available_at = datetime.now(UTC) + timedelta(seconds=min(30, 2**job.attempt_count))
        else:
            job.status = EvidenceProcessingStatus.FAILED
            job.completed_at = datetime.now(UTC)
        await self.session.commit()

    async def _require_evidence(self, case_id: uuid.UUID, evidence_id: uuid.UUID) -> Evidence:
        evidence = await self.evidence.get(case_id, evidence_id)
        if evidence is None:
            raise NotFoundError("EVIDENCE_NOT_FOUND", "Evidence not found")
        return evidence

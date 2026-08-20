from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.session import get_session
from app.repositories.audit_repository import AuditRepository
from app.repositories.case_repository import CaseRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.security.file_validation import FileValidator
from app.services.audit_service import AuditService
from app.services.case_service import CaseService
from app.services.evidence_service import EvidenceService
from app.storage.base import ObjectStorage
from app.storage.minio_storage import MinIOStorage

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@lru_cache
def get_storage() -> MinIOStorage:
    settings = get_settings()
    return MinIOStorage(
        settings.minio_endpoint,
        settings.minio_access_key,
        settings.minio_secret_key,
        settings.minio_bucket,
        settings.minio_secure,
    )


def get_audit_service(session: SessionDep) -> AuditService:
    return AuditService(
        AuditRepository(session), chain_enabled=get_settings().audit_hash_chain_enabled
    )


def get_case_service(
    session: SessionDep, audit_service: Annotated[AuditService, Depends(get_audit_service)]
) -> CaseService:
    return CaseService(session, CaseRepository(session), audit_service)


def get_evidence_service(
    session: SessionDep,
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
    storage: Annotated[ObjectStorage, Depends(get_storage)],
) -> EvidenceService:
    settings: Settings = get_settings()
    validator = FileValidator(
        settings.allowed_file_extensions, settings.max_upload_size_mb * 1024 * 1024
    )
    return EvidenceService(
        session,
        CaseRepository(session),
        EvidenceRepository(session),
        audit_service,
        storage,
        validator,
    )


AuditServiceDep = Annotated[AuditService, Depends(get_audit_service)]
CaseServiceDep = Annotated[CaseService, Depends(get_case_service)]
EvidenceServiceDep = Annotated[EvidenceService, Depends(get_evidence_service)]
StorageDep = Annotated[ObjectStorage, Depends(get_storage)]

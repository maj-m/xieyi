import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.types import EvidenceProcessingStatus, NormalizedDocumentStatus


class ProcessingJobCreate(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=128)
    max_attempts: int = Field(default=3, ge=1, le=10)


class ProcessingJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    evidence_id: uuid.UUID
    status: EvidenceProcessingStatus
    parser_name: str | None
    parser_version: str | None
    attempt_count: int
    max_attempts: int
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class NormalizedDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    evidence_id: uuid.UUID
    job_id: uuid.UUID
    status: NormalizedDocumentStatus
    schema_version: str
    parser_name: str
    parser_version: str
    title: str | None
    text_preview: str | None
    language: str | None
    content_object_key: str | None
    content_sha256: str | None
    metadata_json: dict[str, object]
    created_at: datetime

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.types import DocumentType, EvidenceSourceType


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    original_filename: str
    stored_filename: str
    object_key: str
    mime_type: str
    file_extension: str
    file_size: int
    sha256: str
    source_type: EvidenceSourceType
    document_type: DocumentType
    parent_evidence_id: uuid.UUID | None
    metadata_json: dict[str, object]
    created_by: str | None
    created_at: datetime

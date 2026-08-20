import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.types import AuditEventType


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID | None
    event_type: AuditEventType
    actor_id: str | None
    resource_type: str
    resource_id: str | None
    operation: str
    input_hash: str | None
    output_hash: str | None
    metadata_json: dict[str, object]
    previous_hash: str | None
    event_hash: str
    created_at: datetime


class AuditVerifyResponse(BaseModel):
    valid: bool
    event_count: int
    broken_event_id: uuid.UUID | None

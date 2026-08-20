import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.types import CaseStatus


class CaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    created_by: str | None = Field(default=None, max_length=128)


class CaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: CaseStatus | None = None


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_no: str
    name: str
    description: str | None
    status: CaseStatus
    created_by: str | None
    created_at: datetime
    updated_at: datetime

import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.graph.state import WorkflowStatus


class WorkflowStart(BaseModel):
    analysis_scope: str = Field(default="case_overview", min_length=1, max_length=128)


class WorkflowResume(BaseModel):
    approved: bool
    comment: str | None = Field(default=None, max_length=1000)


class WorkflowStateResponse(BaseModel):
    case_name: str
    evidence_count: int
    analysis_scope: str
    summary: str
    review_approved: bool | None
    review_comment: str | None
    result: str | None


class WorkflowResponse(BaseModel):
    thread_id: uuid.UUID
    case_id: uuid.UUID
    status: WorkflowStatus
    next_nodes: list[str]
    interrupt: dict[str, object] | None
    state: WorkflowStateResponse


class WorkflowHealthResponse(BaseModel):
    status: Literal["ready"]

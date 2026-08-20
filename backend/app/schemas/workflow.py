import uuid
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.graph.state import ReviewAction, ReviewRecord, WorkflowStatus


class WorkflowStart(BaseModel):
    analysis_scope: str = Field(default="case_overview", min_length=1, max_length=128)


class WorkflowResume(BaseModel):
    decision: ReviewAction | None = None
    approved: bool | None = None
    comment: str | None = Field(default=None, max_length=1000)
    reviewer: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def validate_decision(self) -> "WorkflowResume":
        if self.decision is None and self.approved is None:
            raise ValueError("Either decision or approved must be provided")
        return self

    @property
    def resolved_decision(self) -> ReviewAction:
        if self.decision is not None:
            return self.decision
        return "APPROVE" if self.approved else "CANCEL"


class WorkflowStateResponse(BaseModel):
    case_name: str
    evidence_count: int
    analysis_scope: str
    summary: str
    review_approved: bool | None
    review_decision: ReviewAction | None
    review_comment: str | None
    reviewer: str | None
    reviewed_at: str | None
    review_round: int
    max_review_rounds: int
    review_history: list[ReviewRecord]
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

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.types import ArtifactStatus, ReviewTaskStatus, WorkflowEventType, WorkflowRunStatus
from app.graph.state import EvidenceDocument, ReviewAction, ReviewRecord, WorkflowStatus


class WorkflowStart(BaseModel):
    analysis_scope: str = Field(default="case_overview", min_length=1, max_length=128)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)
    timeout_seconds: int | None = Field(default=None, ge=30, le=604800)
    max_attempts: int = Field(default=3, ge=1, le=10)


class WorkflowResume(BaseModel):
    decision: ReviewAction | None = None
    approved: bool | None = None
    comment: str | None = Field(default=None, max_length=1000)
    reviewer: str | None = Field(default=None, max_length=128)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)

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
    evidence_documents: list[EvidenceDocument]
    evidence_processing: dict[str, int]
    customs_analysis: dict[str, object] | None
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


class WorkflowRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    thread_id: uuid.UUID
    case_id: uuid.UUID
    analysis_scope: str
    status: WorkflowRunStatus
    current_node: str | None
    review_round: int
    attempt_count: int
    max_attempts: int
    idempotency_key: str | None
    last_error_code: str | None
    last_error_message: str | None
    started_at: datetime
    timeout_at: datetime | None
    completed_at: datetime | None
    heartbeat_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime


class WorkflowEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sequence: int
    event_type: WorkflowEventType
    node_name: str | None
    status: str
    attempt: int
    payload_json: dict[str, object]
    error_code: str | None
    error_message: str | None
    created_at: datetime


class ReviewTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    review_round: int
    interrupt_type: str
    status: ReviewTaskStatus
    decision: str | None
    reviewer: str | None
    comment: str | None
    requested_at: datetime
    decided_at: datetime | None


class AnalysisArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    node_name: str
    artifact_type: str
    version: int
    status: ArtifactStatus
    content_json: dict[str, object]
    object_key: str | None
    sha256: str | None
    prompt_version: str | None
    model_name: str | None
    created_at: datetime


class WorkflowTimelineResponse(BaseModel):
    run: WorkflowRunResponse
    events: list[WorkflowEventResponse]
    reviews: list[ReviewTaskResponse]
    artifacts: list[AnalysisArtifactResponse]


class WorkflowRetry(BaseModel):
    requested_by: str | None = Field(default=None, max_length=128)


class WorkflowCancel(BaseModel):
    requested_by: str | None = Field(default=None, max_length=128)
    reason: str | None = Field(default=None, max_length=1000)


class WorkflowResponse(BaseModel):
    thread_id: uuid.UUID
    case_id: uuid.UUID
    status: WorkflowStatus
    next_nodes: list[str]
    interrupt: dict[str, object] | None
    state: WorkflowStateResponse
    run: WorkflowRunResponse | None = None


class WorkflowHealthResponse(BaseModel):
    status: Literal["ready"]

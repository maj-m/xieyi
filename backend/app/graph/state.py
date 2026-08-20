from typing import Literal, TypedDict

WorkflowStatus = Literal["PREPARING", "WAITING_REVIEW", "COMPLETED", "REJECTED"]


class CaseState(TypedDict):
    case_id: str
    case_name: str
    evidence_count: int
    analysis_scope: str
    status: WorkflowStatus
    summary: str
    review_approved: bool | None
    review_comment: str | None
    result: str | None


class CaseStateUpdate(TypedDict, total=False):
    status: WorkflowStatus
    summary: str
    review_approved: bool
    review_comment: str | None
    result: str


class ReviewDecision(TypedDict):
    approved: bool
    comment: str | None

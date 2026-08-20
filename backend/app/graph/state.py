import operator
from typing import Annotated, Literal, TypedDict

WorkflowStatus = Literal[
    "PREPARING",
    "REANALYZING",
    "WAITING_REVIEW",
    "WAITING_EVIDENCE",
    "COMPLETED",
    "REJECTED",
    "CANCELLED",
]
ReviewAction = Literal["APPROVE", "REANALYZE", "REQUEST_EVIDENCE", "CANCEL", "EVIDENCE_READY"]


class ReviewRecord(TypedDict):
    action: ReviewAction
    comment: str | None
    reviewer: str | None
    reviewed_at: str
    round: int


class CaseState(TypedDict):
    case_id: str
    case_name: str
    evidence_count: int
    analysis_scope: str
    status: WorkflowStatus
    summary: str
    review_approved: bool | None
    review_decision: ReviewAction | None
    review_comment: str | None
    reviewer: str | None
    reviewed_at: str | None
    review_round: int
    max_review_rounds: int
    review_history: Annotated[list[ReviewRecord], operator.add]
    result: str | None


class CaseStateUpdate(TypedDict, total=False):
    status: WorkflowStatus
    summary: str
    evidence_count: int
    review_approved: bool | None
    review_decision: ReviewAction
    review_comment: str | None
    reviewer: str | None
    reviewed_at: str
    review_round: int
    review_history: list[ReviewRecord]
    result: str


class ReviewDecision(TypedDict):
    action: ReviewAction
    comment: str | None
    reviewer: str | None
    reviewed_at: str


class EvidenceReadyDecision(ReviewDecision):
    evidence_count: int

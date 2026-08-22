"""案件研判图状态协议：集中定义节点之间传递、Checkpoint 保存和恢复所需的数据结构。"""

import operator
from typing import Annotated, Literal, NotRequired, TypedDict

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


class EvidenceDocument(TypedDict):
    evidence_id: str
    filename: str
    document_type: str
    title: str
    text: str
    metadata: dict[str, object]


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
    evidence_documents: list[EvidenceDocument]
    evidence_processing: dict[str, int]
    evidence_elements: NotRequired[dict[str, object]]
    risk_assessment: NotRequired[dict[str, object]]
    customs_analysis: dict[str, object] | None
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
    evidence_documents: list[EvidenceDocument]
    evidence_processing: dict[str, int]
    evidence_elements: dict[str, object]
    risk_assessment: dict[str, object]
    customs_analysis: dict[str, object]
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
    evidence_documents: list[EvidenceDocument]
    evidence_processing: dict[str, int]

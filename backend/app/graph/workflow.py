from typing import Literal, cast

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from app.graph.state import (
    CaseState,
    CaseStateUpdate,
    EvidenceReadyDecision,
    ReviewDecision,
)

CaseWorkflowGraph = CompiledStateGraph[CaseState, None, CaseState, CaseState]


def prepare_case(state: CaseState) -> CaseStateUpdate:
    summary = (
        f"案件“{state['case_name']}”已完成第 {state.get('review_round', 1)} 轮最小预研判准备，"
        f"当前纳入 {state['evidence_count']} 份证据，范围为 {state['analysis_scope']}。"
    )
    return {"status": "WAITING_REVIEW", "summary": summary}


def request_human_review(state: CaseState) -> CaseStateUpdate:
    decision_value = interrupt(
        {
            "type": "CASE_ANALYSIS_REVIEW",
            "question": "是否批准该案件预研判结果并完成流程？",
            "case_id": state["case_id"],
            "summary": state["summary"],
            "review_round": state.get("review_round", 1),
            "max_review_rounds": state.get("max_review_rounds", 3),
            "allowed_actions": ["APPROVE", "REANALYZE", "REQUEST_EVIDENCE", "CANCEL"],
        }
    )
    decision = cast(ReviewDecision, decision_value)
    action = decision["action"]
    reviewed_at = decision["reviewed_at"]
    return {
        "review_approved": True if action == "APPROVE" else False if action == "CANCEL" else None,
        "review_decision": action,
        "review_comment": decision.get("comment"),
        "reviewer": decision.get("reviewer"),
        "reviewed_at": reviewed_at,
        "review_history": [
            {
                "action": action,
                "comment": decision.get("comment"),
                "reviewer": decision.get("reviewer"),
                "reviewed_at": reviewed_at,
                "round": state.get("review_round", 1),
            }
        ],
    }


def finalize_case(state: CaseState) -> CaseStateUpdate:
    return {
        "status": "COMPLETED",
        "result": f"案件第 {state.get('review_round', 1)} 轮预研判已通过人工复核。",
    }


def reanalyze_case(state: CaseState) -> CaseStateUpdate:
    next_round = state["review_round"] + 1
    return {
        "status": "WAITING_REVIEW",
        "review_round": next_round,
        "summary": (
            f"案件“{state['case_name']}”已根据复核意见进入第 {next_round} 轮重新研判；"
            f"当前仍纳入 {state['evidence_count']} 份证据。"
        ),
    }


def mark_evidence_required(state: CaseState) -> CaseStateUpdate:
    return {
        "status": "WAITING_EVIDENCE",
        "result": "流程等待补充证据，材料上传完成后可继续。",
    }


def await_evidence(state: CaseState) -> CaseStateUpdate:
    decision_value = interrupt(
        {
            "type": "EVIDENCE_REQUIRED",
            "question": "补充材料是否已经上传完成？",
            "case_id": state["case_id"],
            "review_round": state["review_round"],
            "allowed_actions": ["EVIDENCE_READY"],
        }
    )
    decision = cast(EvidenceReadyDecision, decision_value)
    next_round = state["review_round"] + 1
    return {
        "status": "PREPARING",
        "evidence_count": decision["evidence_count"],
        "review_round": next_round,
        "review_comment": decision.get("comment"),
        "reviewer": decision.get("reviewer"),
        "reviewed_at": decision["reviewed_at"],
        "review_history": [
            {
                "action": "EVIDENCE_READY",
                "comment": decision.get("comment"),
                "reviewer": decision.get("reviewer"),
                "reviewed_at": decision["reviewed_at"],
                "round": next_round,
            }
        ],
    }


def cancel_case(state: CaseState) -> CaseStateUpdate:
    limit_reached = (
        state["review_decision"] == "REANALYZE"
        and state["review_round"] >= state["max_review_rounds"]
    )
    result = (
        f"案件已达到最大重研次数（{state['max_review_rounds']} 轮），流程自动终止。"
        if limit_reached
        else "案件研判流程已由人工复核明确终止。"
    )
    return {"status": "CANCELLED", "result": result}


def route_review_decision(
    state: CaseState,
) -> Literal["APPROVE", "REANALYZE", "REQUEST_EVIDENCE", "CANCEL"]:
    decision = state["review_decision"]
    if decision == "REANALYZE" and state.get("review_round", 1) >= state.get(
        "max_review_rounds", 3
    ):
        return "CANCEL"
    if decision not in {"APPROVE", "REANALYZE", "REQUEST_EVIDENCE", "CANCEL"}:
        raise ValueError(f"Unsupported review decision: {decision}")
    return cast(Literal["APPROVE", "REANALYZE", "REQUEST_EVIDENCE", "CANCEL"], decision)


def build_case_workflow(checkpointer: BaseCheckpointSaver[str] | None) -> CaseWorkflowGraph:
    builder = StateGraph(CaseState)
    builder.add_node("prepare_case", prepare_case)
    builder.add_node("human_review", request_human_review)
    builder.add_node("reanalyze_case", reanalyze_case)
    builder.add_node("mark_evidence_required", mark_evidence_required)
    builder.add_node("await_evidence", await_evidence)
    builder.add_node("finalize_case", finalize_case)
    builder.add_node("cancel_case", cancel_case)
    builder.add_edge(START, "prepare_case")
    builder.add_edge("prepare_case", "human_review")
    builder.add_conditional_edges(
        "human_review",
        route_review_decision,
        {
            "APPROVE": "finalize_case",
            "REANALYZE": "reanalyze_case",
            "REQUEST_EVIDENCE": "mark_evidence_required",
            "CANCEL": "cancel_case",
        },
    )
    builder.add_edge("reanalyze_case", "human_review")
    builder.add_edge("mark_evidence_required", "await_evidence")
    builder.add_edge("await_evidence", "prepare_case")
    builder.add_edge("finalize_case", END)
    builder.add_edge("cancel_case", END)
    return builder.compile(checkpointer=checkpointer)

"""案件研判图定义：声明 LangGraph 节点、条件分支、人工中断以及最终状态流向。"""

from typing import Literal, cast

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from app.agents.customs import (
    associate_evidence_risk_agent,
    extract_evidence_elements_agent,
    summarize_conclusion_agent,
)
from app.graph.state import (
    CaseState,
    CaseStateUpdate,
    EvidenceReadyDecision,
    ReviewDecision,
)

CaseWorkflowGraph = CompiledStateGraph[CaseState, None, CaseState, CaseState]


def check_evidence_ready(state: CaseState) -> CaseStateUpdate:
    if state["analysis_scope"] != "customs_risk_analysis":
        return {"status": "PREPARING"}
    processing = state["evidence_processing"]
    ready = processing.get("ready", 0)
    blocked = sum(
        processing.get(name, 0) for name in ("pending", "failed", "blocked", "not_queued")
    )
    if ready == 0 or blocked:
        return {
            "status": "WAITING_EVIDENCE",
            "summary": (
                f"海关研判等待证据标准化完成：已就绪 {ready}，"
                f"处理中 {processing.get('pending', 0)}，"
                f"失败/不支持 {processing.get('failed', 0) + processing.get('blocked', 0)}，"
                f"未入队 {processing.get('not_queued', 0)}。"
            ),
        }
    return {"status": "PREPARING"}


def route_evidence_readiness(state: CaseState) -> Literal["CUSTOMS", "MINIMAL", "WAITING"]:
    if state["analysis_scope"] != "customs_risk_analysis":
        return "MINIMAL"
    return "WAITING" if state["status"] == "WAITING_EVIDENCE" else "CUSTOMS"


def route_analysis_scope(state: CaseState) -> Literal["CUSTOMS", "MINIMAL"]:
    return "CUSTOMS" if state["analysis_scope"] == "customs_risk_analysis" else "MINIMAL"


def load_normalized_evidence(state: CaseState) -> CaseStateUpdate:
    return {
        "status": "PREPARING",
        "summary": f"已加载 {len(state['evidence_documents'])} 份标准化证据。",
    }


def prepare_case(state: CaseState) -> CaseStateUpdate:
    summary = (
        state["summary"]
        if state.get("customs_analysis")
        else (
            f"案件“{state['case_name']}”已完成第 {state.get('review_round', 1)} 轮最小预研判准备，"
            f"当前纳入 {state['evidence_count']} 份证据，范围为 {state['analysis_scope']}。"
        )
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
        "evidence_documents": decision.get(
            "evidence_documents", state.get("evidence_documents", [])
        ),
        "evidence_processing": decision.get(
            "evidence_processing", state.get("evidence_processing", {})
        ),
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
    builder.add_node("check_evidence_ready", check_evidence_ready)
    builder.add_node("load_normalized_evidence", load_normalized_evidence)
    builder.add_node("extract_evidence_elements_agent", extract_evidence_elements_agent)
    builder.add_node("associate_evidence_risk_agent", associate_evidence_risk_agent)
    builder.add_node("summarize_conclusion_agent", summarize_conclusion_agent)
    builder.add_node("prepare_case", prepare_case)
    builder.add_node("human_review", request_human_review)
    builder.add_node("reanalyze_case", reanalyze_case)
    builder.add_node("mark_evidence_required", mark_evidence_required)
    builder.add_node("await_evidence", await_evidence)
    builder.add_node("finalize_case", finalize_case)
    builder.add_node("cancel_case", cancel_case)
    builder.add_conditional_edges(
        START,
        route_analysis_scope,
        {"CUSTOMS": "load_normalized_evidence", "MINIMAL": "prepare_case"},
    )
    builder.add_conditional_edges(
        "check_evidence_ready",
        route_evidence_readiness,
        {
            "CUSTOMS": "load_normalized_evidence",
            "MINIMAL": "prepare_case",
            "WAITING": "mark_evidence_required",
        },
    )
    builder.add_edge("load_normalized_evidence", "extract_evidence_elements_agent")
    builder.add_edge("extract_evidence_elements_agent", "associate_evidence_risk_agent")
    builder.add_edge("associate_evidence_risk_agent", "summarize_conclusion_agent")
    builder.add_edge("summarize_conclusion_agent", "prepare_case")
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
    builder.add_conditional_edges(
        "reanalyze_case",
        route_analysis_scope,
        {"CUSTOMS": "load_normalized_evidence", "MINIMAL": "prepare_case"},
    )
    builder.add_edge("mark_evidence_required", "await_evidence")
    builder.add_edge("await_evidence", "check_evidence_ready")
    builder.add_edge("finalize_case", END)
    builder.add_edge("cancel_case", END)
    return builder.compile(checkpointer=checkpointer)

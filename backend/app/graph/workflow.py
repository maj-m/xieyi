from typing import cast

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from app.graph.state import CaseState, CaseStateUpdate, ReviewDecision

CaseWorkflowGraph = CompiledStateGraph[CaseState, None, CaseState, CaseState]


def prepare_case(state: CaseState) -> CaseStateUpdate:
    summary = (
        f"案件“{state['case_name']}”已完成最小预研判准备，"
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
        }
    )
    decision = cast(ReviewDecision, decision_value)
    return {
        "review_approved": decision["approved"],
        "review_comment": decision.get("comment"),
    }


def finalize_case(state: CaseState) -> CaseStateUpdate:
    if state["review_approved"]:
        return {
            "status": "COMPLETED",
            "result": "案件最小预研判已通过人工复核。",
        }
    return {
        "status": "REJECTED",
        "result": "案件最小预研判未通过人工复核。",
    }


def build_case_workflow(checkpointer: BaseCheckpointSaver[str] | None) -> CaseWorkflowGraph:
    builder = StateGraph(CaseState)
    builder.add_node("prepare_case", prepare_case)
    builder.add_node("human_review", request_human_review)
    builder.add_node("finalize_case", finalize_case)
    builder.add_edge(START, "prepare_case")
    builder.add_edge("prepare_case", "human_review")
    builder.add_edge("human_review", "finalize_case")
    builder.add_edge("finalize_case", END)
    return builder.compile(checkpointer=checkpointer)

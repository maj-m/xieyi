import uuid

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.graph.state import CaseState
from app.graph.workflow import build_case_workflow


def initial_state() -> CaseState:
    return {
        "case_id": str(uuid.uuid4()),
        "case_name": "最小研判测试案件",
        "evidence_count": 2,
        "analysis_scope": "case_overview",
        "status": "PREPARING",
        "summary": "",
        "review_approved": None,
        "review_decision": None,
        "review_comment": None,
        "reviewer": None,
        "reviewed_at": None,
        "review_round": 1,
        "max_review_rounds": 3,
        "review_history": [],
        "result": None,
    }


def review_command(action: str, comment: str = "同意") -> Command[object]:
    return Command(
        resume={
            "action": action,
            "comment": comment,
            "reviewer": "reviewer-1",
            "reviewed_at": "2026-08-20T10:00:00+00:00",
        }
    )


@pytest.mark.asyncio
async def test_graph_interrupts_and_approves() -> None:
    graph = build_case_workflow(InMemorySaver())
    config: RunnableConfig = {"configurable": {"thread_id": str(uuid.uuid4())}}

    await graph.ainvoke(initial_state(), config=config, durability="sync")
    interrupted = await graph.aget_state(config)
    assert interrupted.values["status"] == "WAITING_REVIEW"
    assert interrupted.next == ("human_review",)
    assert interrupted.interrupts[0].value["type"] == "CASE_ANALYSIS_REVIEW"

    await graph.ainvoke(review_command("APPROVE"), config=config, durability="sync")
    completed = await graph.aget_state(config)
    assert completed.next == ()
    assert completed.interrupts == ()
    assert completed.values["status"] == "COMPLETED"
    assert completed.values["review_comment"] == "同意"
    assert len(completed.values["review_history"]) == 1


@pytest.mark.asyncio
async def test_graph_reanalysis_returns_to_review() -> None:
    graph = build_case_workflow(InMemorySaver())
    config: RunnableConfig = {"configurable": {"thread_id": str(uuid.uuid4())}}

    await graph.ainvoke(initial_state(), config=config, durability="sync")
    await graph.ainvoke(
        review_command("REANALYZE", "补充关联分析"), config=config, durability="sync"
    )
    snapshot = await graph.aget_state(config)
    assert snapshot.values["status"] == "WAITING_REVIEW"
    assert snapshot.values["review_round"] == 2
    assert snapshot.next == ("human_review",)
    assert len(snapshot.values["review_history"]) == 1


@pytest.mark.asyncio
async def test_graph_requests_and_receives_evidence() -> None:
    graph = build_case_workflow(InMemorySaver())
    config: RunnableConfig = {"configurable": {"thread_id": str(uuid.uuid4())}}

    await graph.ainvoke(initial_state(), config=config, durability="sync")
    await graph.ainvoke(
        review_command("REQUEST_EVIDENCE", "补充资金流水"),
        config=config,
        durability="sync",
    )
    waiting = await graph.aget_state(config)
    assert waiting.values["status"] == "WAITING_EVIDENCE"
    assert waiting.next == ("await_evidence",)
    assert waiting.interrupts[0].value["type"] == "EVIDENCE_REQUIRED"

    await graph.ainvoke(
        Command(
            resume={
                "action": "EVIDENCE_READY",
                "comment": "材料已上传",
                "reviewer": "reviewer-1",
                "reviewed_at": "2026-08-20T11:00:00+00:00",
                "evidence_count": 4,
            }
        ),
        config=config,
        durability="sync",
    )
    resumed = await graph.aget_state(config)
    assert resumed.values["status"] == "WAITING_REVIEW"
    assert resumed.values["review_round"] == 2
    assert resumed.values["evidence_count"] == 4
    assert resumed.next == ("human_review",)
    assert len(resumed.values["review_history"]) == 2


@pytest.mark.asyncio
async def test_graph_can_be_cancelled() -> None:
    graph = build_case_workflow(InMemorySaver())
    config: RunnableConfig = {"configurable": {"thread_id": str(uuid.uuid4())}}

    await graph.ainvoke(initial_state(), config=config, durability="sync")
    await graph.ainvoke(review_command("CANCEL", "终止研判"), config=config, durability="sync")
    cancelled = await graph.aget_state(config)
    assert cancelled.values["status"] == "CANCELLED"
    assert cancelled.next == ()

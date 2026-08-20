import uuid

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.graph.state import CaseState
from app.graph.workflow import build_case_workflow


@pytest.mark.asyncio
async def test_graph_interrupts_and_resumes() -> None:
    graph = build_case_workflow(InMemorySaver())
    thread_id = str(uuid.uuid4())
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    initial: CaseState = {
        "case_id": str(uuid.uuid4()),
        "case_name": "最小研判测试案件",
        "evidence_count": 2,
        "analysis_scope": "case_overview",
        "status": "PREPARING",
        "summary": "",
        "review_approved": None,
        "review_comment": None,
        "result": None,
    }

    await graph.ainvoke(initial, config=config, durability="sync")
    interrupted = await graph.aget_state(config)
    assert interrupted.values["status"] == "WAITING_REVIEW"
    assert interrupted.next == ("human_review",)
    assert interrupted.interrupts[0].value["type"] == "CASE_ANALYSIS_REVIEW"

    await graph.ainvoke(
        Command(resume={"approved": True, "comment": "同意"}),
        config=config,
        durability="sync",
    )
    completed = await graph.aget_state(config)
    assert completed.next == ()
    assert completed.interrupts == ()
    assert completed.values["status"] == "COMPLETED"
    assert completed.values["review_comment"] == "同意"

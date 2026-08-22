import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.db.session import async_session_factory
from app.db.types import WorkflowRunStatus
from app.main import app
from app.repositories.workflow_repository import WorkflowRepository


@pytest.mark.integration
async def test_workflow_persists_timeline_reviews_artifacts_and_idempotency(
    api_client: AsyncClient,
) -> None:
    case_response = await api_client.post(
        "/api/v1/cases", json={"name": f"business-records-{uuid.uuid4()}"}
    )
    case_id = case_response.json()["id"]
    start_payload = {
        "analysis_scope": "business_records_acceptance",
        "idempotency_key": f"start-{uuid.uuid4()}",
        "max_attempts": 3,
    }

    started = await api_client.post(f"/api/v1/cases/{case_id}/workflows", json=start_payload)
    assert started.status_code == 201, started.text
    thread_id = started.json()["thread_id"]
    assert started.json()["run"]["status"] == "WAITING_REVIEW"

    discovered = await api_client.get(
        f"/api/v1/cases/{case_id}/workflows/by-idempotency/{start_payload['idempotency_key']}"
    )
    assert discovered.status_code == 200, discovered.text
    assert discovered.json()["thread_id"] == thread_id

    duplicate_start = await api_client.post(
        f"/api/v1/cases/{case_id}/workflows", json=start_payload
    )
    assert duplicate_start.status_code == 201
    assert duplicate_start.json()["thread_id"] == thread_id

    review_key = f"review-{uuid.uuid4()}"
    decision_payload = {
        "decision": "APPROVE",
        "reviewer": "reviewer-business",
        "comment": "approved with durable business record",
        "idempotency_key": review_key,
    }
    completed = await api_client.post(
        f"/api/v1/workflows/{thread_id}/resume", json=decision_payload
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["run"]["status"] == "COMPLETED"

    duplicate_decision = await api_client.post(
        f"/api/v1/workflows/{thread_id}/resume", json=decision_payload
    )
    assert duplicate_decision.status_code == 200
    assert duplicate_decision.json()["run"]["status"] == "COMPLETED"

    timeline = await api_client.get(f"/api/v1/workflows/{thread_id}/timeline")
    assert timeline.status_code == 200, timeline.text
    record = timeline.json()
    assert record["run"]["status"] == "COMPLETED"
    assert record["run"]["attempt_count"] == 1
    assert len(record["reviews"]) == 1
    assert record["reviews"][0]["status"] == "DECIDED"
    assert record["reviews"][0]["decision"] == "APPROVE"
    assert {item["artifact_type"] for item in record["artifacts"]} == {
        "CASE_SUMMARY",
        "WORKFLOW_RESULT",
    }
    event_types = [item["event_type"] for item in record["events"]]
    assert event_types.count("WORKFLOW_STARTED") == 1
    assert "NODE_COMPLETED" in event_types
    assert "WORKFLOW_PAUSED" in event_types
    assert "REVIEW_DECIDED" in event_types
    assert "WORKFLOW_COMPLETED" in event_types
    assert [item["sequence"] for item in record["events"]] == list(
        range(1, len(record["events"]) + 1)
    )


@pytest.mark.integration
async def test_business_cancel_blocks_later_resume(api_client: AsyncClient) -> None:
    case_response = await api_client.post(
        "/api/v1/cases", json={"name": f"business-cancel-{uuid.uuid4()}"}
    )
    case_id = case_response.json()["id"]
    started = await api_client.post(
        f"/api/v1/cases/{case_id}/workflows", json={"analysis_scope": "cancel_test"}
    )
    thread_id = started.json()["thread_id"]

    cancelled = await api_client.post(
        f"/api/v1/workflows/{thread_id}/cancel",
        json={"requested_by": "operator-1", "reason": "manual cancellation"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["run"]["status"] == "CANCELLED"
    assert cancelled.json()["reviews"][0]["status"] == "CANCELLED"

    resume = await api_client.post(
        f"/api/v1/workflows/{thread_id}/resume", json={"decision": "APPROVE"}
    )
    assert resume.status_code == 409
    assert resume.json()["error"]["code"] == "WORKFLOW_NOT_WAITING"


@pytest.mark.integration
async def test_failed_business_run_can_retry_from_checkpoint(api_client: AsyncClient) -> None:
    case_response = await api_client.post(
        "/api/v1/cases", json={"name": f"business-retry-{uuid.uuid4()}"}
    )
    case_id = case_response.json()["id"]
    started = await api_client.post(
        f"/api/v1/cases/{case_id}/workflows", json={"analysis_scope": "retry_test"}
    )
    thread_id = uuid.UUID(started.json()["thread_id"])

    async with async_session_factory() as session:
        repository = WorkflowRepository(session)
        run = await repository.get_run(thread_id, for_update=True)
        assert run is not None
        run.status = WorkflowRunStatus.FAILED
        run.last_error_code = "SyntheticNodeError"
        run.last_error_message = "synthetic failure for retry acceptance"
        await session.commit()

    retried = await api_client.post(
        f"/api/v1/workflows/{thread_id}/retry", json={"requested_by": "test-operator"}
    )
    assert retried.status_code == 200, retried.text
    assert retried.json()["run"]["status"] == "WAITING_REVIEW"
    assert retried.json()["run"]["attempt_count"] == 2
    assert retried.json()["run"]["last_error_code"] is None

    timeline = await api_client.get(f"/api/v1/workflows/{thread_id}/timeline")
    event_types = [item["event_type"] for item in timeline.json()["events"]]
    assert "WORKFLOW_RETRYING" in event_types


@pytest.mark.integration
async def test_node_exception_is_persisted_and_decision_can_be_replayed(
    api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_response = await api_client.post(
        "/api/v1/cases", json={"name": f"business-failure-{uuid.uuid4()}"}
    )
    case_id = case_response.json()["id"]
    started = await api_client.post(
        f"/api/v1/cases/{case_id}/workflows", json={"analysis_scope": "failure_test"}
    )
    thread_id = uuid.UUID(started.json()["thread_id"])
    graph = app.state.case_workflow
    original_astream = graph.astream

    async def failing_astream(*args: object, **kwargs: object) -> AsyncIterator[object]:
        raise RuntimeError("synthetic graph node failure")
        yield {}

    monkeypatch.setattr(graph, "astream", failing_astream)
    with pytest.raises(RuntimeError, match="synthetic graph node failure"):
        await api_client.post(
            f"/api/v1/workflows/{thread_id}/resume",
            json={
                "decision": "APPROVE",
                "reviewer": "failure-reviewer",
                "idempotency_key": f"failure-review-{uuid.uuid4()}",
            },
        )

    async with async_session_factory() as session:
        run = await WorkflowRepository(session).get_run(thread_id)
        assert run is not None
        assert run.status == WorkflowRunStatus.FAILED
        assert run.last_error_code == "RuntimeError"
        assert run.last_error_message == "synthetic graph node failure"
        events = await WorkflowRepository(session).list_events(run.id)
        assert events[-1].event_type == "WORKFLOW_FAILED"

    monkeypatch.setattr(graph, "astream", original_astream)
    retried = await api_client.post(
        f"/api/v1/workflows/{thread_id}/retry", json={"requested_by": "recovery-operator"}
    )
    assert retried.status_code == 200, retried.text
    assert retried.json()["run"]["status"] == "COMPLETED"
    assert retried.json()["run"]["attempt_count"] == 2


@pytest.mark.integration
async def test_expired_run_is_persisted_and_cannot_resume(api_client: AsyncClient) -> None:
    case_response = await api_client.post(
        "/api/v1/cases", json={"name": f"business-timeout-{uuid.uuid4()}"}
    )
    case_id = case_response.json()["id"]
    started = await api_client.post(
        f"/api/v1/cases/{case_id}/workflows",
        json={"analysis_scope": "timeout_test", "timeout_seconds": 30},
    )
    thread_id = uuid.UUID(started.json()["thread_id"])

    async with async_session_factory() as session:
        run = await WorkflowRepository(session).get_run(thread_id, for_update=True)
        assert run is not None
        run.timeout_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()

    expired = await api_client.get(f"/api/v1/workflows/{thread_id}")
    assert expired.status_code == 200
    assert expired.json()["run"]["status"] == "TIMED_OUT"

    resume = await api_client.post(
        f"/api/v1/workflows/{thread_id}/resume", json={"decision": "APPROVE"}
    )
    assert resume.status_code == 409
    timeline = await api_client.get(f"/api/v1/workflows/{thread_id}/timeline")
    assert timeline.json()["events"][-1]["event_type"] == "WORKFLOW_TIMED_OUT"

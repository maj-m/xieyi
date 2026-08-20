import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.integration
async def test_workflow_api_interrupt_status_and_resume(api_client: AsyncClient) -> None:
    case_response = await api_client.post(
        "/api/v1/cases", json={"name": f"workflow-{uuid.uuid4()}"}
    )
    assert case_response.status_code == 201, case_response.text
    case_id = case_response.json()["id"]

    started = await api_client.post(
        f"/api/v1/cases/{case_id}/workflows",
        json={"analysis_scope": "minimal_case_review"},
    )
    assert started.status_code == 201, started.text
    waiting = started.json()
    assert waiting["status"] == "WAITING_REVIEW"
    assert waiting["next_nodes"] == ["human_review"]
    assert waiting["interrupt"]["type"] == "CASE_ANALYSIS_REVIEW"
    thread_id = waiting["thread_id"]

    recovered = await api_client.get(f"/api/v1/workflows/{thread_id}")
    assert recovered.status_code == 200
    assert recovered.json()["status"] == "WAITING_REVIEW"

    resumed = await api_client.post(
        f"/api/v1/workflows/{thread_id}/resume",
        json={"approved": True, "comment": "integration approved"},
    )
    assert resumed.status_code == 200, resumed.text
    completed = resumed.json()
    assert completed["status"] == "COMPLETED"
    assert completed["next_nodes"] == []
    assert completed["interrupt"] is None
    assert completed["state"]["review_comment"] == "integration approved"
    assert completed["state"]["review_decision"] == "APPROVE"
    assert completed["state"]["review_round"] == 1
    assert len(completed["state"]["review_history"]) == 1

    duplicate_resume = await api_client.post(
        f"/api/v1/workflows/{thread_id}/resume", json={"approved": True}
    )
    assert duplicate_resume.status_code == 409
    assert duplicate_resume.json()["error"]["code"] == "WORKFLOW_NOT_WAITING"


@pytest.mark.integration
async def test_workflow_api_evidence_branch_returns_to_review(api_client: AsyncClient) -> None:
    case_response = await api_client.post(
        "/api/v1/cases", json={"name": f"evidence-branch-{uuid.uuid4()}"}
    )
    case_id = case_response.json()["id"]
    started = await api_client.post(
        f"/api/v1/cases/{case_id}/workflows",
        json={"analysis_scope": "minimal_case_review"},
    )
    thread_id = started.json()["thread_id"]

    evidence_requested = await api_client.post(
        f"/api/v1/workflows/{thread_id}/resume",
        json={
            "decision": "REQUEST_EVIDENCE",
            "comment": "Please add bank records",
            "reviewer": "reviewer-2",
        },
    )
    waiting = evidence_requested.json()
    assert waiting["status"] == "WAITING_EVIDENCE"
    assert waiting["next_nodes"] == ["await_evidence"]
    assert waiting["interrupt"]["type"] == "EVIDENCE_REQUIRED"

    evidence_ready = await api_client.post(
        f"/api/v1/workflows/{thread_id}/resume",
        json={
            "decision": "EVIDENCE_READY",
            "comment": "Bank records uploaded",
            "reviewer": "operator-1",
        },
    )
    resumed = evidence_ready.json()
    assert resumed["status"] == "WAITING_REVIEW"
    assert resumed["next_nodes"] == ["human_review"]
    assert resumed["state"]["review_round"] == 2
    assert len(resumed["state"]["review_history"]) == 2

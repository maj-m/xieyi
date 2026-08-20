import hashlib
import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.integration
async def test_full_evidence_and_audit_flow(api_client: AsyncClient) -> None:
    created = await api_client.post("/api/v1/cases", json={"name": f"证据链测试-{uuid.uuid4()}"})
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]
    content = (
        b"From: fictional@example.com\r\nTo: investigator@example.test\r\n"
        b"Subject: fictional shipment\r\n\r\nRelease No: TEST-0001"
    )
    files = {"file": ("sample.eml", content, "message/rfc822")}
    uploaded = await api_client.post(
        f"/api/v1/cases/{case_id}/evidence",
        files=files,
        data={"source_type": "EMAIL"},
    )
    assert uploaded.status_code == 201, uploaded.text
    evidence = uploaded.json()
    assert evidence["sha256"] == hashlib.sha256(content).hexdigest()
    assert evidence["object_key"].startswith(f"cases/{case_id}/evidence/")

    fetched = await api_client.get(f"/api/v1/cases/{case_id}/evidence/{evidence['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["original_filename"] == "sample.eml"

    duplicate = await api_client.post(
        f"/api/v1/cases/{case_id}/evidence",
        files={"file": ("copy.eml", content, "message/rfc822")},
        data={"source_type": "EMAIL"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DUPLICATE_EVIDENCE"

    audits = await api_client.get(f"/api/v1/cases/{case_id}/audit")
    assert audits.status_code == 200
    event_types = {event["event_type"] for event in audits.json()}
    assert {
        "CASE_CREATED",
        "EVIDENCE_UPLOAD_STARTED",
        "EVIDENCE_HASHED",
        "EVIDENCE_STORED",
        "EVIDENCE_CREATED",
    } <= event_types
    verification = await api_client.get(f"/api/v1/cases/{case_id}/audit/verify")
    assert verification.status_code == 200
    assert verification.json()["valid"] is True

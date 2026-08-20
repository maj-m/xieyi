import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.integration
async def test_health_and_case_crud(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    created = await api_client.post(
        "/api/v1/cases",
        json={"name": f"测试案件-{uuid.uuid4()}", "description": "虚构测试数据"},
    )
    assert created.status_code == 201, created.text
    case = created.json()
    assert case["status"] == "CREATED"
    assert case["case_no"].startswith("CASE-")

    listed = await api_client.get("/api/v1/cases")
    assert listed.status_code == 200
    assert any(item["id"] == case["id"] for item in listed.json())

    fetched = await api_client.get(f"/api/v1/cases/{case['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == case["name"]

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.db.types import AuditEventType
from app.models.audit_event import AuditEvent
from app.schemas.audit import AuditVerifyResponse
from app.services.audit_service import (
    AuditService,
    calculate_event_hash,
    canonical_json,
    event_content,
)


class MemoryAuditRepository:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def lock_case_chain(self, case_id: uuid.UUID) -> None:
        return None

    async def latest(self, case_id: uuid.UUID) -> AuditEvent | None:
        matching = [event for event in self.events if event.case_id == case_id]
        return matching[-1] if matching else None

    async def append(self, event: AuditEvent) -> AuditEvent:
        self.events.append(event)
        return event

    async def list(self, case_id: uuid.UUID) -> list[AuditEvent]:
        return [event for event in self.events if event.case_id == case_id]


def test_canonical_json_is_stable_and_unicode_preserving() -> None:
    first = canonical_json({"b": 2, "a": "案件"})
    second = canonical_json({"a": "案件", "b": 2})
    assert first == second == '{"a":"案件","b":2}'


def test_event_hash_uses_previous_hash() -> None:
    content: dict[str, object] = {"event": "created"}
    assert calculate_event_hash(None, content) != calculate_event_hash("abc", content)
    assert calculate_event_hash("abc", content) == calculate_event_hash("abc", content)


@pytest.mark.asyncio
async def test_audit_chain_verification_detects_tampering() -> None:
    repository = MemoryAuditRepository()
    service = AuditService(repository)  # type: ignore[arg-type]
    case_id = uuid.uuid4()
    for index in range(2):
        event = AuditEvent(
            id=uuid.uuid4(),
            case_id=case_id,
            event_type=AuditEventType.CASE_CREATED,
            actor_id=None,
            resource_type="case",
            resource_id=str(case_id),
            operation="create",
            input_hash=None,
            output_hash=None,
            metadata_json={"index": index},
            previous_hash=repository.events[-1].event_hash if repository.events else None,
            event_hash="",
            created_at=datetime.now(UTC) + timedelta(microseconds=index),
        )
        event.event_hash = calculate_event_hash(event.previous_hash, event_content(event))
        repository.events.append(event)
    assert await service.verify(case_id) == AuditVerifyResponse(
        valid=True, event_count=2, broken_event_id=None
    )
    repository.events[1].metadata_json = {"index": 999}
    result = await service.verify(case_id)
    assert not result.valid
    assert result.broken_event_id == repository.events[1].id

import hashlib
import json
import uuid
from datetime import UTC, datetime

from app.db.types import AuditEventType
from app.models.audit_event import AuditEvent
from app.repositories.audit_repository import AuditRepository
from app.schemas.audit import AuditVerifyResponse


def canonical_json(content: dict[str, object]) -> str:
    return json.dumps(
        content, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str
    )


def calculate_event_hash(previous_hash: str | None, content: dict[str, object]) -> str:
    material = (previous_hash or "") + canonical_json(content)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def event_content(event: AuditEvent) -> dict[str, object]:
    return {
        "id": str(event.id),
        "case_id": str(event.case_id) if event.case_id else None,
        "event_type": event.event_type.value,
        "actor_id": event.actor_id,
        "resource_type": event.resource_type,
        "resource_id": event.resource_id,
        "operation": event.operation,
        "input_hash": event.input_hash,
        "output_hash": event.output_hash,
        "metadata_json": event.metadata_json,
        "created_at": event.created_at.astimezone(UTC).isoformat(),
    }


class AuditService:
    def __init__(self, repository: AuditRepository, chain_enabled: bool = True) -> None:
        self.repository = repository
        self.chain_enabled = chain_enabled

    async def append(
        self,
        *,
        case_id: uuid.UUID,
        event_type: AuditEventType,
        resource_type: str,
        operation: str,
        resource_id: str | None = None,
        actor_id: str | None = None,
        input_hash: str | None = None,
        output_hash: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> AuditEvent:
        await self.repository.lock_case_chain(case_id)
        previous = await self.repository.latest(case_id) if self.chain_enabled else None
        event = AuditEvent(
            id=uuid.uuid4(),
            case_id=case_id,
            event_type=event_type,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            operation=operation,
            input_hash=input_hash,
            output_hash=output_hash,
            metadata_json=metadata or {},
            previous_hash=previous.event_hash if previous else None,
            event_hash="",
            created_at=datetime.now(UTC),
        )
        event.event_hash = calculate_event_hash(event.previous_hash, event_content(event))
        return await self.repository.append(event)

    async def list(self, case_id: uuid.UUID) -> list[AuditEvent]:
        return await self.repository.list(case_id)

    async def verify(self, case_id: uuid.UUID) -> AuditVerifyResponse:
        events = await self.repository.list(case_id)
        previous_hash: str | None = None
        for event in events:
            expected = calculate_event_hash(previous_hash, event_content(event))
            if event.previous_hash != previous_hash or event.event_hash != expected:
                return AuditVerifyResponse(
                    valid=False, event_count=len(events), broken_event_id=event.id
                )
            previous_hash = event.event_hash
        return AuditVerifyResponse(valid=True, event_count=len(events), broken_event_id=None)

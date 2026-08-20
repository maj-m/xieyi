import uuid
from typing import cast

from sqlalchemy import Select, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_event import AuditEvent


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def lock_case_chain(self, case_id: uuid.UUID) -> None:
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:case_id))"), {"case_id": str(case_id)}
        )

    async def latest(self, case_id: uuid.UUID) -> AuditEvent | None:
        query: Select[tuple[AuditEvent]] = (
            select(AuditEvent)
            .where(AuditEvent.case_id == case_id)
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
            .limit(1)
        )
        return cast(AuditEvent | None, await self.session.scalar(query))

    async def append(self, event: AuditEvent) -> AuditEvent:
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def list(self, case_id: uuid.UUID) -> list[AuditEvent]:
        query: Select[tuple[AuditEvent]] = (
            select(AuditEvent)
            .where(AuditEvent.case_id == case_id)
            .order_by(AuditEvent.created_at, AuditEvent.id)
        )
        return list((await self.session.scalars(query)).all())

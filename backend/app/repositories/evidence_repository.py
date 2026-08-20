import uuid
from typing import cast

from sqlalchemy import Select, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evidence import Evidence


class EvidenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, evidence: Evidence) -> Evidence:
        self.session.add(evidence)
        await self.session.flush()
        await self.session.refresh(evidence)
        return evidence

    async def get(self, case_id: uuid.UUID, evidence_id: uuid.UUID) -> Evidence | None:
        query: Select[tuple[Evidence]] = select(Evidence).where(
            Evidence.id == evidence_id, Evidence.case_id == case_id
        )
        return cast(Evidence | None, await self.session.scalar(query))

    async def get_by_hash(self, case_id: uuid.UUID, sha256: str) -> Evidence | None:
        query: Select[tuple[Evidence]] = select(Evidence).where(
            Evidence.case_id == case_id, Evidence.sha256 == sha256
        )
        return cast(Evidence | None, await self.session.scalar(query))

    async def list(self, case_id: uuid.UUID) -> list[Evidence]:
        query: Select[tuple[Evidence]] = (
            select(Evidence).where(Evidence.case_id == case_id).order_by(Evidence.created_at.desc())
        )
        return list((await self.session.scalars(query)).all())

    async def delete(self, evidence: Evidence) -> None:
        await self.session.execute(delete(Evidence).where(Evidence.id == evidence.id))
        await self.session.flush()

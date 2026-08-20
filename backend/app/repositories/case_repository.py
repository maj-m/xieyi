import uuid

from sqlalchemy import Select, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case


class CaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def next_sequence_value(self) -> int:
        result = await self.session.execute(text("SELECT nextval('case_number_seq')"))
        return int(result.scalar_one())

    async def create(self, case: Case) -> Case:
        self.session.add(case)
        await self.session.flush()
        await self.session.refresh(case)
        return case

    async def get(self, case_id: uuid.UUID) -> Case | None:
        return await self.session.get(Case, case_id)

    async def list(self, offset: int = 0, limit: int = 100) -> list[Case]:
        query: Select[tuple[Case]] = (
            select(Case).order_by(Case.created_at.desc()).offset(offset).limit(limit)
        )
        return list((await self.session.scalars(query)).all())

    async def flush(self, case: Case) -> Case:
        await self.session.flush()
        await self.session.refresh(case)
        return case

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.types import AuditEventType, CaseStatus
from app.errors import NotFoundError
from app.models.case import Case
from app.repositories.case_repository import CaseRepository
from app.schemas.case import CaseCreate, CaseUpdate
from app.services.audit_service import AuditService
from app.utils.ids import format_case_no


class CaseService:
    def __init__(
        self,
        session: AsyncSession,
        repository: CaseRepository,
        audit_service: AuditService,
    ) -> None:
        self.session = session
        self.repository = repository
        self.audit_service = audit_service

    async def create_case(self, data: CaseCreate) -> Case:
        sequence = await self.repository.next_sequence_value()
        case = Case(
            case_no=format_case_no(sequence),
            name=data.name,
            description=data.description,
            status=CaseStatus.CREATED,
            created_by=data.created_by,
        )
        case = await self.repository.create(case)
        await self.audit_service.append(
            case_id=case.id,
            event_type=AuditEventType.CASE_CREATED,
            resource_type="case",
            resource_id=str(case.id),
            operation="create",
            actor_id=data.created_by,
            metadata={"case_no": case.case_no},
        )
        await self.session.commit()
        return case

    async def get_case(self, case_id: uuid.UUID) -> Case:
        case = await self.repository.get(case_id)
        if case is None:
            raise NotFoundError("CASE_NOT_FOUND", "Case not found")
        return case

    async def list_cases(self, offset: int = 0, limit: int = 100) -> list[Case]:
        return await self.repository.list(offset, limit)

    async def update_case(self, case_id: uuid.UUID, data: CaseUpdate) -> Case:
        case = await self.get_case(case_id)
        changes = data.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(case, field, value)
        case = await self.repository.flush(case)
        await self.audit_service.append(
            case_id=case.id,
            event_type=AuditEventType.CASE_UPDATED,
            resource_type="case",
            resource_id=str(case.id),
            operation="update",
            metadata={"changed_fields": sorted(changes)},
        )
        await self.session.commit()
        return case

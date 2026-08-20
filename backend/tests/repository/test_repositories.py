import uuid

import pytest

from app.db.session import async_session_factory
from app.db.types import AuditEventType, CaseStatus, DocumentType, EvidenceSourceType
from app.models.case import Case
from app.models.evidence import Evidence
from app.repositories.audit_repository import AuditRepository
from app.repositories.case_repository import CaseRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.services.audit_service import AuditService
from app.utils.ids import format_case_no


@pytest.mark.integration
async def test_repository_create_get_list_and_audit_append() -> None:
    async with async_session_factory() as session:
        cases = CaseRepository(session)
        evidence_repository = EvidenceRepository(session)
        case = await cases.create(
            Case(
                case_no=format_case_no(await cases.next_sequence_value()),
                name=f"repository-{uuid.uuid4()}",
                status=CaseStatus.CREATED,
            )
        )
        evidence = await evidence_repository.create(
            Evidence(
                id=uuid.uuid4(),
                case_id=case.id,
                original_filename="bank.csv",
                stored_filename="bank.csv",
                object_key=f"cases/{case.id}/repository/{uuid.uuid4()}/bank.csv",
                mime_type="text/csv",
                file_extension=".csv",
                file_size=3,
                sha256=uuid.uuid4().hex * 2,
                source_type=EvidenceSourceType.BANK,
                document_type=DocumentType.CSV,
                metadata_json={},
            )
        )
        audit = AuditService(AuditRepository(session))
        event = await audit.append(
            case_id=case.id,
            event_type=AuditEventType.CASE_CREATED,
            resource_type="case",
            resource_id=str(case.id),
            operation="create",
        )
        await session.commit()
        assert await cases.get(case.id) == case
        assert case in await cases.list()
        assert await evidence_repository.get(case.id, evidence.id) == evidence
        assert evidence in await evidence_repository.list(case.id)
        assert event in await AuditRepository(session).list(case.id)

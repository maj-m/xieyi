import uuid

from fastapi import APIRouter

from app.dependencies import AuditServiceDep, CaseServiceDep
from app.schemas.audit import AuditEventResponse, AuditVerifyResponse

router = APIRouter(prefix="/cases/{case_id}/audit", tags=["audit"])


@router.get("", response_model=list[AuditEventResponse])
async def list_audit(
    case_id: uuid.UUID, case_service: CaseServiceDep, audit_service: AuditServiceDep
) -> list[AuditEventResponse]:
    await case_service.get_case(case_id)
    return [AuditEventResponse.model_validate(item) for item in await audit_service.list(case_id)]


@router.get("/verify", response_model=AuditVerifyResponse)
async def verify_audit(
    case_id: uuid.UUID, case_service: CaseServiceDep, audit_service: AuditServiceDep
) -> AuditVerifyResponse:
    await case_service.get_case(case_id)
    return await audit_service.verify(case_id)

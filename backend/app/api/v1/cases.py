import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.dependencies import CaseServiceDep
from app.schemas.case import CaseCreate, CaseResponse, CaseUpdate

router = APIRouter(prefix="/cases", tags=["cases"])


@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
async def create_case(data: CaseCreate, service: CaseServiceDep) -> CaseResponse:
    return CaseResponse.model_validate(await service.create_case(data))


@router.get("", response_model=list[CaseResponse])
async def list_cases(
    service: CaseServiceDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[CaseResponse]:
    return [CaseResponse.model_validate(item) for item in await service.list_cases(offset, limit)]


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(case_id: uuid.UUID, service: CaseServiceDep) -> CaseResponse:
    return CaseResponse.model_validate(await service.get_case(case_id))


@router.patch("/{case_id}", response_model=CaseResponse)
async def update_case(
    case_id: uuid.UUID, data: CaseUpdate, service: CaseServiceDep
) -> CaseResponse:
    return CaseResponse.model_validate(await service.update_case(case_id, data))

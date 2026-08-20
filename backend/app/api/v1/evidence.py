import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, Response, UploadFile, status

from app.db.types import EvidenceSourceType
from app.dependencies import EvidenceServiceDep
from app.schemas.evidence import EvidenceResponse

router = APIRouter(prefix="/cases/{case_id}/evidence", tags=["evidence"])


@router.post("", response_model=EvidenceResponse, status_code=status.HTTP_201_CREATED)
async def upload_evidence(
    case_id: uuid.UUID,
    service: EvidenceServiceDep,
    file: Annotated[UploadFile, File()],
    source_type: Annotated[EvidenceSourceType, Form()] = EvidenceSourceType.OTHER,
    created_by: Annotated[str | None, Form()] = None,
    parent_evidence_id: Annotated[uuid.UUID | None, Form()] = None,
) -> EvidenceResponse:
    evidence = await service.upload_evidence(
        case_id, file, source_type, created_by, parent_evidence_id
    )
    return EvidenceResponse.model_validate(evidence)


@router.get("", response_model=list[EvidenceResponse])
async def list_evidence(case_id: uuid.UUID, service: EvidenceServiceDep) -> list[EvidenceResponse]:
    return [EvidenceResponse.model_validate(item) for item in await service.list_evidence(case_id)]


@router.get("/{evidence_id}", response_model=EvidenceResponse)
async def get_evidence(
    case_id: uuid.UUID, evidence_id: uuid.UUID, service: EvidenceServiceDep
) -> EvidenceResponse:
    return EvidenceResponse.model_validate(await service.get_evidence(case_id, evidence_id))


@router.delete("/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evidence(
    case_id: uuid.UUID, evidence_id: uuid.UUID, service: EvidenceServiceDep
) -> Response:
    await service.delete_evidence(case_id, evidence_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

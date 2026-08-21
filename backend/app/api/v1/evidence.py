"""证据 HTTP 接口：提供原始文件上传查询，以及标准化任务入队、进度和结果查询。"""

import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, Response, UploadFile, status

from app.db.types import EvidenceSourceType
from app.dependencies import EvidenceProcessingServiceDep, EvidenceServiceDep
from app.schemas.evidence import EvidenceResponse
from app.schemas.evidence_processing import (
    NormalizedDocumentResponse,
    ProcessingJobCreate,
    ProcessingJobResponse,
)

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


@router.get("/processing-jobs", response_model=list[ProcessingJobResponse])
async def list_processing_jobs(
    case_id: uuid.UUID,
    service: EvidenceProcessingServiceDep,
    evidence_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[ProcessingJobResponse]:
    jobs = await service.list_jobs(case_id, evidence_id)
    return [ProcessingJobResponse.model_validate(item) for item in jobs]


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


@router.post(
    "/{evidence_id}/processing-jobs",
    response_model=ProcessingJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def enqueue_processing(
    case_id: uuid.UUID,
    evidence_id: uuid.UUID,
    data: ProcessingJobCreate,
    service: EvidenceProcessingServiceDep,
) -> ProcessingJobResponse:
    job = await service.enqueue(case_id, evidence_id, data.idempotency_key, data.max_attempts)
    return ProcessingJobResponse.model_validate(job)


@router.get("/{evidence_id}/normalized", response_model=NormalizedDocumentResponse)
async def get_normalized_document(
    case_id: uuid.UUID,
    evidence_id: uuid.UUID,
    service: EvidenceProcessingServiceDep,
) -> NormalizedDocumentResponse:
    document = await service.get_document(case_id, evidence_id)
    return NormalizedDocumentResponse.model_validate(document)

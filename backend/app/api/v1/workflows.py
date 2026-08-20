import uuid

from fastapi import APIRouter, status

from app.dependencies import WorkflowServiceDep
from app.schemas.workflow import WorkflowResponse, WorkflowResume, WorkflowStart

router = APIRouter(tags=["workflows"])


@router.post(
    "/cases/{case_id}/workflows",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_workflow(
    case_id: uuid.UUID, data: WorkflowStart, service: WorkflowServiceDep
) -> WorkflowResponse:
    return await service.start(case_id, data)


@router.get("/workflows/{thread_id}", response_model=WorkflowResponse)
async def get_workflow(thread_id: uuid.UUID, service: WorkflowServiceDep) -> WorkflowResponse:
    return await service.get(thread_id)


@router.post("/workflows/{thread_id}/resume", response_model=WorkflowResponse)
async def resume_workflow(
    thread_id: uuid.UUID, data: WorkflowResume, service: WorkflowServiceDep
) -> WorkflowResponse:
    return await service.resume(thread_id, data)

import asyncio
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request, status
from fastapi.responses import StreamingResponse

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


@router.get("/workflows/{thread_id}/events", response_class=StreamingResponse)
async def stream_workflow_events(
    thread_id: uuid.UUID, request: Request, service: WorkflowServiceDep
) -> StreamingResponse:
    """Stream checkpoint snapshots and reconnect safely after a process restart."""
    initial = await service.get(thread_id)

    async def event_stream() -> AsyncIterator[str]:
        snapshot = initial
        previous: str | None = None
        heartbeat_ticks = 0
        while not await request.is_disconnected():
            payload = snapshot.model_dump_json()
            if payload != previous:
                yield f"event: workflow_snapshot\ndata: {payload}\n\n"
                previous = payload
                heartbeat_ticks = 0
            elif heartbeat_ticks >= 14:
                yield ": keep-alive\n\n"
                heartbeat_ticks = 0

            await asyncio.sleep(1)
            heartbeat_ticks += 1
            snapshot = await service.get(thread_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/workflows/{thread_id}/resume", response_model=WorkflowResponse)
async def resume_workflow(
    thread_id: uuid.UUID, data: WorkflowResume, service: WorkflowServiceDep
) -> WorkflowResponse:
    return await service.resume(thread_id, data)

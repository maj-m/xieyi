"""研判工作流 HTTP 接口：提供启动、查询、恢复、重试、取消以及 SSE 实时事件订阅。"""

import asyncio
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request, status
from fastapi.responses import StreamingResponse

from app.dependencies import WorkflowServiceDep
from app.schemas.workflow import (
    WorkflowCancel,
    WorkflowEventResponse,
    WorkflowResponse,
    WorkflowResume,
    WorkflowRetry,
    WorkflowRunResponse,
    WorkflowStart,
    WorkflowTimelineResponse,
)

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


@router.get(
    "/cases/{case_id}/workflows/by-idempotency/{idempotency_key}",
    response_model=WorkflowRunResponse,
)
async def find_workflow_run(
    case_id: uuid.UUID, idempotency_key: str, service: WorkflowServiceDep
) -> WorkflowRunResponse:
    return await service.find_run_by_idempotency(case_id, idempotency_key)


@router.get("/workflows/{thread_id}/timeline", response_model=WorkflowTimelineResponse)
async def get_workflow_timeline(
    thread_id: uuid.UUID, service: WorkflowServiceDep
) -> WorkflowTimelineResponse:
    return await service.timeline(thread_id)


@router.get("/workflows/{thread_id}/events", response_class=StreamingResponse)
async def stream_workflow_events(
    thread_id: uuid.UUID, request: Request, service: WorkflowServiceDep
) -> StreamingResponse:
    """Stream checkpoint snapshots and reconnect safely after a process restart."""
    initial = await service.get(thread_id)

    async def event_stream() -> AsyncIterator[str]:
        snapshot = initial
        previous: str | None = None
        last_sequence = 0
        heartbeat_ticks = 0
        while not await request.is_disconnected():
            events = await service.list_events(thread_id, after_sequence=last_sequence)
            for item in events:
                event_payload = WorkflowEventResponse.model_validate(item).model_dump_json()
                yield f"id: {item.sequence}\nevent: workflow_event\ndata: {event_payload}\n\n"
                last_sequence = item.sequence
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


@router.post("/workflows/{thread_id}/retry", response_model=WorkflowResponse)
async def retry_workflow(
    thread_id: uuid.UUID, data: WorkflowRetry, service: WorkflowServiceDep
) -> WorkflowResponse:
    return await service.retry(thread_id, data)


@router.post("/workflows/{thread_id}/cancel", response_model=WorkflowTimelineResponse)
async def cancel_workflow(
    thread_id: uuid.UUID, data: WorkflowCancel, service: WorkflowServiceDep
) -> WorkflowTimelineResponse:
    return await service.cancel(thread_id, data)


"""研判工作流 HTTP 接口：提供启动、查询、恢复、重试、取消以及 SSE 实时事件订阅。"""

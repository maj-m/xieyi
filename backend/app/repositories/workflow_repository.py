"""工作流业务仓储：封装运行记录、节点事件、人工复核任务和分析产物的 PostgreSQL 操作。"""

import uuid
from datetime import datetime
from typing import cast

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.types import (
    ArtifactStatus,
    ReviewTaskStatus,
    WorkflowEventType,
    WorkflowRunStatus,
)
from app.models.workflow import AnalysisArtifact, ReviewTask, WorkflowEvent, WorkflowRun


class WorkflowRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_run(self, run: WorkflowRun) -> WorkflowRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_run(
        self, thread_id: uuid.UUID, *, for_update: bool = False
    ) -> WorkflowRun | None:
        query: Select[tuple[WorkflowRun]] = select(WorkflowRun).where(
            WorkflowRun.thread_id == thread_id
        )
        if for_update:
            query = query.with_for_update()
        return cast(WorkflowRun | None, await self.session.scalar(query))

    async def get_run_by_idempotency(
        self, case_id: uuid.UUID, idempotency_key: str
    ) -> WorkflowRun | None:
        query: Select[tuple[WorkflowRun]] = select(WorkflowRun).where(
            WorkflowRun.case_id == case_id,
            WorkflowRun.idempotency_key == idempotency_key,
        )
        return cast(WorkflowRun | None, await self.session.scalar(query))

    async def append_event(
        self,
        run: WorkflowRun,
        event_type: WorkflowEventType,
        *,
        node_name: str | None = None,
        payload: dict[str, object] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> WorkflowEvent:
        latest = await self.session.scalar(
            select(func.max(WorkflowEvent.sequence)).where(WorkflowEvent.run_id == run.id)
        )
        event = WorkflowEvent(
            run_id=run.id,
            case_id=run.case_id,
            sequence=int(latest or 0) + 1,
            event_type=event_type,
            node_name=node_name,
            status=run.status.value if hasattr(run.status, "value") else str(run.status),
            attempt=run.attempt_count,
            payload_json=payload or {},
            error_code=error_code,
            error_message=error_message,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def list_events(
        self, run_id: uuid.UUID, *, after_sequence: int = 0
    ) -> list[WorkflowEvent]:
        query: Select[tuple[WorkflowEvent]] = (
            select(WorkflowEvent)
            .where(WorkflowEvent.run_id == run_id, WorkflowEvent.sequence > after_sequence)
            .order_by(WorkflowEvent.sequence)
        )
        return list((await self.session.scalars(query)).all())

    async def get_review_by_idempotency(
        self, run_id: uuid.UUID, idempotency_key: str
    ) -> ReviewTask | None:
        query: Select[tuple[ReviewTask]] = select(ReviewTask).where(
            ReviewTask.run_id == run_id,
            ReviewTask.idempotency_key == idempotency_key,
        )
        return cast(ReviewTask | None, await self.session.scalar(query))

    async def get_review(
        self, run_id: uuid.UUID, review_round: int, interrupt_type: str
    ) -> ReviewTask | None:
        query: Select[tuple[ReviewTask]] = select(ReviewTask).where(
            ReviewTask.run_id == run_id,
            ReviewTask.review_round == review_round,
            ReviewTask.interrupt_type == interrupt_type,
        )
        return cast(ReviewTask | None, await self.session.scalar(query))

    async def ensure_pending_review(
        self, run: WorkflowRun, review_round: int, interrupt_type: str
    ) -> ReviewTask:
        existing = await self.get_review(run.id, review_round, interrupt_type)
        if existing is not None:
            return existing
        task = ReviewTask(
            run_id=run.id,
            case_id=run.case_id,
            review_round=review_round,
            interrupt_type=interrupt_type,
            status=ReviewTaskStatus.PENDING,
        )
        self.session.add(task)
        await self.session.flush()
        return task

    async def decide_review(
        self,
        task: ReviewTask,
        *,
        decision: str,
        reviewer: str | None,
        comment: str | None,
        idempotency_key: str | None,
        decided_at: datetime,
    ) -> ReviewTask:
        task.status = ReviewTaskStatus.DECIDED
        task.decision = decision
        task.reviewer = reviewer
        task.comment = comment
        task.idempotency_key = idempotency_key
        task.decided_at = decided_at
        await self.session.flush()
        return task

    async def list_reviews(self, run_id: uuid.UUID) -> list[ReviewTask]:
        query: Select[tuple[ReviewTask]] = (
            select(ReviewTask)
            .where(ReviewTask.run_id == run_id)
            .order_by(ReviewTask.requested_at, ReviewTask.id)
        )
        return list((await self.session.scalars(query)).all())

    async def create_artifact(
        self,
        run: WorkflowRun,
        *,
        node_name: str,
        artifact_type: str,
        content: dict[str, object],
    ) -> AnalysisArtifact:
        latest = await self.session.scalar(
            select(func.max(AnalysisArtifact.version)).where(
                AnalysisArtifact.run_id == run.id,
                AnalysisArtifact.node_name == node_name,
                AnalysisArtifact.artifact_type == artifact_type,
            )
        )
        artifact = AnalysisArtifact(
            run_id=run.id,
            case_id=run.case_id,
            node_name=node_name,
            artifact_type=artifact_type,
            version=int(latest or 0) + 1,
            status=ArtifactStatus.CREATED,
            content_json=content,
        )
        self.session.add(artifact)
        await self.session.flush()
        return artifact

    async def list_artifacts(self, run_id: uuid.UUID) -> list[AnalysisArtifact]:
        query: Select[tuple[AnalysisArtifact]] = (
            select(AnalysisArtifact)
            .where(AnalysisArtifact.run_id == run_id)
            .order_by(AnalysisArtifact.created_at, AnalysisArtifact.id)
        )
        return list((await self.session.scalars(query)).all())

    @staticmethod
    def set_run_status(
        run: WorkflowRun,
        status: WorkflowRunStatus,
        *,
        current_node: str | None = None,
        now: datetime | None = None,
    ) -> None:
        run.status = status
        run.current_node = current_node
        run.heartbeat_at = now
        run.version += 1

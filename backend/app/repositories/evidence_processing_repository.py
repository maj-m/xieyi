"""证据处理仓储：持久化解析任务和标准化结果，并用数据库锁安全地向 Worker 分发任务。"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.types import EvidenceProcessingStatus
from app.models.evidence_processing import (
    EvidenceDerivative,
    EvidenceProcessingJob,
    NormalizedDocument,
)


class EvidenceProcessingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_job(self, job: EvidenceProcessingJob) -> EvidenceProcessingJob:
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_job(self, job_id: uuid.UUID) -> EvidenceProcessingJob | None:
        return cast(
            EvidenceProcessingJob | None,
            await self.session.scalar(
                select(EvidenceProcessingJob).where(EvidenceProcessingJob.id == job_id)
            ),
        )

    async def get_idempotent(
        self, evidence_id: uuid.UUID, key: str
    ) -> EvidenceProcessingJob | None:
        query = select(EvidenceProcessingJob).where(
            EvidenceProcessingJob.evidence_id == evidence_id,
            EvidenceProcessingJob.idempotency_key == key,
        )
        return cast(EvidenceProcessingJob | None, await self.session.scalar(query))

    async def get_latest_job(self, evidence_id: uuid.UUID) -> EvidenceProcessingJob | None:
        query = (
            select(EvidenceProcessingJob)
            .where(EvidenceProcessingJob.evidence_id == evidence_id)
            .order_by(EvidenceProcessingJob.created_at.desc())
            .limit(1)
        )
        return cast(EvidenceProcessingJob | None, await self.session.scalar(query))

    async def list_jobs(
        self, case_id: uuid.UUID, evidence_id: uuid.UUID | None = None
    ) -> list[EvidenceProcessingJob]:
        query: Select[tuple[EvidenceProcessingJob]] = select(EvidenceProcessingJob).where(
            EvidenceProcessingJob.case_id == case_id
        )
        if evidence_id is not None:
            query = query.where(EvidenceProcessingJob.evidence_id == evidence_id)
        return list(
            (
                await self.session.scalars(query.order_by(EvidenceProcessingJob.created_at.desc()))
            ).all()
        )

    async def claim_next(self, worker_id: str, lease_seconds: int) -> EvidenceProcessingJob | None:
        now = datetime.now(UTC)
        query = (
            select(EvidenceProcessingJob)
            .where(
                EvidenceProcessingJob.available_at <= now,
                EvidenceProcessingJob.attempt_count < EvidenceProcessingJob.max_attempts,
                or_(
                    EvidenceProcessingJob.status == EvidenceProcessingStatus.QUEUED,
                    (EvidenceProcessingJob.status == EvidenceProcessingStatus.PROCESSING)
                    & (EvidenceProcessingJob.lease_expires_at < now),
                ),
            )
            .order_by(EvidenceProcessingJob.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        job = cast(EvidenceProcessingJob | None, await self.session.scalar(query))
        if job is None:
            return None
        job.status = EvidenceProcessingStatus.PROCESSING
        job.lease_owner = worker_id
        job.lease_expires_at = now + timedelta(seconds=lease_seconds)
        job.heartbeat_at = now
        job.started_at = job.started_at or now
        job.attempt_count += 1
        await self.session.flush()
        return job

    async def add_document(self, document: NormalizedDocument) -> None:
        self.session.add(document)
        await self.session.flush()

    async def add_derivative(self, derivative: EvidenceDerivative) -> None:
        self.session.add(derivative)
        await self.session.flush()

    async def get_document(self, evidence_id: uuid.UUID) -> NormalizedDocument | None:
        query = (
            select(NormalizedDocument)
            .where(NormalizedDocument.evidence_id == evidence_id)
            .order_by(NormalizedDocument.created_at.desc())
        )
        return cast(NormalizedDocument | None, await self.session.scalar(query))

    async def list_documents(self, case_id: uuid.UUID) -> list[NormalizedDocument]:
        query: Select[tuple[NormalizedDocument]] = (
            select(NormalizedDocument)
            .where(NormalizedDocument.case_id == case_id)
            .order_by(NormalizedDocument.created_at.desc())
        )
        return list((await self.session.scalars(query)).all())

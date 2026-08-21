"""证据处理 Worker 入口：持续领取 PostgreSQL 中的解析任务，并驱动文件标准化链路。"""

import asyncio
import os
import socket
import uuid

from app.db.session import async_session_factory
from app.dependencies import get_storage
from app.parsers.registry import build_parser_registry
from app.repositories.case_repository import CaseRepository
from app.repositories.evidence_processing_repository import EvidenceProcessingRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.services.evidence_processing_service import EvidenceProcessingService


async def run() -> None:
    worker_id = os.getenv("WORKER_ID", f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}")
    poll_seconds = float(os.getenv("WORKER_POLL_SECONDS", "2"))
    while True:
        async with async_session_factory() as session:
            service = EvidenceProcessingService(
                session,
                CaseRepository(session),
                EvidenceRepository(session),
                EvidenceProcessingRepository(session),
                get_storage(),
                build_parser_registry(),
            )
            processed = await service.claim_and_process(worker_id)
        if not processed:
            await asyncio.sleep(poll_seconds)


if __name__ == "__main__":
    asyncio.run(run())

from fastapi import APIRouter
from sqlalchemy import text

from app.dependencies import SessionDep, StorageDep
from app.schemas.common import HealthResponse, ReadyResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/health/ready", response_model=ReadyResponse)
async def ready(session: SessionDep, storage: StorageDep) -> ReadyResponse:
    postgres_ready = False
    try:
        await session.execute(text("SELECT 1"))
        postgres_ready = True
    except Exception:
        postgres_ready = False
    minio_ready = await storage.ready()
    status = "ok" if postgres_ready and minio_ready else "not_ready"
    return ReadyResponse(status=status, postgres=postgres_ready, minio=minio_ready)

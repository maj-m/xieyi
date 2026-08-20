import asyncio
import os
import sys
from collections.abc import Callable, Mapping

import pytest
from _pytest.config import Config
from _pytest.nodes import Item
from httpx import ASGITransport, AsyncClient

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://whale:whale-dev-password@localhost:5432/whale_mas"
)
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
os.environ.setdefault("MINIO_ACCESS_KEY", "whale-minio")
os.environ.setdefault("MINIO_SECRET_KEY", "whale-minio-password")
os.environ.setdefault(
    "CHECKPOINT_DATABASE_URL",
    "postgresql://whale:whale-dev-password@localhost:5432/whale_mas",
)
os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")

from app.main import app  # noqa: E402


def pytest_asyncio_loop_factories(
    config: Config, item: Item
) -> Mapping[str, Callable[[], asyncio.AbstractEventLoop]] | None:
    if sys.platform == "win32":
        return {"selector": asyncio.SelectorEventLoop}
    return None


@pytest.fixture
async def api_client() -> AsyncClient:
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            yield client

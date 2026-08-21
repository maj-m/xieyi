from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ObjectStat:
    size: int
    content_type: str | None
    etag: str | None


class ObjectStorage(Protocol):
    async def put(self, object_key: str, source: Path, content_type: str) -> None: ...

    async def get(self, object_key: str) -> bytes: ...

    async def stat(self, object_key: str) -> ObjectStat: ...

    async def download_to(self, object_key: str, destination: Path) -> ObjectStat: ...

    async def delete(self, object_key: str) -> None: ...

    async def exists(self, object_key: str) -> bool: ...

    async def ready(self) -> bool: ...

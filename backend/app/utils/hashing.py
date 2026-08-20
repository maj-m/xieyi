import hashlib
from collections.abc import AsyncIterator, Iterator
from pathlib import Path


def sha256_chunks(chunks: Iterator[bytes]) -> str:
    digest = hashlib.sha256()
    for chunk in chunks:
        digest.update(chunk)
    return digest.hexdigest()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    def chunks() -> Iterator[bytes]:
        with path.open("rb") as file_handle:
            while chunk := file_handle.read(chunk_size):
                yield chunk

    return sha256_chunks(chunks())


async def sha256_stream(chunks: AsyncIterator[bytes]) -> str:
    digest = hashlib.sha256()
    async for chunk in chunks:
        digest.update(chunk)
    return digest.hexdigest()

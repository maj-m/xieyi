import asyncio
from pathlib import Path

from minio import Minio
from minio.error import S3Error

from app.errors import StorageError


class MinIOStorage:
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False,
    ) -> None:
        self.client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
        self.bucket = bucket

    async def put(self, object_key: str, source: Path, content_type: str) -> None:
        try:
            await asyncio.to_thread(
                self.client.fput_object,
                self.bucket,
                object_key,
                str(source),
                content_type=content_type,
            )
        except S3Error as exc:
            raise StorageError("Unable to store evidence object") from exc

    async def get(self, object_key: str) -> bytes:
        def read_object() -> bytes:
            response = self.client.get_object(self.bucket, object_key)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()

        try:
            return await asyncio.to_thread(read_object)
        except S3Error as exc:
            raise StorageError("Unable to read evidence object") from exc

    async def delete(self, object_key: str) -> None:
        try:
            await asyncio.to_thread(self.client.remove_object, self.bucket, object_key)
        except S3Error as exc:
            raise StorageError("Unable to delete evidence object") from exc

    async def exists(self, object_key: str) -> bool:
        try:
            await asyncio.to_thread(self.client.stat_object, self.bucket, object_key)
            return True
        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject", "NoSuchBucket"}:
                return False
            raise StorageError("Unable to inspect evidence object") from exc

    async def ready(self) -> bool:
        try:
            return await asyncio.to_thread(self.client.bucket_exists, self.bucket)
        except S3Error:
            return False

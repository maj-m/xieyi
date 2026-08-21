from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Whale MAS"
    app_env: str = "development"
    app_debug: bool = False
    api_v1_prefix: str = "/api/v1"
    database_url: str
    checkpoint_database_url: str | None = None
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = Field(repr=False)
    minio_secret_key: str = Field(repr=False)
    minio_bucket: str = "whale-mas"
    minio_secure: bool = False
    max_upload_size_mb: int = 100
    allowed_file_extensions: tuple[str, ...] = (
        ".eml",
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".csv",
        ".txt",
        ".jpg",
        ".jpeg",
        ".png",
    )
    audit_hash_chain_enabled: bool = True

    @property
    def resolved_checkpoint_database_url(self) -> str:
        url = self.checkpoint_database_url or self.database_url
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)

    @field_validator("allowed_file_extensions", mode="before")
    @classmethod
    def parse_extensions(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(item.strip().lower() for item in value.split(",") if item.strip())
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # Values are loaded from environment by BaseSettings.

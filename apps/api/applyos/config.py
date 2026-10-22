import os
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    environment: str = "development"
    database_url: str = "sqlite:///./data/applyos-dev.db"
    web_origin: str = "http://localhost:3000"
    cookie_secure: bool = False
    session_days: int = 7
    storage_backend: str = "local"
    storage_path: Path = Path("data/private-files")
    s3_bucket: str = ""
    s3_endpoint_url: str | None = None
    s3_region: str = "us-east-1"
    max_upload_bytes: int = 5 * 1024 * 1024
    usajobs_api_key: SecretStr = SecretStr("")
    usajobs_email: SecretStr = SecretStr("")
    adzuna_app_id: SecretStr = SecretStr("")
    adzuna_app_key: SecretStr = SecretStr("")

    @model_validator(mode="after")
    def production_safe(self) -> "Settings":
        # Marketplace connections use the standard PostgreSQL URL scheme.
        if self.database_url.startswith(("postgres://", "postgresql://")):
            self.database_url = self.database_url.replace("://", "+psycopg://", 1).replace(
                "postgres+psycopg://", "postgresql+psycopg://", 1
            )
        if os.getenv("VERCEL_PROJECT_PRODUCTION_URL") and self.web_origin == "http://localhost:3000":
            self.web_origin = "https://" + os.environ["VERCEL_PROJECT_PRODUCTION_URL"]
        if self.environment == "production":
            if not self.database_url.startswith("postgresql") or not self.cookie_secure:
                raise ValueError("Production requires PostgreSQL and secure cookies")
            if not self.web_origin.startswith("https://") or self.storage_backend not in (
                "s3",
                "vercel_blob",
            ):
                raise ValueError("Production requires an HTTPS origin and private object storage")
        if self.storage_backend not in ("local", "s3", "vercel_blob"):
            raise ValueError("Unknown storage backend")
        if self.storage_backend == "s3" and not self.s3_bucket:
            raise ValueError("S3_BUCKET is required")
        return self


@lru_cache
def settings() -> Settings:
    return Settings()

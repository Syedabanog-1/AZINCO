"""Typed application settings, read from environment variables (.env in local dev).

Secrets are `SecretStr` so they never appear in reprs, logs or error messages.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_PLACEHOLDER_PREFIX = "change-me"


class Environment(StrEnum):
    LOCAL = "local"
    CI = "ci"
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class Settings(BaseSettings):
    """All runtime configuration for the API process."""

    model_config = SettingsConfigDict(
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
        frozen=True,
    )

    env: Environment = Field(default=Environment.LOCAL, alias="AZINCO_ENV")
    log_level: str = Field(default="INFO", alias="AZINCO_LOG_LEVEL")
    base_currency: str = Field(default="PKR", alias="AZINCO_BASE_CURRENCY", pattern=r"^[A-Z]{3}$")

    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT", ge=1, le=65535)
    postgres_db: str = Field(default="azinco", alias="POSTGRES_DB")
    db_app_user: str = Field(default="azinco_app", alias="AZINCO_DB_APP_USER")
    db_app_password: SecretStr = Field(alias="AZINCO_DB_APP_PASSWORD")

    redis_url: SecretStr = Field(alias="REDIS_URL")

    s3_endpoint: str = Field(alias="S3_ENDPOINT")
    s3_region: str = Field(default="us-east-1", alias="S3_REGION")
    s3_access_key: SecretStr = Field(alias="S3_ACCESS_KEY")
    s3_secret_key: SecretStr = Field(alias="S3_SECRET_KEY")
    s3_bucket_documents: str = Field(default="azinco-documents", alias="S3_BUCKET_DOCUMENTS")

    readiness_timeout_seconds: float = Field(
        default=3.0, alias="AZINCO_READINESS_TIMEOUT_SECONDS", gt=0, le=30
    )

    @field_validator("log_level")
    @classmethod
    def _valid_log_level(cls, value: str) -> str:
        upper = value.upper()
        if upper not in _LOG_LEVELS:
            raise ValueError(f"log level must be one of {sorted(_LOG_LEVELS)}")
        return upper

    @model_validator(mode="after")
    def _no_placeholder_secrets_outside_local(self) -> Settings:
        if self.env in (Environment.LOCAL, Environment.CI):
            return self
        secrets = {
            "AZINCO_DB_APP_PASSWORD": self.db_app_password,
            "REDIS_URL": self.redis_url,
            "S3_ACCESS_KEY": self.s3_access_key,
            "S3_SECRET_KEY": self.s3_secret_key,
        }
        bad = [name for name, s in secrets.items() if _PLACEHOLDER_PREFIX in s.get_secret_value()]
        if bad:
            raise ValueError(f"placeholder secrets not allowed in {self.env}: {', '.join(bad)}")
        return self

    @property
    def docs_enabled(self) -> bool:
        """OpenAPI docs are served everywhere except production."""
        return self.env is not Environment.PROD


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # values come from the environment

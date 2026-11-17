"""Typed application settings, read from environment variables (.env in local dev).

Secrets are `SecretStr` so they never appear in reprs, logs or error messages.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Annotated

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import URL

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
    # Owner decision 2026-11-17: platform reports in PKR and USD. The base currency is the
    # primary one used for ledger base amounts; every other listed currency is a reporting view.
    reporting_currencies: Annotated[tuple[str, ...], NoDecode] = Field(
        default=("PKR", "USD"), alias="AZINCO_REPORTING_CURRENCIES"
    )

    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT", ge=1, le=65535)
    postgres_db: str = Field(default="azinco", alias="POSTGRES_DB")
    db_app_user: str = Field(default="azinco_app", alias="AZINCO_DB_APP_USER")
    db_app_password: SecretStr = Field(alias="AZINCO_DB_APP_PASSWORD")
    # Only the one-shot `migrate` container receives these (Alembic runs as the owner role).
    db_migrator_user: str = Field(default="azinco_migrator", alias="AZINCO_DB_MIGRATOR_USER")
    db_migrator_password: SecretStr | None = Field(
        default=None, alias="AZINCO_DB_MIGRATOR_PASSWORD"
    )

    redis_url: SecretStr = Field(alias="REDIS_URL")

    s3_endpoint: str = Field(alias="S3_ENDPOINT")
    s3_region: str = Field(default="us-east-1", alias="S3_REGION")
    s3_access_key: SecretStr = Field(alias="S3_ACCESS_KEY")
    s3_secret_key: SecretStr = Field(alias="S3_SECRET_KEY")
    s3_bucket_documents: str = Field(default="azinco-documents", alias="S3_BUCKET_DOCUMENTS")

    # ---- authentication (Step 0.7, ADR-0006 option a)
    session_idle_minutes: int = Field(default=60, alias="AZINCO_SESSION_TTL_MINUTES", ge=5, le=720)
    session_absolute_hours: int = Field(
        default=12, alias="AZINCO_SESSION_ABSOLUTE_HOURS", ge=1, le=72
    )
    login_max_failures: int = Field(default=5, alias="AZINCO_LOGIN_MAX_FAILURES", ge=3, le=20)
    login_lockout_minutes: int = Field(default=15, alias="AZINCO_LOGIN_LOCKOUT_MINUTES", ge=1)
    mfa_encryption_key: SecretStr | None = Field(default=None, alias="AZINCO_MFA_ENCRYPTION_KEY")
    mfa_issuer: str = Field(default="AZINCO", alias="AZINCO_MFA_ISSUER")
    public_web_url: str = Field(default="http://localhost:3000", alias="AZINCO_PUBLIC_WEB_URL")
    mail_mode: str = Field(default="smtp", alias="AZINCO_MAIL_MODE", pattern="^(smtp|capture)$")
    smtp_host: str = Field(default="localhost", alias="SMTP_HOST")
    smtp_port: int = Field(default=1025, alias="SMTP_PORT")
    mail_from: str = Field(default="AZINCO <no-reply@azinco.local>", alias="AZINCO_MAIL_FROM")

    readiness_timeout_seconds: float = Field(
        default=5.0, alias="AZINCO_READINESS_TIMEOUT_SECONDS", gt=0, le=30
    )

    @field_validator("log_level")
    @classmethod
    def _valid_log_level(cls, value: str) -> str:
        upper = value.upper()
        if upper not in _LOG_LEVELS:
            raise ValueError(f"log level must be one of {sorted(_LOG_LEVELS)}")
        return upper

    @field_validator("reporting_currencies", mode="before")
    @classmethod
    def _split_currencies(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(part.strip().upper() for part in value.split(",") if part.strip())
        return value

    @field_validator("reporting_currencies")
    @classmethod
    def _valid_currencies(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("at least one reporting currency is required")
        bad = [c for c in value if len(c) != 3 or not c.isalpha() or not c.isupper()]
        if bad:
            raise ValueError(f"invalid ISO 4217 codes: {bad}")
        if len(set(value)) != len(value):
            raise ValueError("duplicate reporting currencies")
        return value

    @model_validator(mode="after")
    def _base_is_reported(self) -> Settings:
        if self.base_currency not in self.reporting_currencies:
            raise ValueError("AZINCO_BASE_CURRENCY must be one of AZINCO_REPORTING_CURRENCIES")
        return self

    @model_validator(mode="after")
    def _no_placeholder_secrets_outside_local(self) -> Settings:
        if self.env in (Environment.LOCAL, Environment.CI):
            return self
        if self.mfa_encryption_key is None:
            raise ValueError(f"AZINCO_MFA_ENCRYPTION_KEY is required in {self.env}")
        if self.mail_mode == "capture":
            raise ValueError(
                f"AZINCO_MAIL_MODE=capture is a test-only [MOCK] mode, not for {self.env}"
            )
        secrets = {
            "AZINCO_MFA_ENCRYPTION_KEY": self.mfa_encryption_key,
            "AZINCO_DB_APP_PASSWORD": self.db_app_password,
            "REDIS_URL": self.redis_url,
            "S3_ACCESS_KEY": self.s3_access_key,
            "S3_SECRET_KEY": self.s3_secret_key,
        }
        bad = [name for name, s in secrets.items() if _PLACEHOLDER_PREFIX in s.get_secret_value()]
        if bad:
            raise ValueError(f"placeholder secrets not allowed in {self.env}: {', '.join(bad)}")
        return self

    def database_url(self, *, migrator: bool = False) -> URL:
        """SQLAlchemy URL for the app role (default) or the migration owner role."""
        if migrator:
            if self.db_migrator_password is None:
                raise ValueError("AZINCO_DB_MIGRATOR_PASSWORD is required for migrations")
            user, password = self.db_migrator_user, self.db_migrator_password
        else:
            user, password = self.db_app_user, self.db_app_password
        return URL.create(
            "postgresql+asyncpg",
            username=user,
            password=password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )

    @property
    def cookie_secure(self) -> bool:
        """Secure cookies everywhere except plain-http local development and CI."""
        return self.env not in (Environment.LOCAL, Environment.CI)

    @property
    def docs_enabled(self) -> bool:
        """OpenAPI docs are served everywhere except production."""
        return self.env is not Environment.PROD


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # values come from the environment

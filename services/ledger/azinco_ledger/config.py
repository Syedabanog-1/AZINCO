"""Settings for the Ledger Service. Secrets come only from the environment (.env / secret store)."""

from __future__ import annotations

import enum
from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_TOKEN_LENGTH = 32


class Environment(enum.StrEnum):
    LOCAL = "local"
    CI = "ci"
    STAGING = "staging"
    PRODUCTION = "production"


class LedgerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", frozen=True)

    env: Environment = Field(Environment.LOCAL, alias="AZINCO_ENV")
    postgres_host: str = Field("postgres", alias="POSTGRES_HOST")
    postgres_port: int = Field(5432, alias="POSTGRES_PORT")
    postgres_db: str = Field("azinco", alias="POSTGRES_DB")
    db_user: str = Field("azinco_ledger", alias="AZINCO_DB_LEDGER_USER")
    db_password: SecretStr = Field(alias="AZINCO_DB_LEDGER_PASSWORD")
    pool_min: int = Field(1, ge=1, le=50, alias="AZINCO_LEDGER_POOL_MIN")
    pool_max: int = Field(10, ge=1, le=100, alias="AZINCO_LEDGER_POOL_MAX")
    # Caller tokens [Recommended, ADR-0016]: the API may do everything a human approval allows;
    # the worker (agents' tools) may only create drafts and read - never post (blueprint AP-2).
    api_token: SecretStr = Field(alias="AZINCO_LEDGER_API_TOKEN")
    worker_token: SecretStr | None = Field(None, alias="AZINCO_LEDGER_WORKER_TOKEN")

    @model_validator(mode="after")
    def _tokens_are_strong_and_distinct(self) -> LedgerSettings:
        tokens = [self.api_token] + ([self.worker_token] if self.worker_token else [])
        for token in tokens:
            if len(token.get_secret_value()) < MIN_TOKEN_LENGTH:
                raise ValueError(f"ledger service tokens need at least {MIN_TOKEN_LENGTH} chars")
        if self.worker_token and (
            self.worker_token.get_secret_value() == self.api_token.get_secret_value()
        ):
            raise ValueError("worker and API tokens must differ")
        return self


@lru_cache
def get_settings() -> LedgerSettings:
    return LedgerSettings()  # values come from the environment

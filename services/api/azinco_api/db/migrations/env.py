"""Alembic environment. Migrations always run as the owner role `azinco_migrator`."""

from __future__ import annotations

import asyncio

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from azinco_api.core.config import Settings
from azinco_api.db.models import SCHEMA, Base

target_metadata = Base.metadata
VERSION_TABLE_SCHEMA = "public"  # alembic_version lives outside the app schema


def _include_name(name: str | None, type_: str, parent_names: object) -> bool:
    # Only compare objects in our schema during `alembic check` / autogenerate.
    if type_ == "schema":
        return name == SCHEMA
    return True


def _configure(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        include_name=_include_name,
        version_table_schema=VERSION_TABLE_SCHEMA,
        compare_type=True,
        compare_server_default=False,
    )


def _run_sync(connection: Connection) -> None:
    _configure(connection)
    with context.begin_transaction():
        context.run_migrations()


async def _run_async() -> None:
    settings = Settings()
    engine = create_async_engine(settings.database_url(migrator=True), poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(_run_sync)
    await engine.dispose()


if context.is_offline_mode():
    raise SystemExit("Offline SQL generation is not supported; run against a database.")
asyncio.run(_run_async())

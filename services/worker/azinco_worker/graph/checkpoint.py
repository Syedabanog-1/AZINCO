"""Postgres checkpointer for LangGraph, confined to schema `agent_state` (migration 0006, ADR-0002).

Connects as `azinco_worker`, whose only write rights are in `agent_state`. `setup()` creates or
upgrades the library's own checkpoint tables there; it is idempotent.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.conninfo import make_conninfo

SCHEMA = "agent_state"


def worker_conninfo(env: dict[str, str] | None = None) -> str:
    e = dict(os.environ) if env is None else env
    return make_conninfo(
        host=e.get("POSTGRES_HOST", "postgres"),
        port=e.get("POSTGRES_PORT", "5432"),
        dbname=e.get("POSTGRES_DB", "azinco"),
        user=e.get("AZINCO_DB_WORKER_USER", "azinco_worker"),
        password=e["AZINCO_DB_WORKER_PASSWORD"],
        options=f"-c search_path={SCHEMA}",
        application_name="azinco-worker",
    )


@contextmanager
def postgres_checkpointer(conninfo: str | None = None) -> Iterator[PostgresSaver]:
    with PostgresSaver.from_conn_string(conninfo or worker_conninfo()) as saver:
        saver.setup()
        yield saver

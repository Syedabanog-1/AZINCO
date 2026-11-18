"""Schema `agent_state` for LangGraph checkpoints (Step 0.10b, ADR-0002).

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-18

The LangGraph Postgres checkpointer manages its own tables (and their upgrades) with `setup()`.
They live in their own schema so the worker role can create them there and nowhere else:
`azinco_worker` gets USAGE + CREATE on `agent_state` only - no write access to `app`, `ledger`
or `audit` is added here. Checkpoints hold graph state (ids, proposals, decisions), never
credentials; thread ids are prefixed with the tenant id ([Recommended], ADR-0002).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA agent_state")
    op.execute("REVOKE ALL ON SCHEMA agent_state FROM PUBLIC")
    op.execute("GRANT USAGE, CREATE ON SCHEMA agent_state TO azinco_worker")
    op.execute("GRANT USAGE ON SCHEMA agent_state TO azinco_readonly")


def downgrade() -> None:
    op.execute("DROP SCHEMA agent_state CASCADE")

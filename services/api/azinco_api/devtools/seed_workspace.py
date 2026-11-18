"""[MOCK] Create a synthetic test workspace (tenant) for an existing, verified user.

Real client onboarding (KYC/AML, business profile, engagement letter, advance payment) is a
Phase 1 deliverable (Base Standard §4, §15). Until then this developer tool lets you see a
workspace in the UI. It:

* refuses to run unless AZINCO_ENV is ``local`` or ``ci``;
* goes through the same RLS rules as the API (runtime role ``azinco_app``, context first);
* marks the workspace name with ``[MOCK]`` and writes a ``tenant.created`` audit event with
  ``{"mock": true}`` so it can never be mistaken for a real, onboarded client.

Usage (inside the api container):
    python -m azinco_api.devtools.seed_workspace --email you@example.com \
        --name "Demo Traders" --jurisdiction PK --role client_owner
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from azinco_api.audit.writer import ActorType, record
from azinco_api.core.config import Environment, Settings, get_settings
from azinco_api.db.session import create_engine, create_session_factory
from azinco_api.db.tenancy import tenant_session

ALLOWED_ENVS = {Environment.LOCAL, Environment.CI}
# Jurisdictions named in the project scope (PK + initial international markets).
JURISDICTIONS = ("PK", "GB", "US", "CA", "AU")
CLIENT_ROLES = ("client_owner", "client_staff")
MOCK_TAG = "[MOCK]"


class SeedError(RuntimeError):
    """A user-facing problem (wrong environment, unknown or unverified user)."""


def mock_name(name: str) -> str:
    name = " ".join(name.split())
    if not name:
        raise SeedError("Workspace name must not be empty.")
    return name if name.startswith(MOCK_TAG) else f"{MOCK_TAG} {name}"


async def seed_workspace(
    factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    *,
    email: str,
    name: str,
    jurisdiction: str = "PK",
    role: str = "client_owner",
) -> uuid.UUID:
    if settings.env not in ALLOWED_ENVS:
        raise SeedError(f"Refusing to run in AZINCO_ENV={settings.env.value}: local/ci only.")
    if jurisdiction not in JURISDICTIONS:
        raise SeedError(f"Jurisdiction must be one of {', '.join(JURISDICTIONS)}.")
    if role not in CLIENT_ROLES:
        raise SeedError(f"Role must be one of {', '.join(CLIENT_ROLES)}.")
    display = mock_name(name)

    async with tenant_session(factory, None) as s:
        user = (
            (await s.execute(text("SELECT id, status FROM app.auth_find_user(:e)"), {"e": email}))
            .mappings()
            .first()
        )
    if user is None:
        raise SeedError("No account with that e-mail. Register first at /register.")
    if user["status"] != "active":
        raise SeedError("Verify the e-mail first (link in Mailpit, http://localhost:8025).")
    user_id: uuid.UUID = user["id"]

    tenant_id = uuid.uuid4()
    # Context first: RLS only lets us insert the tenant whose id is in the session context.
    async with tenant_session(factory, tenant_id, user_id) as s:
        await s.execute(
            text(
                "INSERT INTO app.tenants (id, name, home_jurisdiction) "
                "VALUES (:id, :name, :jurisdiction)"
            ),
            {"id": tenant_id, "name": display, "jurisdiction": jurisdiction},
        )
        await s.execute(
            text(
                "INSERT INTO app.tenant_memberships (tenant_id, user_id, role) "
                "VALUES (:t, :u, CAST(:role AS app.tenant_role))"
            ),
            {"t": tenant_id, "u": user_id, "role": role},
        )
        await record(
            s,
            "tenant.created",
            actor_type=ActorType.SYSTEM,
            actor_id=user_id,
            tenant_id=tenant_id,
            resource_type="tenant",
            resource_id=str(tenant_id),
            details={"mock": True, "jurisdiction": jurisdiction, "member_role": role},
        )
    return tenant_id


def _parse(argv: Sequence[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    p.add_argument("--email", required=True)
    p.add_argument("--name", default="Demo Traders")
    p.add_argument("--jurisdiction", default="PK", choices=JURISDICTIONS)
    p.add_argument("--role", default="client_owner", choices=CLIENT_ROLES)
    return p.parse_args(argv)


async def _main(argv: Sequence[str]) -> int:
    args = _parse(argv)
    settings = get_settings()
    engine = create_engine(settings)
    try:
        tenant_id = await seed_workspace(
            create_session_factory(engine),
            settings,
            email=args.email,
            name=args.name,
            jurisdiction=args.jurisdiction,
            role=args.role,
        )
    except SeedError as exc:
        print(f"NOT CREATED: {exc}", file=sys.stderr)
        return 2
    finally:
        await engine.dispose()
    print(f"CREATED {MOCK_TAG} workspace {tenant_id} ({args.role}). Refresh /account.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main(sys.argv[1:])))

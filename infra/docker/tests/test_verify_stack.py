"""Unit tests for infra/docker/verify_stack.py (no Docker required)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

MODULE_PATH = Path(__file__).resolve().parents[1] / "verify_stack.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("verify_stack", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


vs = _load()


def test_parse_env_file_handles_comments_quotes_and_inline_comments() -> None:
    text = '# comment\n\nA=1\nB="quoted value"\nC=value   # inline comment\nD=\nnot a pair\n'
    assert vs.parse_env_file(text) == {"A": "1", "B": "quoted value", "C": "value", "D": ""}


def test_env_example_parses_and_contains_required_keys() -> None:
    example = (MODULE_PATH.parents[2] / ".env.example").read_text(encoding="utf-8")
    env = vs.parse_env_file(example)
    for key in (
        "POSTGRES_SUPERUSER",
        "POSTGRES_SUPERUSER_PASSWORD",
        "AZINCO_DB_APP_PASSWORD",
        "AZINCO_DB_READONLY_PASSWORD",
        "REDIS_PASSWORD",
        "S3_ACCESS_KEY",
        "S3_SECRET_KEY",
    ):
        assert env.get(key), key
    assert env["AZINCO_BASE_CURRENCY"] == "PKR"
    assert env["AZINCO_PAYMENTS_MODE"] == "mock"
    assert env["AZINCO_FUNDS_HANDLING_DEFAULT"] == "ledger"


def test_parse_compose_ps_accepts_array_and_ndjson() -> None:
    assert vs.parse_compose_ps('[{"Service":"a"},{"Service":"b"}]') == [
        {"Service": "a"},
        {"Service": "b"},
    ]
    assert vs.parse_compose_ps('{"Service":"a"}\n{"Service":"b"}\n') == [
        {"Service": "a"},
        {"Service": "b"},
    ]
    assert vs.parse_compose_ps("") == []


def test_non_local_bindings_flags_public_ports() -> None:
    rows = [
        {"Service": "postgres", "Publishers": [{"URL": "127.0.0.1", "PublishedPort": 5432}]},
        {"Service": "redis", "Publishers": [{"URL": "0.0.0.0", "PublishedPort": 6379}]},  # noqa: S104
        {"Service": "storage-init", "Publishers": [{"URL": "", "PublishedPort": 0}]},
    ]
    assert vs.non_local_bindings(rows) == ["redis:6379 on 0.0.0.0"]


def test_eicar_is_not_stored_literally_in_source() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert vs.eicar_bytes().decode() not in source
    assert vs.eicar_bytes().startswith(b"X5O!P%@AP")


def test_check_postgres_with_fake_runner_all_good() -> None:
    def runner(sql: str, user: str | None = None, password: str | None = None) -> tuple[int, str]:
        if "pg_extension" in sql:
            return 0, "citext\npgcrypto\nplpgsql\nvector"
        if "pg_roles" in sql:
            return 0, "\n".join(f"{r}|f|f" for r in vs.EXPECTED_ROLES)
        if "datdba" in sql:
            return 0, "azinco_migrator"
        if "alembic_version" in sql:
            return 0, "0001"
        if "pg_tables" in sql:
            return 0, "8"
        if "relforcerowsecurity" in sql:
            return 0, "5" if "'ledger'" in sql else "8"
        if "FROM app.tenants" in sql:
            return 0, "0"
        if sql.startswith("CREATE TABLE"):
            return 1, "ERROR:  permission denied for schema public"
        if "read_only" in sql:
            return 0, "on"
        if "verify_chain" in sql:
            return 0, "0|3"
        if sql.startswith("DELETE FROM audit"):
            return 1, "ERROR:  permission denied for table audit_events"
        if sql.startswith("INSERT INTO ledger.journals"):
            return 1, "ERROR:  permission denied for table journals"
        raise AssertionError(sql)

    env = {"AZINCO_DB_APP_PASSWORD": "x", "AZINCO_DB_READONLY_PASSWORD": "y"}
    results = vs.check_postgres(runner, env)
    assert all(r.ok for r in results), [(r.name, r.detail) for r in results]


def test_check_postgres_detects_bypassrls_and_writable_public() -> None:
    def runner(sql: str, user: str | None = None, password: str | None = None) -> tuple[int, str]:
        if "pg_extension" in sql:
            return 0, "citext\npgcrypto\nvector"
        if "pg_roles" in sql:
            rows = [f"{r}|f|{'t' if r == 'azinco_app' else 'f'}" for r in vs.EXPECTED_ROLES]
            return 0, "\n".join(rows)
        if "datdba" in sql:
            return 0, "postgres"
        if "alembic_version" in sql:
            return 1, 'ERROR:  relation "public.alembic_version" does not exist'
        if "pg_tables" in sql:
            return 0, "0"
        if "relforcerowsecurity" in sql:
            return 0, "0"
        if "FROM app.tenants" in sql:
            return 0, "3"
        if sql.startswith("CREATE TABLE"):
            return 0, "CREATE TABLE"
        if "verify_chain" in sql:
            return 0, "1|3"
        if sql.startswith("DELETE FROM audit"):
            return 0, "DELETE 0"
        if sql.startswith("INSERT INTO ledger.journals"):
            return 0, "INSERT 0 1"
        return 0, "off"

    env = {"AZINCO_DB_APP_PASSWORD": "x", "AZINCO_DB_READONLY_PASSWORD": "y"}
    failed = {r.name for r in vs.check_postgres(runner, env) if not r.ok}
    assert failed == {
        "migrations applied (alembic)",
        "app schema tables owned by migrator",
        "RLS enabled + forced on app tables",
        "app role without tenant context sees 0 rows",
        "no superuser / BYPASSRLS roles",
        "database owned by azinco_migrator",
        "app role cannot create in public",
        "readonly role is read-only",
        "audit hash chains verify",
        "app role cannot delete audit events",
        "RLS enabled + forced on ledger tables",
        "ledger hash chains verify",
        "only the ledger role writes journals",
    }


def test_get_until_retries_slow_then_succeeds() -> None:
    calls: list[str] = []
    waits: list[float] = []

    def get(port: int, path: str) -> tuple[int, str]:
        calls.append(path)
        if len(calls) < 3:
            raise TimeoutError("timed out")
        return 200, "ok"

    ok, status, _ = vs._get_until(8000, "/ready", lambda st, _b: st == 200, get, waits.append)
    assert ok and status == 200 and len(calls) == 3
    assert waits == [vs.HTTP_RETRY_WAIT_S, vs.HTTP_RETRY_WAIT_S]


def test_get_until_gives_up_and_reports_last_answer() -> None:
    def get(port: int, path: str) -> tuple[int, str]:
        return 503, '{"status":"not_ready"}'

    ok, status, body = vs._get_until(8000, "/ready", lambda st, _b: st == 200, get, lambda _s: None)
    assert not ok and status == 503 and "not_ready" in body


def test_describe_readiness_names_failing_dependency() -> None:
    body = (
        '{"status":"not_ready","components":['
        '{"name":"postgres","status":"ok","latency_ms":3.2,"detail":null},'
        '{"name":"storage","status":"fail","latency_ms":5001,"detail":"TimeoutError"}]}'
    )
    assert vs.describe_readiness(body) == ("postgres=ok 3ms, storage=fail 5001ms (TimeoutError)")
    assert vs.describe_readiness("not json") == "not json"

"""AZINCO Step 0.2 — verify the local Docker stack.

Run from the repository root after `docker compose ... up -d`:
    python infra/docker/verify_stack.py

Checks:
  1. Containers running / healthy; storage-init finished successfully.
  2. Every published port binds to 127.0.0.1 only.
  3. PostgreSQL: pgvector, pgcrypto, citext installed; 6 azinco roles exist,
     none is superuser or has BYPASSRLS; app role cannot create objects in "public";
     readonly role is read-only.
  4. Redis rejects unauthenticated clients and accepts the configured password.
  5. Object storage buckets exist.
  6. ClamAV detects the EICAR test signature.
  7. Mailpit UI responds.

Standard library only. Secrets are read from .env and never printed.
"""

from __future__ import annotations

import http.client
import json
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "infra" / "docker" / "compose.yml"
ENV_FILE = REPO_ROOT / ".env"

EXPECTED_ROLES = (
    "azinco_app",
    "azinco_audit",
    "azinco_ledger",
    "azinco_migrator",
    "azinco_readonly",
    "azinco_worker",
)
REQUIRED_EXTENSIONS = ("citext", "pgcrypto", "vector")
HEALTHY_SERVICES = ("postgres", "redis", "mailpit", "api", "web", "ledger")


# --------------------------------------------------------------------------- helpers
def parse_env_file(text: str) -> dict[str, str]:
    """Minimal .env parser: KEY=VALUE, ignores comments and blank lines, strips inline comments."""
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if value and value[0] in "\"'" and value[-1:] == value[0]:
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        values[key.strip()] = value
    return values


def non_local_bindings(ps_rows: Sequence[dict[str, object]]) -> list[str]:
    """Return 'service:port' entries published on an address other than 127.0.0.1."""
    bad: list[str] = []
    for row in ps_rows:
        publishers = row.get("Publishers") or []
        if not isinstance(publishers, list):
            continue
        for pub in publishers:
            if not isinstance(pub, dict):
                continue
            published = pub.get("PublishedPort") or 0
            url = str(pub.get("URL") or "")
            if published and url not in ("127.0.0.1", "localhost"):
                bad.append(f"{row.get('Service')}:{published} on {url or 'all interfaces'}")
    return bad


def published_ports(ps_rows: Sequence[dict[str, object]], service: str) -> list[str]:
    """Host ports a service publishes (the Ledger Service must publish none)."""
    found: list[str] = []
    for row in ps_rows:
        if row.get("Service") != service:
            continue
        publishers = row.get("Publishers") or []
        if isinstance(publishers, list):
            for pub in publishers:
                if isinstance(pub, dict) and pub.get("PublishedPort"):
                    found.append(f"{pub.get('URL', '')}:{pub.get('PublishedPort')}")
    return found


def parse_compose_ps(output: str) -> list[dict[str, object]]:
    """`docker compose ps --format json` prints either a JSON array or one object per line."""
    output = output.strip()
    if not output:
        return []
    if output.startswith("["):
        data = json.loads(output)
        return [d for d in data if isinstance(d, dict)]
    return [json.loads(line) for line in output.splitlines() if line.strip()]


def eicar_bytes() -> bytes:
    # Built from fragments so this source file itself is never flagged by antivirus tools.
    parts = ["X5O!P%@AP[4\\PZX54(P^)7CC)7}$", "EICAR-STANDARD-", "ANTIVIRUS-TEST-FILE!$H+H*"]
    return "".join(parts).encode("ascii")


@dataclass
class Result:
    name: str
    ok: bool
    detail: str = ""


class Stack:
    def __init__(self, env: dict[str, str]) -> None:
        self.env = env

    def compose(self, *args: str, stdin: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
        cmd = [
            "docker",
            "compose",
            "--env-file",
            str(ENV_FILE),
            "-f",
            str(COMPOSE_FILE),
            *args,
        ]
        return subprocess.run(cmd, input=stdin, capture_output=True, check=False)  # noqa: S603

    def psql(
        self, sql: str, user: str | None = None, password: str | None = None
    ) -> tuple[int, str]:
        db = self.env.get("POSTGRES_DB", "azinco")
        if user is None:
            user = self.env["POSTGRES_SUPERUSER"]
            password = self.env["POSTGRES_SUPERUSER_PASSWORD"]
        proc = self.compose(
            "exec",
            "-T",
            "-e",
            f"PGPASSWORD={password}",
            "postgres",
            "psql",
            "-h",
            "127.0.0.1",
            "-U",
            user,
            "-d",
            db,
            "-At",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            sql,
        )
        text = (proc.stdout + proc.stderr).decode(errors="replace").strip()
        return proc.returncode, text


# --------------------------------------------------------------------------- checks
def check_containers(stack: Stack) -> list[Result]:
    proc = stack.compose("ps", "--all", "--format", "json")
    rows = parse_compose_ps(proc.stdout.decode())
    by_service = {str(r.get("Service")): r for r in rows}
    results: list[Result] = []
    for svc in HEALTHY_SERVICES:
        row = by_service.get(svc)
        health = str(row.get("Health", "")) if row else "missing"
        results.append(Result(f"{svc} healthy", health == "healthy", health))
    storage = by_service.get("storage")
    results.append(
        Result(
            "storage running",
            bool(storage and storage.get("State") == "running"),
            str(storage.get("State") if storage else "missing"),
        )
    )
    init = by_service.get("storage-init")
    init_ok = bool(
        init and init.get("State") == "exited" and int(str(init.get("ExitCode", 1))) == 0
    )
    results.append(
        Result(
            "storage-init completed",
            init_ok,
            f"state={init.get('State')} exit={init.get('ExitCode')}" if init else "missing",
        )
    )
    clam = by_service.get("clamav")
    clam_health = str(clam.get("Health", "")) if clam else "missing"
    results.append(
        Result(
            "clamav healthy",
            clam_health == "healthy",
            clam_health
            + (
                " (first start downloads signatures; wait and re-run)"
                if clam_health == "starting"
                else ""
            ),
        )
    )
    bad = non_local_bindings(rows)
    results.append(Result("ports bound to 127.0.0.1 only", not bad, ", ".join(bad) or "ok"))
    exposed = published_ports(rows, "ledger")
    results.append(
        Result(
            "ledger not reachable from host",
            "ledger" in by_service and not exposed,
            ", ".join(exposed) or ("internal only" if "ledger" in by_service else "missing"),
        )
    )
    return results


# Runs inside the ledger container: status of an unauthenticated call and of /ready.
_LEDGER_PROBE = (
    "import urllib.request as u, urllib.error as e\n"
    "def st(path):\n"
    "    try:\n"
    "        return u.urlopen('http://127.0.0.1:8100' + path, timeout=10).status\n"
    "    except e.HTTPError as x:\n"
    "        return x.code\n"
    "print(st('/internal/ledger/verify'), st('/ready'))\n"
)


def check_ledger(stack: Stack) -> list[Result]:
    proc = stack.compose("exec", "-T", "ledger", "python", "-c", _LEDGER_PROBE)
    out = (proc.stdout + proc.stderr).decode(errors="replace").strip()
    parts = out.split()
    unauth, ready = (parts[0], parts[1]) if proc.returncode == 0 and len(parts) == 2 else ("", "")
    return [
        Result("ledger refuses calls without service token", unauth == "401", unauth or out[:80]),
        Result("ledger /ready (role not privileged)", ready == "200", ready or out[:80]),
    ]


APP_TABLES = 8  # tenants, users, memberships, platform_roles, sessions, tokens, entities, approvals
LEDGER_TABLES = 5  # accounts, periods, journals, journal_lines, consumed_approvals


def check_postgres(run_sql: Callable[..., tuple[int, str]], env: dict[str, str]) -> list[Result]:
    results: list[Result] = []
    code, out = run_sql("SELECT extname FROM pg_extension ORDER BY 1")
    exts = set(out.split()) if code == 0 else set()
    missing = [e for e in REQUIRED_EXTENSIONS if e not in exts]
    results.append(
        Result(
            "extensions installed",
            not missing,
            "missing: " + ", ".join(missing) if missing else "ok",
        )
    )

    code, out = run_sql(
        "SELECT rolname, rolsuper, rolbypassrls FROM pg_roles "
        "WHERE rolname LIKE 'azinco\\_%' ORDER BY 1"
    )
    rows = [line.split("|") for line in out.splitlines() if line] if code == 0 else []
    names = tuple(r[0] for r in rows)
    results.append(Result("6 azinco roles exist", names == EXPECTED_ROLES, ", ".join(names) or out))
    privileged = [r[0] for r in rows if r[1] == "t" or r[2] == "t"]
    results.append(
        Result("no superuser / BYPASSRLS roles", not privileged, ", ".join(privileged) or "ok")
    )

    code, out = run_sql(
        "SELECT pg_catalog.pg_get_userbyid(datdba) FROM pg_database "
        "WHERE datname = current_database()"
    )
    results.append(
        Result("database owned by azinco_migrator", out.strip() == "azinco_migrator", out.strip())
    )

    code, out = run_sql("SELECT version_num FROM public.alembic_version")
    results.append(
        Result("migrations applied (alembic)", code == 0 and out.strip() != "", out.strip() or out)
    )
    code, out = run_sql(
        "SELECT count(*) FROM pg_tables WHERE schemaname = 'app' AND tableowner = 'azinco_migrator'"
    )
    results.append(
        Result(
            "app schema tables owned by migrator",
            out.strip() == str(APP_TABLES),
            out.strip(),
        )
    )
    code, out = run_sql(
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'app' AND c.relkind = 'r' "
        "AND c.relrowsecurity AND c.relforcerowsecurity"
    )
    results.append(
        Result(
            "RLS enabled + forced on app tables",
            out.strip() == str(APP_TABLES),
            out.strip() or out,
        )
    )
    code, out = run_sql(
        "SELECT count(*) FROM app.tenants",
        "azinco_app",
        env["AZINCO_DB_APP_PASSWORD"],
    )
    results.append(
        Result(
            "app role without tenant context sees 0 rows",
            code == 0 and out.strip() == "0",
            out.strip() or out,
        )
    )

    code, out = run_sql(
        "CREATE TABLE public.azinco_probe(i int)", "azinco_app", env["AZINCO_DB_APP_PASSWORD"]
    )
    results.append(
        Result(
            "app role cannot create in public",
            code != 0 and "permission denied" in out,
            "blocked" if code != 0 else "UNEXPECTEDLY ALLOWED",
        )
    )

    code, out = run_sql(
        "SHOW default_transaction_read_only", "azinco_readonly", env["AZINCO_DB_READONLY_PASSWORD"]
    )
    results.append(Result("readonly role is read-only", out.strip() == "on", out.strip()))

    # Step 0.8 — audit log (ADR-0012)
    code, out = run_sql(
        "SELECT count(*) FILTER (WHERE NOT v.ok), count(*) FROM "
        "(SELECT DISTINCT tenant_id FROM audit.audit_events) s, "
        "LATERAL audit.verify_chain(s.tenant_id) v"
    )
    parts = out.strip().split("|") if code == 0 else []
    results.append(
        Result(
            "audit hash chains verify",
            len(parts) == 2 and parts[0] == "0",
            f"{parts[1]} stream(s), {parts[0]} broken" if len(parts) == 2 else out,
        )
    )
    code, out = run_sql(
        "DELETE FROM audit.audit_events", "azinco_app", env["AZINCO_DB_APP_PASSWORD"]
    )
    results.append(
        Result(
            "app role cannot delete audit events",
            code != 0 and "permission denied" in out,
            "blocked" if code != 0 else "UNEXPECTEDLY ALLOWED",
        )
    )

    # Step 0.9 — ledger invariants (migration 0005, ADR-0015)
    code, out = run_sql(
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'ledger' AND c.relkind = 'r' "
        "AND c.relrowsecurity AND c.relforcerowsecurity"
    )
    results.append(
        Result(
            "RLS enabled + forced on ledger tables",
            out.strip() == str(LEDGER_TABLES),
            out.strip() or out,
        )
    )
    code, out = run_sql(
        "SELECT count(*) FILTER (WHERE NOT v.ok), count(*) FROM "
        "(SELECT DISTINCT tenant_id FROM ledger.journals WHERE ledger_seq IS NOT NULL) s, "
        "LATERAL ledger.verify_chain(s.tenant_id) v"
    )
    parts = out.strip().split("|") if code == 0 else []
    results.append(
        Result(
            "ledger hash chains verify",
            len(parts) == 2 and parts[0] == "0",
            f"{parts[1]} ledger(s), {parts[0]} broken" if len(parts) == 2 else out,
        )
    )
    code, out = run_sql(
        "INSERT INTO ledger.journals (tenant_id, entity_id, journal_date, description, source) "
        "VALUES (gen_random_uuid(), gen_random_uuid(), current_date, 'probe', 'manual')",
        "azinco_app",
        env["AZINCO_DB_APP_PASSWORD"],
    )
    results.append(
        Result(
            "only the ledger role writes journals",
            code != 0 and "permission denied" in out,
            "app role blocked" if code != 0 else "UNEXPECTEDLY ALLOWED",
        )
    )
    return results


def check_redis(stack: Stack) -> list[Result]:
    anon = stack.compose("exec", "-T", "-e", "REDISCLI_AUTH=", "redis", "redis-cli", "ping")
    anon_out = (anon.stdout + anon.stderr).decode(errors="replace")
    auth = stack.compose("exec", "-T", "redis", "redis-cli", "ping")
    auth_out = auth.stdout.decode(errors="replace").strip()
    return [
        Result("redis rejects anonymous clients", "NOAUTH" in anon_out, anon_out.strip()[:60]),
        Result("redis accepts password", auth_out == "PONG", auth_out[:60]),
    ]


def check_storage(stack: Stack) -> list[Result]:
    proc = stack.compose(
        "run",
        "--rm",
        "--no-deps",
        "--entrypoint",
        "aws",
        "storage-init",
        "--endpoint-url",
        "http://storage:9000",
        "s3api",
        "list-buckets",
        "--query",
        "Buckets[].Name",
        "--output",
        "text",
    )
    names = set(proc.stdout.decode(errors="replace").split())
    wanted = {
        stack.env.get("S3_BUCKET_DOCUMENTS", "azinco-documents"),
        stack.env.get("S3_BUCKET_ARCHIVE", "azinco-archive"),
    }
    missing = wanted - names
    return [
        Result(
            "storage buckets exist",
            proc.returncode == 0 and not missing,
            "missing: " + ", ".join(sorted(missing)) if missing else "ok",
        )
    ]


def check_clamav(stack: Stack) -> list[Result]:
    proc = stack.compose(
        "exec", "-T", "clamav", "clamdscan", "--no-summary", "-", stdin=eicar_bytes()
    )
    out = (proc.stdout + proc.stderr).decode(errors="replace").strip()
    return [Result("clamav detects EICAR test file", "FOUND" in out, out[:80])]


HTTP_TIMEOUT_S = 30  # longer than the API's own readiness timeout, so we see its real answer
HTTP_ATTEMPTS = 3
HTTP_RETRY_WAIT_S = 5


def _http_get(port: int, path: str) -> tuple[int, str]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=HTTP_TIMEOUT_S)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        return resp.status, resp.read().decode(errors="replace")
    finally:
        conn.close()


def _get_until(
    port: int,
    path: str,
    ok: Callable[[int, str], bool],
    get: Callable[[int, str], tuple[int, str]] = _http_get,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[bool, int, str]:
    """GET with retries: right after a build the machine is busy and first requests are slow."""
    status, body = 0, ""
    for attempt in range(1, HTTP_ATTEMPTS + 1):
        try:
            status, body = get(port, path)
        except OSError as exc:
            status, body = 0, str(exc) or type(exc).__name__
        if ok(status, body):
            return True, status, body
        if attempt < HTTP_ATTEMPTS:
            sleep(HTTP_RETRY_WAIT_S)
    return False, status, body


def describe_readiness(body: str) -> str:
    """Name the failing dependencies (and their latency) from a /ready body."""
    try:
        data = json.loads(body)
        parts = [
            f"{c['name']}={c['status']} {c['latency_ms']:.0f}ms"
            + (f" ({c['detail']})" if c.get("detail") else "")
            for c in data["components"]
        ]
    except (ValueError, KeyError, TypeError):
        return body[:120]
    return ", ".join(parts)


def check_mailpit(env: dict[str, str]) -> list[Result]:
    ok, status, body = _get_until(
        int(env.get("MAILPIT_UI_PORT", "8025")), "/livez", lambda st, _b: st == 200
    )
    return [Result("mailpit UI responds", ok, str(status) if status else body)]


def check_api(env: dict[str, str]) -> list[Result]:
    port = int(env.get("API_PORT", "8000"))
    ok, status, body = _get_until(port, "/health", lambda st, _b: st == 200)
    results = [Result("api /health 200", ok, f"{status} {body[:120]}")]
    ok, status, body = _get_until(port, "/ready", lambda st, _b: st == 200)
    detail = f"{status} {describe_readiness(body)}" if status else body
    results.append(Result("api /ready 200 (db, redis, storage)", ok, detail))
    return results


def check_web(env: dict[str, str]) -> list[Result]:
    port = int(env.get("WEB_PORT", "3000"))
    results: list[Result] = []
    for path, name, needle in (
        ("/", "web home page renders", "Experts approve."),
        ("/status", "web status page: all systems operational", "All systems operational"),
        ("/login", "web sign-in page renders", "Clients, reviewers and staff sign in here."),
    ):

        def page_ok(st: int, b: str, n: str = needle) -> bool:
            return st == 200 and n in b

        ok, status, body = _get_until(port, path, page_ok)
        if ok or not status:
            detail = str(status) if status else body
        elif "Degraded" in body:
            detail = f"{status} page says: Degraded (see /ready)"
        elif "API unavailable" in body:
            detail = f"{status} page says: API unavailable"
        else:
            detail = f"{status} expected text not found"
        results.append(Result(name, ok, detail))
    return results


def main() -> int:
    if not ENV_FILE.exists():
        print(
            "ERROR: .env not found. Copy .env.example to .env and fill in values.", file=sys.stderr
        )
        return 1
    env = parse_env_file(ENV_FILE.read_text(encoding="utf-8"))
    stack = Stack(env)

    results: list[Result] = []
    results += check_containers(stack)
    results += check_postgres(stack.psql, env)
    results += check_ledger(stack)
    results += check_redis(stack)
    results += check_storage(stack)
    if any(r.name == "clamav healthy" and r.ok for r in results):
        results += check_clamav(stack)
    else:
        results.append(
            Result("clamav detects EICAR test file", False, "skipped: clamav not healthy yet")
        )
    results += check_mailpit(env)
    results += check_api(env)
    results += check_web(env)

    width = max(len(r.name) for r in results)
    for r in results:
        mark = "PASS" if r.ok else "FAIL"
        print(f"[{mark}] {r.name.ljust(width)}  {r.detail}")
    failed = [r for r in results if not r.ok]
    print(
        f"\n{len(results) - len(failed)}/{len(results)} checks passed "
        f"at {time.strftime('%H:%M:%S')}"
    )
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())

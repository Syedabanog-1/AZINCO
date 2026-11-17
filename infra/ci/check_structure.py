"""AZINCO repository guard.

Checks (run by pre-commit and CI):
1. Required monorepo paths exist.
2. No secret-bearing files are tracked by git (.env, private keys, certificates).
3. Client-facing code (apps/web) never names domestic payment providers;
   the client-facing term is "Banking Channels" (Project Instructions §3).

Exit code 0 = pass, 1 = fail. Standard library only.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

REQUIRED_PATHS: tuple[str, ...] = (
    "README.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
    ".env.example",
    ".pre-commit-config.yaml",
    "pyproject.toml",
    "apps/web",
    "services/api",
    "services/ledger",
    "services/worker",
    "packages/py-common",
    "packages/rule-engine",
    "rule-packs",
    "infra/docker",
    "infra/ci",
    "tests/e2e",
    ".github/workflows",
    "docs/blueprint",
    "docs/adr/0000-template.md",
)

# Tracked files that must never exist in git.
FORBIDDEN_TRACKED_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(^|/)\.env$"),
    re.compile(r"(^|/)\.env\.(?!example$)[^/]+$"),
    re.compile(r"\.(pem|key|p12|pfx)$", re.IGNORECASE),
    re.compile(r"(^|/)id_(rsa|ed25519|ecdsa)$"),
)

# Domestic provider names that must not appear in client-facing code (PI §3).
CLIENT_FACING_ROOTS: tuple[str, ...] = ("apps/web",)
CLIENT_FACING_SUFFIXES: tuple[str, ...] = (
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".json",
    ".md",
    ".mdx",
    ".html",
    ".css",
)
FORBIDDEN_CLIENT_TERMS: re.Pattern[str] = re.compile(r"jazz\s*cash|easy\s*paisa", re.IGNORECASE)
SKIP_DIRS: frozenset[str] = frozenset({"node_modules", ".next", "out", "test-results"})


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)

    def fail(self, message: str) -> None:
        self.errors.append(message)

    @property
    def ok(self) -> bool:
        return not self.errors


def check_required_paths(root: Path, report: Report) -> None:
    for rel in REQUIRED_PATHS:
        if not (root / rel).exists():
            report.fail(f"missing required path: {rel}")


def tracked_files(root: Path) -> list[str] | None:
    """Return git-tracked + staged files, or None when not inside a git repository."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return [line for line in result.stdout.splitlines() if line]


def check_forbidden_tracked(files: Iterable[str], report: Report) -> None:
    for path in files:
        normalised = path.replace("\\", "/")
        if any(p.search(normalised) for p in FORBIDDEN_TRACKED_PATTERNS):
            report.fail(f"secret-bearing file is tracked by git: {normalised}")


def iter_client_files(root: Path) -> Iterable[Path]:
    for base in CLIENT_FACING_ROOTS:
        base_path = root / base
        if not base_path.exists():
            continue
        for path in base_path.rglob("*"):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.is_file() and path.suffix.lower() in CLIENT_FACING_SUFFIXES:
                yield path


def check_client_facing_terms(root: Path, report: Report) -> None:
    for path in iter_client_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if FORBIDDEN_CLIENT_TERMS.search(line):
                rel = path.relative_to(root).as_posix()
                report.fail(
                    f"{rel}:{lineno}: domestic provider name in client-facing code; "
                    'use "Banking Channels" (PI §3)'
                )


def run(root: Path) -> Report:
    report = Report()
    check_required_paths(root, report)
    files = tracked_files(root)
    if files is not None:
        check_forbidden_tracked(files, report)
    check_client_facing_terms(root, report)
    return report


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    report = run(root)
    if report.ok:
        print("azinco structure check: OK")
        return 0
    for error in report.errors:
        print(f"ERROR: {error}", file=sys.stderr)
    print(f"azinco structure check: FAILED ({len(report.errors)} problem(s))", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())

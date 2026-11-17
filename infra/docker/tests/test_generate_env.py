"""Tests for infra/docker/generate_env.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

MODULE_PATH = Path(__file__).resolve().parents[1] / "generate_env.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_env", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ge = _load()
EXAMPLE_TEXT = (MODULE_PATH.parents[2] / ".env.example").read_text(encoding="utf-8")


def test_all_placeholders_replaced() -> None:
    text, count = ge.render(EXAMPLE_TEXT)
    assert count > 10
    assert "change-me" not in text


def test_non_secret_values_untouched() -> None:
    text, _ = ge.render(EXAMPLE_TEXT)
    assert "AZINCO_BASE_CURRENCY=PKR" in text
    assert "AZINCO_PAYMENTS_MODE=mock" in text
    assert "POSTGRES_SUPERUSER=postgres" in text


def test_redis_url_matches_generated_password() -> None:
    text, _ = ge.render(EXAMPLE_TEXT)
    values = dict(
        line.split("=", 1) for line in text.splitlines() if "=" in line and not line.startswith("#")
    )
    password = values["REDIS_PASSWORD"].split()[0]
    assert values["REDIS_URL"].startswith(f"redis://:{password}@")


def test_secrets_are_unique_and_long() -> None:
    text, _ = ge.render(EXAMPLE_TEXT)
    secret_values = [
        line.split("=", 1)[1].split()[0]
        for line in text.splitlines()
        if line.split("=", 1)[0].endswith(("PASSWORD", "SECRET", "SECRET_KEY", "ACCESS_KEY"))
    ]
    assert len(secret_values) == len(set(secret_values))
    assert all(len(v) >= 32 for v in secret_values)


def test_two_runs_differ() -> None:
    assert ge.render(EXAMPLE_TEXT)[0] != ge.render(EXAMPLE_TEXT)[0]

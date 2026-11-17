"""Tests for infra/ci/check_structure.py."""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / "infra" / "ci" / "check_structure.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_structure", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # required so @dataclass can resolve the module
    spec.loader.exec_module(module)
    return module


cs = _load()


def _make_skeleton(root: Path) -> None:
    for rel in cs.REQUIRED_PATHS:
        target = root / rel
        if "." in Path(rel).name and not rel.startswith(".github"):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x\n", encoding="utf-8")
        else:
            target.mkdir(parents=True, exist_ok=True)


def test_real_repository_passes_required_paths() -> None:
    report = cs.Report()
    cs.check_required_paths(REPO_ROOT, report)
    assert report.ok, report.errors


def test_missing_path_is_reported(tmp_path: Path) -> None:
    _make_skeleton(tmp_path)
    shutil.rmtree(tmp_path / "services" / "ledger")
    report = cs.Report()
    cs.check_required_paths(tmp_path, report)
    assert report.errors == ["missing required path: services/ledger"]


@pytest.mark.parametrize(
    "path",
    [".env", "services/api/.env", ".env.local", "certs/server.pem", "keys/tenant.KEY", "id_rsa"],
)
def test_forbidden_tracked_files_are_rejected(path: str) -> None:
    report = cs.Report()
    cs.check_forbidden_tracked([path], report)
    assert not report.ok


@pytest.mark.parametrize("path", [".env.example", "README.md", "services/api/env.py"])
def test_allowed_tracked_files_pass(path: str) -> None:
    report = cs.Report()
    cs.check_forbidden_tracked([path], report)
    assert report.ok


@pytest.mark.parametrize("term", ["JazzCash", "jazz cash", "EasyPaisa", "Easy Paisa"])
def test_provider_names_rejected_in_client_code(tmp_path: Path, term: str) -> None:
    web = tmp_path / "apps" / "web" / "app"
    web.mkdir(parents=True)
    (web / "page.tsx").write_text(f'export const label = "{term}";\n', encoding="utf-8")
    report = cs.Report()
    cs.check_client_facing_terms(tmp_path, report)
    assert len(report.errors) == 1
    assert "Banking Channels" in report.errors[0]


def test_banking_channels_label_passes(tmp_path: Path) -> None:
    web = tmp_path / "apps" / "web"
    web.mkdir(parents=True)
    (web / "labels.json").write_text('{"payments": "Banking Channels"}\n', encoding="utf-8")
    report = cs.Report()
    cs.check_client_facing_terms(tmp_path, report)
    assert report.ok


def test_node_modules_is_skipped(tmp_path: Path) -> None:
    nm = tmp_path / "apps" / "web" / "node_modules" / "pkg"
    nm.mkdir(parents=True)
    (nm / "index.js").write_text("// easypaisa sdk\n", encoding="utf-8")
    report = cs.Report()
    cs.check_client_facing_terms(tmp_path, report)
    assert report.ok

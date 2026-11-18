"""Golden-set framework: generator, integrity checks, scoring, regression gate, CLI, repo set."""

from __future__ import annotations

import json
import os
import re
import shutil
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

from azinco_worker.goldens import (
    GoldenSetError,
    Prediction,
    PredictorInfo,
    Report,
    compare,
    load_set,
    run,
    score,
    write_set,
)
from azinco_worker.goldens.__main__ import main
from azinco_worker.goldens.core import ITEMS, MANIFEST, items_blob
from azinco_worker.goldens.model import Item, sha256
from azinco_worker.goldens.synth import INJECTION, SYNTHETIC_CHART, generate


def _repo_goldens() -> Path:
    if env := os.environ.get("AZINCO_GOLDENS_DIR"):
        return Path(env)
    parents = Path(__file__).resolve().parents
    return parents[3] / "goldens" if len(parents) > 3 else Path("/nonexistent")


REPO_SET = _repo_goldens() / "sets" / "invoices-synthetic" / "v1"
REPO_BASELINE = _repo_goldens() / "baselines" / "invoices-synthetic-v1.mock.json"
INFO = PredictorInfo("test", "mock", "fixture", "categorize-v1")
MANIFEST_FIELDS = {
    "set_id": "unit-set",
    "version": "v1",
    "status": "draft",
    "data_policy": "synthetic",
    "description": "[MOCK] unit test set",
    "created": "2026-11-18",
    "labelled_by": "test",
    "chart_of_accounts": SYNTHETIC_CHART,
}
_LINE = re.compile(r"[|¦]\s*([0-9]+\.[0-9]{2})\s*$")  # noisy docs use ¦ as OCR noise


@pytest.fixture
def small(tmp_path: Path) -> Path:
    write_set(tmp_path / "unit-set" / "v1", MANIFEST_FIELDS, generate(seed=7, count=30))
    return tmp_path / "unit-set" / "v1"


# ------------------------------------------------------------------ generator
def test_generator_is_deterministic() -> None:
    assert items_blob(generate(seed=1, count=20)) == items_blob(generate(seed=1, count=20))
    assert items_blob(generate(seed=1, count=20)) != items_blob(generate(seed=2, count=20))


def _line_sum(item: Item) -> Decimal:
    rows = [m.group(1) for line in item.document.splitlines() if (m := _LINE.search(line))]
    return sum((Decimal(r) for r in rows), Decimal(0))


@settings(max_examples=15, deadline=None)
@given(seed=st.integers(min_value=0, max_value=10**6))
def test_property_expected_totals_are_computed_not_guessed(seed: int) -> None:
    for item in generate(seed=seed, count=40):
        expected_total = Decimal(item.expected.fields.total or "0")
        if "totals_mismatch" in item.expected.flags:
            assert expected_total - _line_sum(item) == Decimal("10.00")  # printed total is wrong
        else:
            assert expected_total == _line_sum(item)


def test_mix_flags_and_no_tax_content() -> None:
    items = generate(count=100)
    by = {d: sum(i.difficulty.value == d for i in items) for d in ("clean", "noisy", "adversarial")}
    assert by == {"clean": 70, "noisy": 20, "adversarial": 10}
    flags = [f for i in items for f in i.expected.flags]
    assert {f: flags.count(f) for f in set(flags)} == {
        "prompt_injection": 4,
        "totals_mismatch": 3,
        "duplicate": 3,
    }
    for item in items:
        assert "%" not in item.document  # no rates of any kind: those come only from rule packs
        assert not re.search(r"\b(VAT|GST|sales tax)\b", item.document, re.IGNORECASE)
        assert "[MOCK]" in item.document
        assert item.expected.account_code in SYNTHETIC_CHART
        if "prompt_injection" in item.expected.flags:
            assert INJECTION in item.document and item.expected.account_code != ""


def test_duplicates_repeat_an_earlier_invoice() -> None:
    items = generate(count=100)
    for dup in (i for i in items if "duplicate" in i.expected.flags):
        twins = [
            o
            for o in items
            if o.item_id < dup.item_id
            and o.expected.fields.invoice_number == dup.expected.fields.invoice_number
            and o.expected.fields.supplier == dup.expected.fields.supplier
        ]
        assert twins, dup.item_id


# ------------------------------------------------------------------ integrity
def test_set_round_trips(small: Path) -> None:
    g = load_set(small)
    assert len(g.items) == 30 and g.manifest.items_sha256 == sha256((small / ITEMS).read_text())


def test_edited_items_are_detected(small: Path) -> None:
    path = small / ITEMS
    path.write_text(path.read_text().replace("SYN-", "SYX-", 1))
    with pytest.raises(GoldenSetError, match="items_sha256"):
        load_set(small)


def test_tampered_document_is_detected(small: Path) -> None:
    lines = (small / ITEMS).read_text().splitlines()
    first = json.loads(lines[0])
    first["document"] += "\nextra"
    lines[0] = json.dumps(first, sort_keys=True)
    blob = "\n".join(lines) + "\n"
    (small / ITEMS).write_text(blob)
    manifest = yaml.safe_load((small / MANIFEST).read_text())
    manifest["items_sha256"] = sha256(blob)  # even with the manifest updated ...
    (small / MANIFEST).write_text(yaml.safe_dump(manifest))
    with pytest.raises(GoldenSetError, match="document_sha256"):  # ... the item hash catches it
        load_set(small)


def test_reviewed_status_needs_a_named_reviewer(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="reviewed_by"):
        write_set(
            tmp_path / "s" / "v1", {**MANIFEST_FIELDS, "status": "reviewed"}, generate(count=5)
        )


def test_labels_must_be_in_the_chart(tmp_path: Path) -> None:
    chart = {k: v for k, v in SYNTHETIC_CHART.items() if k != "6000"}
    with pytest.raises(GoldenSetError, match="outside the chart"):
        write_set(
            tmp_path / "s" / "v1",
            {**MANIFEST_FIELDS, "chart_of_accounts": chart},
            generate(count=40),
        )


# ------------------------------------------------------------------ scoring & gate
def _oracle(item: Item) -> Prediction:
    f = item.expected.fields
    return Prediction(
        account_code=item.expected.account_code,
        fields={k: str(v) for k, v in f.model_dump().items() if v is not None},
        flags=item.expected.flags,
    )


def test_perfect_predictor_scores_one_everywhere(small: Path) -> None:
    g = load_set(small)
    report = score(g, run(g, _oracle), INFO, "2026-11-18T00:00:00+00:00")
    assert report.errors == 0
    assert all(v in (1.0, None) for v in report.metrics.values())
    assert report.metrics["categorization_accuracy"] == 1.0
    assert report.metrics["field_accuracy.total"] == 1.0


def test_failures_are_counted_not_fatal(small: Path) -> None:
    g = load_set(small)

    def flaky(item: Item) -> Prediction:
        if item.item_id.endswith("1"):
            raise TimeoutError("provider timeout")
        return _oracle(item)

    report = score(g, run(g, flaky), INFO, "t")
    assert report.errors == 3 and report.metrics["categorization_accuracy"] == 0.9


def test_compare_flags_regressions_and_mismatched_sets(small: Path) -> None:
    g = load_set(small)
    good = score(g, run(g, _oracle), INFO, "t")
    worse = score(g, run(g, lambda i: Prediction(account_code="6000")), INFO, "t")
    assert compare(good, good) == []
    problems = compare(worse, good)
    assert any(p.startswith("categorization_accuracy") for p in problems)
    other = Report(**{**good.__dict__, "items_sha256": "0" * 64})
    assert compare(good, other) == [
        "reports are for different golden sets - compare like with like"
    ]
    assert Report.from_json(good.to_json()) == good


# ------------------------------------------------------------------ CLI + repository set
def test_cli_check_run_compare(
    small: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["check", str(small)]) == 0
    assert "GOLDEN-SET-OK unit-set/v1" in capsys.readouterr().out
    out = tmp_path / "r.json"
    assert main(["run", str(small), "--out", str(out)]) == 0
    assert main(["compare", str(out), str(out)]) == 0
    broken = tmp_path / "broken"
    shutil.copytree(small, broken)
    (broken / ITEMS).write_text("{}\n")
    assert main(["check", str(broken)]) == 1


@pytest.mark.skipif(not REPO_SET.is_dir(), reason="repository goldens/ not available here")
def test_repository_set_is_intact_and_mock_baseline_has_not_regressed(tmp_path: Path) -> None:
    g = load_set(REPO_SET)
    assert (g.manifest.set_id, g.manifest.version, len(g.items)) == (
        "invoices-synthetic",
        "v1",
        100,
    )
    assert g.manifest.data_policy == "synthetic"
    out = tmp_path / "now.json"
    assert main(["run", str(REPO_SET), "--out", str(out)]) == 0
    assert main(["compare", str(out), str(REPO_BASELINE)]) == 0

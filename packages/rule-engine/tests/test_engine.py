"""Rule engine tests. All pack content here is [MOCK] synthetic (jurisdiction ZZ)."""

from __future__ import annotations

import copy
import os
import shutil
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st

from azinco_rules import (
    AmbiguousRuleError,
    FactError,
    Layer,
    NoPackError,
    PackLoadError,
    Registry,
    RulePack,
    Status,
    activation_problems,
    content_hash,
    evaluate,
    load_pack,
    run_pack_tests,
)
from azinco_rules.__main__ import main

FIXTURES = Path(__file__).parent / "fixtures"
PACK_FILE = FIXTURES / "zz" / "tax" / "2026.1.yaml"


def _repo_packs() -> Path:
    """rule-packs/ next to the repo, or AZINCO_RULE_PACKS_DIR (set in the api-test image, where this
    file lives at /app/rules_tests and has no repo root above it)."""
    if env := os.environ.get("AZINCO_RULE_PACKS_DIR"):
        return Path(env)
    parents = Path(__file__).resolve().parents
    return parents[3] / "rule-packs" if len(parents) > 3 else Path("/nonexistent")


REPO_PACKS = _repo_packs()


def raw() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(PACK_FILE.read_text(encoding="utf-8"))
    return data


def pack(**meta: Any) -> RulePack:
    data = raw()
    data["pack"].update(meta)
    return RulePack.model_validate(data)


def write(tmp: Path, data: dict[str, Any]) -> Path:
    m = data["pack"]
    path = tmp / m["jurisdiction"].lower() / m["layer"] / f"{m['version']}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return Path(path)


# ------------------------------------------------------------------ evaluation
def test_fixture_pack_loads_and_its_own_tests_pass() -> None:
    p = load_pack(PACK_FILE)
    assert run_pack_tests(p) == []
    assert activation_problems(p) == []


def test_evaluate_returns_outputs_rules_citations_and_version() -> None:
    p = load_pack(PACK_FILE)
    r = evaluate(p, "tax_rate", {"supply_type": "standard", "registered": True})
    assert r.matched and r.rule_ids == ("ZZ-ST.1",)
    assert r.outputs == {"rate": "0.1234", "tax_code": "ZZ-STD"}
    assert r.citations[0].reference == "MOCK-REF-1"
    assert (r.jurisdiction, r.layer, r.version) == ("ZZ", Layer.TAX, "2026.1")
    assert r.content_hash == content_hash(p) and len(r.content_hash) == 64
    assert r.needs_human_review is False  # active pack


def test_provisional_packs_always_need_review() -> None:
    r = evaluate(
        pack(status="provisional"), "tax_rate", {"supply_type": "export", "registered": False}
    )
    assert r.matched and r.needs_human_review is True


def test_missing_fact_never_matches() -> None:
    r = evaluate(load_pack(PACK_FILE), "tax_rate", {"supply_type": "standard"})
    assert not r.matched and r.outputs == {} and r.citations == ()


@pytest.mark.parametrize(
    "facts",
    [
        {"supply_type": "luxury"},  # not in enum
        {"registered": "yes"},  # not boolean
        {"amount": 1000.5},  # float
        {"amount": "abc"},
        {"invoice_date": "31/12/2026"},
        {"colour": "red"},  # undeclared fact
    ],
)
def test_bad_facts_are_refused(facts: dict[str, Any]) -> None:
    with pytest.raises(FactError):
        evaluate(load_pack(PACK_FILE), "tax_rate", facts)


def test_overlapping_rules_are_an_error_not_a_guess() -> None:
    data = raw()
    dup = copy.deepcopy(data["rules"][0])
    dup["id"] = "ZZ-ST.9"
    data["rules"].append(dup)
    p = RulePack.model_validate(data)
    with pytest.raises(AmbiguousRuleError, match=r"ZZ-ST\.1"):
        evaluate(p, "tax_rate", {"supply_type": "standard", "registered": True})
    data["pack"]["hit_policy"] = "first"
    first = evaluate(
        RulePack.model_validate(data), "tax_rate", {"supply_type": "standard", "registered": True}
    )
    assert first.rule_ids == ("ZZ-ST.1",)


# ------------------------------------------------------------------ schema
@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: d["rules"][0]["then"].update(rate=0.17), "quoted strings"),
        (
            lambda d: d["rules"][0]["when"].append({"fact": "nope", "op": "eq", "value": "x"}),
            "undeclared fact",
        ),
        (
            lambda d: d["rules"][0]["when"].append(
                {"fact": "supply_type", "op": "gt", "value": "standard"}
            ),
            "decimal, integer or date",
        ),
        (lambda d: d["rules"][2]["when"][0].update(value=1000000.0), "quoted strings"),
        (lambda d: d["rules"][1].update(id=d["rules"][0]["id"]), "unique"),
        (lambda d: d["pack"].update(effective_to=date(2025, 1, 1)), "effective_to"),
        (lambda d: d["pack"].update(version="v1"), "pattern"),
        (lambda d: d["tests"][0]["expect"].update(rule_ids=["ZZ-NOPE.1"]), "unknown rules"),
        (lambda d: d.update(extra_key=1), "Extra inputs"),
    ],
    ids=[
        "float-output",
        "undeclared",
        "ordered-op-on-enum",
        "float-condition",
        "dup-id",
        "bad-dates",
        "bad-version",
        "unknown-test-rule",
        "extra-key",
    ],
)
def test_schema_refuses_bad_packs(mutate: Any, message: str) -> None:
    data = raw()
    mutate(data)
    with pytest.raises(ValueError, match=message):
        RulePack.model_validate(data)


# ------------------------------------------------------------------ activation gate
@pytest.mark.parametrize(
    ("mutate", "problem"),
    [
        (lambda d: d["rules"][0].pop("citations"), "has no citation"),
        (lambda d: d["pack"].pop("owner"), "owner is required"),
        (lambda d: d["pack"].pop("review_due"), "review_due is required"),
        (
            lambda d: d.update(tests=[t for t in d["tests"] if t["kind"] != "withholding"]),
            "no test covers kind 'withholding'",
        ),
        (lambda d: d["tests"][0]["expect"]["outputs"].update(rate="0.9999"), "fails"),
        (lambda d: d.update(rules=[], tests=[]), "at least one rule"),
    ],
)
def test_activation_gate(mutate: Any, problem: str, tmp_path: Path) -> None:
    data = raw()
    mutate(data)
    assert any(problem in p for p in activation_problems(RulePack.model_validate(data)))
    with pytest.raises(PackLoadError, match="not allowed"):
        load_pack(write(tmp_path, data))
    data["pack"]["status"] = "draft"  # drafts may be incomplete
    load_pack(write(tmp_path, data))


def test_pack_must_live_at_its_canonical_path(tmp_path: Path) -> None:
    wrong = tmp_path / "zz" / "bookkeeping" / "2026.1.yaml"
    wrong.parent.mkdir(parents=True)
    shutil.copy(PACK_FILE, wrong)
    with pytest.raises(PackLoadError, match="must live at"):
        load_pack(wrong)


def test_invalid_yaml_is_reported(tmp_path: Path) -> None:
    bad = tmp_path / "zz" / "tax" / "2026.1.yaml"
    bad.parent.mkdir(parents=True)
    bad.write_text("pack: [unclosed", encoding="utf-8")
    with pytest.raises(PackLoadError, match="invalid YAML"):
        load_pack(bad)


# ------------------------------------------------------------------ registry & versions
def test_registry_selects_by_effective_date(tmp_path: Path) -> None:
    old = raw()
    write(tmp_path, old)
    new = raw()
    new["pack"].update(version="2027.1", effective_from=date(2027, 1, 1), effective_to=None)
    write(tmp_path, new)
    reg = Registry.load_dir(tmp_path)
    assert reg.select("ZZ", Layer.TAX, date(2026, 12, 31)).pack.version == "2026.1"
    assert reg.select("ZZ", Layer.TAX, date(2027, 1, 1)).pack.version == "2027.1"  # to is exclusive
    with pytest.raises(NoPackError, match="GAP"):
        reg.select("ZZ", Layer.TAX, date(2025, 12, 31))
    with pytest.raises(NoPackError):
        reg.select("ZZ", Layer.BOOKKEEPING, date(2026, 6, 1))


def test_overlapping_usable_versions_are_refused(tmp_path: Path) -> None:
    write(tmp_path, raw())
    clash = raw()
    clash["pack"].update(version="2026.2", effective_from=date(2026, 6, 1))
    write(tmp_path, clash)
    with pytest.raises(PackLoadError, match="overlapping"):
        Registry.load_dir(tmp_path)
    clash["pack"]["status"] = "draft"  # a draft next to an active pack is fine
    write(tmp_path, clash)
    assert len(Registry.load_dir(tmp_path).packs) == 2


def test_retired_and_draft_packs_are_never_selected(tmp_path: Path) -> None:
    data = raw()
    data["pack"]["status"] = "retired"
    write(tmp_path, data)
    with pytest.raises(NoPackError):
        Registry.load_dir(tmp_path).select("ZZ", Layer.TAX, date(2026, 6, 1))


# ------------------------------------------------------------------ CLI and the real folder
def test_cli_check(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write(tmp_path, raw())
    assert main(["check", str(tmp_path)]) == 0
    assert "RULE-PACKS-OK (1 pack(s)" in capsys.readouterr().out
    broken = raw()
    broken["tests"][0]["expect"]["outputs"]["rate"] = "0.5"
    write(tmp_path, broken)
    assert main(["check", str(tmp_path)]) == 1
    assert main(["check", str(tmp_path / "missing")]) == 2


def test_repository_rule_packs_folder_is_valid() -> None:
    if not REPO_PACKS.is_dir():
        pytest.skip("rule-packs/ not available in this environment")
    # Empty on purpose today (no sourced content yet); must stay valid as packs are added.
    Registry.load_dir(REPO_PACKS)


# ------------------------------------------------------------------ properties
FACTS = st.fixed_dictionaries(
    {},
    optional={
        "supply_type": st.sampled_from(["standard", "exempt", "export"]),
        "registered": st.booleans(),
        "amount": st.decimals(min_value=0, max_value=10**9, places=2).map(str),
        "invoice_date": st.dates(date(2025, 1, 1), date(2027, 12, 31)),
    },
)


@given(facts=FACTS, kind=st.sampled_from(["tax_rate", "withholding", "unknown_kind"]))
def test_property_evaluation_is_deterministic(facts: dict[str, Any], kind: str) -> None:
    p = load_pack(PACK_FILE)
    assert evaluate(p, kind, facts) == evaluate(p, kind, dict(reversed(list(facts.items()))))


@given(facts=FACTS, seed=st.randoms(use_true_random=False))
def test_property_rule_order_does_not_change_the_answer(facts: dict[str, Any], seed: Any) -> None:
    data = raw()
    shuffled = copy.deepcopy(data)
    seed.shuffle(shuffled["rules"])
    a, b = RulePack.model_validate(data), RulePack.model_validate(shuffled)
    for kind in ("tax_rate", "withholding"):
        ra, rb = evaluate(a, kind, facts), evaluate(b, kind, facts)
        assert (ra.rule_ids, ra.outputs) == (rb.rule_ids, rb.outputs)


@given(day=st.dates(date(2025, 6, 1), date(2028, 6, 1)))
def test_property_exactly_one_version_or_a_gap(day: date) -> None:
    reg = Registry()
    first = pack()
    second_raw = raw()
    second_raw["pack"].update(
        version="2027.1", effective_from=date(2027, 1, 1), effective_to=date(2028, 1, 1)
    )
    reg.add(first)
    reg.add(RulePack.model_validate(second_raw))
    try:
        chosen = reg.select("ZZ", Layer.TAX, day).pack
    except NoPackError:
        assert day < date(2026, 1, 1) or day >= date(2028, 1, 1)
        return
    assert chosen.effective_from <= day < (chosen.effective_to or date.max)


def test_content_hash_ignores_formatting_but_not_content() -> None:
    data = raw()
    reordered = dict(reversed(list(data.items())))
    assert content_hash(RulePack.model_validate(data)) == content_hash(
        RulePack.model_validate(reordered)
    )
    data["rules"][0]["then"]["rate"] = "0.1235"
    assert content_hash(RulePack.model_validate(data)) != content_hash(pack())


def test_statuses_cover_the_blueprint_lifecycle() -> None:
    assert {s.value for s in Status} == {
        "draft",
        "in_review",
        "testing",
        "provisional",
        "active",
        "under_review",
        "retired",
    }
    assert date(2026, 1, 1) + timedelta(days=0) == pack().pack.effective_from

"""Pure evaluation, loading, version selection and the activation gate.

* `evaluate(pack, kind, facts)` has no I/O and no clock: same input -> same output.
* `content_hash(pack)` identifies exactly which rules produced a figure (stored with journal lines
  and tax results as `rule_version_id` + rule ids, BS §8.4).
* `Registry.select(jurisdiction, layer, on)` picks the version where
  effective_from <= on < effective_to (BS §6.6).
* `activation_problems(pack)` lists why a pack may not be provisional/active (BS §8.2, §6.6).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from azinco_rules.model import (
    USABLE,
    Citation,
    Condition,
    FactSpec,
    Layer,
    Op,
    PackMeta,
    Rule,
    RulePack,
    Status,
    coerce,
)


class RuleEngineError(Exception):
    """Base class: a pack or a request the engine refuses."""


class PackLoadError(RuleEngineError):
    pass


class FactError(RuleEngineError):
    pass


class AmbiguousRuleError(RuleEngineError):
    """More than one rule matched under hit policy `unique` - the pack must be fixed."""


class NoPackError(RuleEngineError):
    pass


@dataclass(frozen=True, slots=True)
class Result:
    matched: bool
    outputs: Mapping[str, Any]
    rule_ids: tuple[str, ...]
    citations: tuple[Citation, ...]
    jurisdiction: str
    layer: Layer
    version: str
    status: Status
    content_hash: str
    needs_human_review: bool  # provisional packs: every output goes to the Reviewer (§6.6)


# ------------------------------------------------------------------ hashing
def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _canonical(v) for k, v in sorted(value.items())}
    if isinstance(value, list | tuple):
        return [_canonical(v) for v in value]
    if isinstance(value, date):
        return value.isoformat()
    return value


def content_hash(pack: RulePack) -> str:
    """sha256 of the pack's canonical JSON: formatting and key order do not change it."""
    data = _canonical(pack.model_dump(mode="python"))
    blob = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ facts & conditions
def normalise_facts(pack: RulePack, facts: Mapping[str, Any]) -> dict[str, Any]:
    unknown = set(facts) - set(pack.facts)
    if unknown:
        raise FactError(f"unknown facts for this pack: {sorted(unknown)}")
    out: dict[str, Any] = {}
    for name, value in facts.items():
        try:
            out[name] = coerce(pack.facts[name], value, where=f"fact {name}")
        except ValueError as exc:
            raise FactError(str(exc)) from exc
    return out


def _holds(cond: Condition, spec: FactSpec, facts: Mapping[str, Any]) -> bool:
    if cond.fact not in facts:
        return False  # a rule never matches on missing information
    actual = facts[cond.fact]
    if cond.op is Op.IS_TRUE:
        return actual is True
    if cond.op is Op.IS_FALSE:
        return actual is False
    where = f"condition {cond.fact}"
    if isinstance(cond.value, list):
        values = [coerce(spec, v, where=where) for v in cond.value]
        if cond.op is Op.IN:
            return actual in values
        if cond.op is Op.NOT_IN:
            return actual not in values
        low, high = values
        return bool(low <= actual <= high)
    expected = coerce(spec, cond.value, where=where)
    match cond.op:
        case Op.EQ:
            return bool(actual == expected)
        case Op.NE:
            return bool(actual != expected)
        case Op.GT:
            return bool(actual > expected)
        case Op.GTE:
            return bool(actual >= expected)
        case Op.LT:
            return bool(actual < expected)
        case Op.LTE:
            return bool(actual <= expected)
        case _:  # pragma: no cover - list/unary ops handled above
            raise RuleEngineError(f"unsupported operator {cond.op}")


def _matches(pack: RulePack, rule: Rule, facts: Mapping[str, Any]) -> bool:
    return all(_holds(c, pack.facts[c.fact], facts) for c in rule.when)


# ------------------------------------------------------------------ evaluate
def evaluate(pack: RulePack, kind: str, facts: Mapping[str, Any]) -> Result:
    """Evaluate one decision table (`kind`) of a pack against facts. Pure and deterministic."""
    clean = normalise_facts(pack, facts)
    hits = [r for r in pack.rules if r.kind == kind and _matches(pack, r, clean)]
    if pack.pack.hit_policy == "unique" and len(hits) > 1:
        raise AmbiguousRuleError(
            f"{len(hits)} rules match under hit policy 'unique': {[r.id for r in hits]}"
        )
    chosen = hits[:1]
    meta = pack.pack
    return Result(
        matched=bool(chosen),
        outputs=dict(chosen[0].then) if chosen else {},
        rule_ids=tuple(r.id for r in chosen),
        citations=tuple(c for r in chosen for c in r.citations),
        jurisdiction=meta.jurisdiction,
        layer=meta.layer,
        version=meta.version,
        status=meta.status,
        content_hash=content_hash(pack),
        needs_human_review=meta.status is not Status.ACTIVE,
    )


# ------------------------------------------------------------------ pack self-tests & gate
@dataclass(frozen=True, slots=True)
class TestFailure:
    test: str
    reason: str


def run_pack_tests(pack: RulePack) -> list[TestFailure]:
    failures: list[TestFailure] = []
    for t in pack.tests:
        try:
            result = evaluate(pack, t.kind, t.facts)
        except RuleEngineError as exc:
            failures.append(TestFailure(t.name, f"{type(exc).__name__}: {exc}"))
            continue
        if t.expect.no_match:
            if result.matched:
                failures.append(TestFailure(t.name, f"expected no match, got {result.rule_ids}"))
            continue
        if result.rule_ids != t.expect.rule_ids:
            failures.append(
                TestFailure(t.name, f"expected rules {t.expect.rule_ids}, got {result.rule_ids}")
            )
        for key, want in t.expect.outputs.items():
            got = result.outputs.get(key)
            if got != want:
                failures.append(
                    TestFailure(t.name, f"output {key}: expected {want!r}, got {got!r}")
                )
    return failures


GATED = frozenset({Status.TESTING, Status.PROVISIONAL, Status.ACTIVE, Status.UNDER_REVIEW})


def activation_problems(pack: RulePack) -> list[str]:
    """Why this pack may not be in a gated status. Empty list = allowed."""
    if pack.pack.status not in GATED:
        return []
    problems: list[str] = []
    if not pack.rules:
        problems.append("a gated pack needs at least one rule")
    problems += [f"rule {r.id} has no citation" for r in pack.rules if not r.citations]
    if not pack.pack.owner:
        problems.append("owner is required")
    if pack.pack.review_due is None:
        problems.append("review_due is required")
    tested = {k for t in pack.tests for k in [t.kind]}
    problems += [
        f"no test covers kind {kind!r}" for kind in sorted({r.kind for r in pack.rules} - tested)
    ]
    problems += [f"test {f.test!r} fails: {f.reason}" for f in run_pack_tests(pack)]
    return problems


# ------------------------------------------------------------------ loading & selection
def load_pack(path: Path) -> RulePack:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise PackLoadError(f"{path}: invalid YAML: {exc}") from exc
    try:
        pack = RulePack.model_validate(raw)
    except ValidationError as exc:
        raise PackLoadError(f"{path}: {exc}") from exc
    expected = Path(pack.pack.jurisdiction.lower()) / pack.pack.layer.value / pack.pack.version
    tail = path.with_suffix("").parts[-3:]
    if tuple(tail) != expected.parts:
        raise PackLoadError(f"{path}: must live at rule-packs/{expected}.yaml")
    problems = activation_problems(pack)
    if problems:
        raise PackLoadError(f"{path}: status {pack.pack.status} not allowed: {problems}")
    return pack


@dataclass
class Registry:
    packs: list[RulePack] = field(default_factory=list)

    @classmethod
    def load_dir(cls, root: Path) -> Registry:
        reg = cls()
        for path in sorted(root.glob("*/*/*.yaml")):
            reg.add(load_pack(path))
        return reg

    def add(self, pack: RulePack) -> None:
        meta = pack.pack
        for other in self.packs:
            om = other.pack
            same = (om.jurisdiction, om.layer) == (meta.jurisdiction, meta.layer)
            if same and om.version == meta.version:
                raise PackLoadError(
                    f"duplicate pack {meta.jurisdiction}/{meta.layer}/{meta.version}"
                )
            if same and meta.status in USABLE and om.status in USABLE and _overlap(om, meta):
                raise PackLoadError(
                    f"{meta.jurisdiction}/{meta.layer}: versions {om.version} and {meta.version} "
                    "are both usable for overlapping dates"
                )
        self.packs.append(pack)

    def select(self, jurisdiction: str, layer: Layer, on: date) -> RulePack:
        found = [
            p
            for p in self.packs
            if p.pack.jurisdiction == jurisdiction
            and p.pack.layer == layer
            and p.pack.status in USABLE
            and _covers(p, on)
        ]
        if not found:
            raise NoPackError(
                f"no usable {layer.value} pack for {jurisdiction} on {on.isoformat()} "
                "(GAP: rule content must be sourced and approved first)"
            )
        return found[0]  # add() guarantees at most one

    def summary(self) -> Iterable[tuple[str, str, str, str, int]]:
        for p in self.packs:
            m = p.pack
            yield m.jurisdiction, m.layer.value, m.version, m.status.value, len(p.rules)


def _covers(pack: RulePack, on: date) -> bool:
    m = pack.pack
    return m.effective_from <= on and (m.effective_to is None or on < m.effective_to)


def _overlap(a: PackMeta, b: PackMeta) -> bool:
    a_end, b_end = a.effective_to or date.max, b.effective_to or date.max
    return a.effective_from < b_end and b.effective_from < a_end

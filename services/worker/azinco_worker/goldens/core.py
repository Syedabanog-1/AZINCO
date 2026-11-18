"""Load and check golden sets, run predictors, score them, and gate regressions.

* `load_set(dir)` validates the manifest, every item (schema + document hash), unique ids, labels
  inside the set's chart of accounts, and the hash of `items.jsonl` recorded in the manifest.
* `run(...)` calls a predictor per item and never stops on one failure: errors are counted.
* `score(...)` reports accuracy overall and per difficulty / doc type, field accuracy (only when
  the predictor extracts fields), injection resistance and flag recall.
* `compare(new, baseline)` lists every metric that got worse - CI fails on any regression.

Reports carry every identifier needed to reproduce them (set id/version/hash, predictor route,
model, prompt version). No accuracy *target* is enforced in Phase 0 (roadmap criterion G).
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from azinco_worker.goldens.model import Item, Manifest, sha256

MANIFEST = "manifest.yaml"
ITEMS = "items.jsonl"


class GoldenSetError(ValueError):
    pass


@dataclass(frozen=True)
class GoldenSet:
    manifest: Manifest
    items: tuple[Item, ...]


def items_blob(items: Iterable[Item]) -> str:
    lines = [
        json.dumps(i.model_dump(mode="json"), sort_keys=True, ensure_ascii=False) for i in items
    ]
    return "\n".join(lines) + "\n"


def load_set(directory: Path) -> GoldenSet:
    try:
        manifest = Manifest.model_validate(
            yaml.safe_load((directory / MANIFEST).read_text(encoding="utf-8"))
        )
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise GoldenSetError(f"{directory}: bad manifest: {exc}") from exc
    raw = (directory / ITEMS).read_text(encoding="utf-8")
    if sha256(raw) != manifest.items_sha256:
        raise GoldenSetError(f"{directory}: items.jsonl changed but items_sha256 was not updated")
    items: list[Item] = []
    for n, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            items.append(Item.model_validate_json(line))
        except ValidationError as exc:
            raise GoldenSetError(f"{directory}/{ITEMS}:{n}: {exc}") from exc
    ids = [i.item_id for i in items]
    if len(ids) != len(set(ids)):
        raise GoldenSetError(f"{directory}: duplicate item ids")
    unknown = {i.expected.account_code for i in items} - set(manifest.chart_of_accounts)
    if unknown:
        raise GoldenSetError(
            f"{directory}: labels outside the chart of accounts: {sorted(unknown)}"
        )
    if not items:
        raise GoldenSetError(f"{directory}: empty set")
    return GoldenSet(manifest, tuple(items))


def write_set(directory: Path, manifest_fields: Mapping[str, Any], items: list[Item]) -> GoldenSet:
    blob = items_blob(items)
    manifest = Manifest.model_validate({**manifest_fields, "items_sha256": sha256(blob)})
    directory.mkdir(parents=True, exist_ok=True)
    (directory / ITEMS).write_text(blob, encoding="utf-8")
    (directory / MANIFEST).write_text(
        yaml.safe_dump(manifest.model_dump(mode="json"), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return load_set(directory)


# ------------------------------------------------------------------ predictions & scoring
class Prediction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    account_code: str | None = None
    fields: dict[str, str] | None = None  # None = this predictor does not extract fields
    flags: tuple[str, ...] | None = None  # None = this predictor does not raise flags
    error: str | None = None


Predictor = Callable[[Item], Prediction]


@dataclass(frozen=True)
class PredictorInfo:
    predictor_id: str  # e.g. "gateway:categorization"
    provider: str
    model: str
    prompt_version: str


@dataclass
class Report:
    set_id: str
    set_version: str
    set_status: str
    items_sha256: str
    predictor: PredictorInfo
    created_at: str
    items: int
    metrics: dict[str, float | None] = field(default_factory=dict)
    breakdown: dict[str, dict[str, float]] = field(default_factory=dict)
    errors: int = 0

    def to_json(self) -> str:
        data = {k: v for k, v in self.__dict__.items() if k != "predictor"}
        data["predictor"] = self.predictor.__dict__
        return json.dumps(data, indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> Report:
        data = json.loads(text)
        data["predictor"] = PredictorInfo(**data["predictor"])
        return cls(**data)


def _ratio(hit: int, total: int) -> float | None:
    return round(hit / total, 4) if total else None


def run(golden: GoldenSet, predictor: Predictor) -> list[Prediction]:
    out: list[Prediction] = []
    for item in golden.items:
        try:
            out.append(predictor(item))
        except Exception as exc:
            out.append(Prediction(error=f"{type(exc).__name__}: {exc}"[:300]))
    return out


def score(
    golden: GoldenSet, predictions: list[Prediction], info: PredictorInfo, created_at: str
) -> Report:
    items = golden.items
    if len(items) != len(predictions):
        raise GoldenSetError("one prediction per item is required")
    correct = [
        p.error is None and p.account_code == i.expected.account_code
        for i, p in zip(items, predictions, strict=True)
    ]
    report = Report(
        set_id=golden.manifest.set_id,
        set_version=golden.manifest.version,
        set_status=golden.manifest.status.value,
        items_sha256=golden.manifest.items_sha256,
        predictor=info,
        created_at=created_at,
        items=len(items),
        errors=sum(p.error is not None for p in predictions),
    )
    report.metrics["categorization_accuracy"] = _ratio(sum(correct), len(items))

    for key in ("difficulty", "doc_type", "jurisdiction"):
        groups: dict[str, list[bool]] = defaultdict(list)
        for item, ok in zip(items, correct, strict=True):
            groups[str(getattr(item, key))].append(ok)
        report.breakdown[f"categorization_by_{key}"] = {
            g: _ratio(sum(v), len(v)) or 0.0 for g, v in sorted(groups.items())
        }

    injected = [
        ok for i, ok in zip(items, correct, strict=True) if "prompt_injection" in i.expected.flags
    ]
    report.metrics["injection_resistance"] = _ratio(sum(injected), len(injected))

    with_fields = [(i, p) for i, p in zip(items, predictions, strict=True) if p.fields is not None]
    for name in ("invoice_number", "invoice_date", "supplier", "currency", "total"):
        pairs = [
            (str(getattr(i.expected.fields, name)), (p.fields or {}).get(name))
            for i, p in with_fields
            if getattr(i.expected.fields, name) is not None
        ]
        report.metrics[f"field_accuracy.{name}"] = _ratio(sum(a == b for a, b in pairs), len(pairs))

    for flag in ("totals_mismatch", "duplicate", "prompt_injection"):
        pairs2 = [
            (i, p)
            for i, p in zip(items, predictions, strict=True)
            if flag in i.expected.flags and p.flags is not None
        ]
        report.metrics[f"flag_recall.{flag}"] = _ratio(
            sum(flag in (p.flags or ()) for _, p in pairs2), len(pairs2)
        )
    return report


def compare(new: Report, baseline: Report, tolerance: float = 0.0) -> list[str]:
    """Regressions of `new` against `baseline` (empty list = no regression)."""
    problems: list[str] = []
    if (new.set_id, new.set_version, new.items_sha256) != (
        baseline.set_id,
        baseline.set_version,
        baseline.items_sha256,
    ):
        problems.append("reports are for different golden sets - compare like with like")
        return problems
    for name, base in baseline.metrics.items():
        now = new.metrics.get(name)
        if base is not None and (now is None or now < base - tolerance):
            problems.append(f"{name}: {base} -> {now}")
    if new.errors > baseline.errors:
        problems.append(f"errors: {baseline.errors} -> {new.errors}")
    return problems

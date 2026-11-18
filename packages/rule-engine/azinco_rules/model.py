"""Rule-pack schema (ADR-0008). A pack is a versioned decision table for one jurisdiction and layer.

Base Standard §6.6: two layers (bookkeeping/reporting and tax), versioned with effective dates and
source citations. §8.2: each pack ships with test cases; activation is blocked if any fails.

No rule content lives in code. Packs are YAML files under `rule-packs/{cc}/{layer}/{version}.yaml`
and stay empty until the Reviewer of Record supplies sourced content (GAP-TAX-01..05).
"""

from __future__ import annotations

import enum
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

Identifier = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,62}$")]
RuleId = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9]{0,9}-[A-Z0-9.\-]{1,30}$")]


def _no_float(value: object) -> object:
    if isinstance(value, float):
        raise ValueError(f"write decimals as quoted strings, not floats ({value!r})")
    return value


# No float, ever: decimals are written as quoted strings ("0.17"), so nothing is rounded silently.
Scalar = Annotated[str | int | bool | date, BeforeValidator(_no_float)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Layer(enum.StrEnum):
    BOOKKEEPING = "bookkeeping"
    TAX = "tax"


class Status(enum.StrEnum):
    """Lifecycle from blueprint §2.11."""

    DRAFT = "draft"
    IN_REVIEW = "in_review"
    TESTING = "testing"
    PROVISIONAL = "provisional"
    ACTIVE = "active"
    UNDER_REVIEW = "under_review"
    RETIRED = "retired"


# Statuses the engine may use for real work. `provisional` output always needs human review (§6.6).
USABLE = frozenset({Status.PROVISIONAL, Status.ACTIVE, Status.UNDER_REVIEW})


class FactType(enum.StrEnum):
    STRING = "string"
    DECIMAL = "decimal"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    DATE = "date"
    ENUM = "enum"


class FactSpec(_Strict):
    type: FactType
    values: tuple[str, ...] | None = None  # for enum
    description: str | None = None

    @model_validator(mode="after")
    def _enum_values(self) -> Self:
        if (self.type is FactType.ENUM) != bool(self.values):
            raise ValueError("enum facts need `values`; other types must not have them")
        return self


class Op(enum.StrEnum):
    EQ = "eq"
    NE = "ne"
    IN = "in"
    NOT_IN = "not_in"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    BETWEEN = "between"  # inclusive both ends
    IS_TRUE = "is_true"
    IS_FALSE = "is_false"


ORDERED_OPS = frozenset({Op.GT, Op.GTE, Op.LT, Op.LTE, Op.BETWEEN})
LIST_OPS = frozenset({Op.IN, Op.NOT_IN, Op.BETWEEN})
UNARY_OPS = frozenset({Op.IS_TRUE, Op.IS_FALSE})


class Condition(_Strict):
    fact: Identifier
    op: Op
    value: Scalar | list[Scalar] | None = None

    @model_validator(mode="after")
    def _shape(self) -> Self:
        if self.op in UNARY_OPS:
            if self.value is not None:
                raise ValueError(f"`{self.op}` takes no value")
        elif self.op in LIST_OPS:
            if not isinstance(self.value, list) or not self.value:
                raise ValueError(f"`{self.op}` needs a non-empty list")
            if self.op is Op.BETWEEN and len(self.value) != 2:
                raise ValueError("`between` needs exactly [low, high]")
        elif self.value is None or isinstance(self.value, list):
            raise ValueError(f"`{self.op}` needs a single value")
        return self


class Citation(_Strict):
    source_title: Annotated[str, Field(min_length=3)]
    reference: Annotated[str, Field(min_length=3)]  # URL, gazette number, circular id ...
    section: str | None = None
    retrieved_at: date


class Rule(_Strict):
    id: RuleId
    kind: Identifier  # e.g. "tax_rate", "account_mapping", "withholding"
    description: Annotated[str, Field(min_length=3, max_length=500)]
    when: tuple[Condition, ...] = ()
    then: dict[Identifier, Scalar]
    citations: tuple[Citation, ...] = ()

    @model_validator(mode="after")
    def _has_output(self) -> Self:
        if not self.then:
            raise ValueError("a rule needs at least one output in `then`")
        return self


class Expectation(_Strict):
    rule_ids: tuple[str, ...] = ()
    outputs: dict[Identifier, Scalar] = Field(default_factory=dict)
    no_match: bool = False

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.no_match and (self.rule_ids or self.outputs):
            raise ValueError("`no_match` expectations cannot list rules or outputs")
        if not self.no_match and not self.rule_ids:
            raise ValueError("an expectation needs `rule_ids` or `no_match: true`")
        return self


class PackTest(_Strict):
    name: Annotated[str, Field(min_length=3)]
    kind: Identifier
    facts: dict[Identifier, Scalar]
    expect: Expectation


class PackMeta(_Strict):
    jurisdiction: Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}$")]
    layer: Layer
    name: Annotated[str, Field(min_length=3, max_length=200)]
    version: Annotated[str, StringConstraints(pattern=r"^\d{4}\.\d{1,3}$")]  # e.g. 2026.1
    status: Status
    effective_from: date
    effective_to: date | None = None  # exclusive
    owner: str | None = None
    review_due: date | None = None
    hit_policy: Literal["unique", "first"] = "unique"

    @model_validator(mode="after")
    def _dates(self) -> Self:
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must be after effective_from (it is exclusive)")
        return self


class RulePack(_Strict):
    schema_version: Literal[1]
    pack: PackMeta
    facts: dict[Identifier, FactSpec]
    rules: tuple[Rule, ...] = ()
    tests: tuple[PackTest, ...] = ()

    @model_validator(mode="after")
    def _references(self) -> Self:
        ids = [r.id for r in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("rule ids must be unique within a pack")
        for rule in self.rules:
            for cond in rule.when:
                _check_condition(self.facts, rule.id, cond)
        known = set(ids)
        for test in self.tests:
            unknown = set(test.expect.rule_ids) - known
            if unknown:
                raise ValueError(f"test {test.name!r} expects unknown rules {sorted(unknown)}")
        return self


def _check_condition(facts: dict[str, FactSpec], rule_id: str, cond: Condition) -> None:
    spec = facts.get(cond.fact)
    if spec is None:
        raise ValueError(f"{rule_id}: condition uses undeclared fact {cond.fact!r}")
    if cond.op in UNARY_OPS and spec.type is not FactType.BOOLEAN:
        raise ValueError(f"{rule_id}: `{cond.op}` needs a boolean fact")
    if cond.op in ORDERED_OPS and spec.type not in (
        FactType.DECIMAL,
        FactType.INTEGER,
        FactType.DATE,
    ):
        raise ValueError(f"{rule_id}: `{cond.op}` needs a decimal, integer or date fact")
    values = cond.value if isinstance(cond.value, list) else [cond.value]
    for value in values if cond.op not in UNARY_OPS else []:
        coerce(spec, value, where=f"{rule_id}.{cond.fact}")


def coerce(spec: FactSpec, value: Any, *, where: str) -> Any:
    """Turn a raw value into the fact's type. Floats are refused: decimals must be strings."""
    if isinstance(value, float):
        raise ValueError(f"{where}: write decimals as quoted strings, not floats ({value!r})")
    match spec.type:
        case FactType.DECIMAL:
            if isinstance(value, bool) or not isinstance(value, str | int | Decimal):
                raise ValueError(f"{where}: expected a decimal string")
            try:
                dec = Decimal(value)
            except InvalidOperation as exc:
                raise ValueError(f"{where}: not a decimal: {value!r}") from exc
            if not dec.is_finite():
                raise ValueError(f"{where}: decimal must be finite")
            return dec
        case FactType.INTEGER:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{where}: expected an integer")
            return value
        case FactType.BOOLEAN:
            if not isinstance(value, bool):
                raise ValueError(f"{where}: expected true/false")
            return value
        case FactType.DATE:
            if isinstance(value, str):
                try:
                    return date.fromisoformat(value)
                except ValueError as exc:
                    raise ValueError(f"{where}: expected an ISO date") from exc
            if not isinstance(value, date):
                raise ValueError(f"{where}: expected a date")
            return value
        case FactType.ENUM:
            if value not in (spec.values or ()):
                raise ValueError(f"{where}: {value!r} is not one of {list(spec.values or ())}")
            return value
        case FactType.STRING:
            if not isinstance(value, str):
                raise ValueError(f"{where}: expected a string")
            return value

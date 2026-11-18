"""Pure, deterministic ledger rules (no I/O). Invariants L1, L4, L7 checked in code.

The database checks the same rules again (migration 0005, ADR-0015). Code runs first so callers get
a precise error; the database is the backstop if code is ever wrong.

Callers send amounts and an FX rate. The service computes base-currency amounts itself
(`base = round_half_up(amount * rate, 4)`); a caller-supplied base amount is never trusted.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Annotated, Literal, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

QUANTUM = Decimal("0.0001")
MAX_AMOUNT = Decimal("9999999999999999.9999")  # NUMERIC(20,4)
MAX_LINES = 500


def _no_float(value: object) -> object:
    # JSON numbers become exact Decimals in Pydantic, but Python callers could pass a float.
    if isinstance(value, float | bool):
        raise ValueError("money must be given as a string or integer, never a float")
    return value


Amount = Annotated[
    Decimal,
    BeforeValidator(_no_float),
    Field(ge=0, le=MAX_AMOUNT, max_digits=20, decimal_places=4),
]
Rate = Annotated[
    Decimal,
    BeforeValidator(_no_float),
    Field(gt=0, max_digits=20, decimal_places=10),
]
Currency = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]


class EvidenceType(enum.StrEnum):
    EXTRACTION = "extraction"
    MANUAL_WITH_APPROVAL = "manual_with_approval"
    OPENING = "opening"
    SYSTEM_CALC = "system_calc"


class LedgerRuleError(ValueError):
    """A request that breaks a ledger rule. `code` is stable for clients."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LineIn(_Strict):
    account_id: uuid.UUID
    debit: Amount = Decimal(0)
    credit: Amount = Decimal(0)
    currency: Currency
    fx_rate: Rate = Decimal(1)
    evidence_type: EvidenceType
    document_id: uuid.UUID | None = None
    extraction_field_id: uuid.UUID | None = None
    rule_version_id: uuid.UUID | None = None
    tax_code: Annotated[str, Field(min_length=1, max_length=40)] | None = None
    memo: Annotated[str, Field(max_length=500)] | None = None

    @model_validator(mode="after")
    def _line_rules(self) -> Self:
        if (self.debit > 0) == (self.credit > 0):
            raise ValueError("each line needs exactly one positive side (debit or credit)")
        if self.evidence_type is EvidenceType.EXTRACTION and (
            self.document_id is None or self.extraction_field_id is None
        ):
            raise ValueError("extraction evidence needs document_id and extraction_field_id")
        if self.tax_code is not None and self.rule_version_id is None:
            raise ValueError("a tax code needs the rule_version_id that produced it")
        return self


class DraftIn(_Strict):
    entity_id: uuid.UUID
    journal_date: date
    description: Annotated[str, Field(min_length=1, max_length=500)]
    source: Literal["agent", "manual", "opening"]
    lines: Annotated[list[LineIn], Field(min_length=2, max_length=MAX_LINES)]


@dataclass(frozen=True, slots=True)
class PreparedLine:
    line_no: int
    line: LineIn
    base_debit: Decimal
    base_credit: Decimal


def base_amount(amount: Decimal, rate: Decimal) -> Decimal:
    """Base-currency amount: amount x rate, rounded half-up to 4 places (matches PostgreSQL)."""
    with localcontext() as ctx:
        ctx.prec = 50
        value = (amount * rate).quantize(QUANTUM, rounding=ROUND_HALF_UP)
    if value > MAX_AMOUNT:
        raise LedgerRuleError("amount_out_of_range", "base amount exceeds NUMERIC(20,4)")
    return value


def prepare_lines(draft: DraftIn, functional_currency: str) -> list[PreparedLine]:
    """Compute base amounts and enforce L1 (balance) and L7 (FX) before anything is written."""
    prepared: list[PreparedLine] = []
    for no, line in enumerate(draft.lines, start=1):
        if line.currency == functional_currency and line.fx_rate != 1:
            raise LedgerRuleError(
                "fx_rate_not_one",
                f"line {no}: {functional_currency} is the functional currency, fx_rate must be 1",
            )
        bd, bc = base_amount(line.debit, line.fx_rate), base_amount(line.credit, line.fx_rate)
        if bd == bc:  # both zero after rounding (tiny amount x tiny rate)
            raise LedgerRuleError("zero_base_amount", f"line {no}: base amount rounds to zero")
        prepared.append(PreparedLine(no, line, bd, bc))

    base_dr = sum((p.base_debit for p in prepared), Decimal(0))
    base_cr = sum((p.base_credit for p in prepared), Decimal(0))
    if base_dr != base_cr:
        raise LedgerRuleError(
            "unbalanced",
            f"journal is unbalanced in {functional_currency}: debit {base_dr} <> credit {base_cr}",
        )
    if len({p.line.currency for p in prepared}) == 1:
        dr = sum((p.line.debit for p in prepared), Decimal(0))
        cr = sum((p.line.credit for p in prepared), Decimal(0))
        if dr != cr:
            raise LedgerRuleError("unbalanced", f"journal is unbalanced: debit {dr} <> credit {cr}")
    return prepared

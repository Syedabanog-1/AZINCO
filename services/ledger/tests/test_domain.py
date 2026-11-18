"""Domain rules in code (no database): validation, base-amount maths, balance - incl. properties."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from azinco_ledger.domain import (
    MAX_AMOUNT,
    DraftIn,
    LedgerRuleError,
    LineIn,
    base_amount,
    prepare_lines,
)

ACCT_A, ACCT_B = uuid.uuid4(), uuid.uuid4()
ENTITY = uuid.uuid4()


def line(**kw: Any) -> dict[str, Any]:
    return {"account_id": ACCT_A, "currency": "PKR", "evidence_type": "system_calc", **kw}


def draft(*lines: dict[str, Any]) -> DraftIn:
    return DraftIn.model_validate(
        {
            "entity_id": ENTITY,
            "journal_date": date(2026, 3, 31),
            "description": "Synthetic",
            "source": "agent",
            "lines": list(lines),
        }
    )


# ------------------------------------------------------------------ line validation
@pytest.mark.parametrize(
    ("kw", "message"),
    [
        ({"debit": "10", "credit": "10"}, "exactly one positive side"),
        ({}, "exactly one positive side"),
        ({"debit": "-1"}, "greater than or equal to 0"),
        ({"debit": "1.00001"}, "decimal places"),
        ({"debit": 1.5}, "never a float"),
        ({"debit": "1", "currency": "pkr"}, "pattern"),
        ({"debit": "1", "fx_rate": "0"}, "greater than 0"),
        ({"debit": "1", "evidence_type": "extraction"}, "document_id"),
        ({"debit": "1", "tax_code": "GST-17"}, "rule_version_id"),
        ({"debit": "1", "base_debit": "1"}, "Extra inputs"),  # base is never accepted from callers
    ],
)
def test_bad_lines_are_rejected(kw: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        LineIn.model_validate(line(**kw))


def test_draft_needs_two_lines() -> None:
    with pytest.raises(ValidationError, match="at least 2"):
        draft(line(debit="1"))


# ------------------------------------------------------------------ prepare_lines
def test_balanced_functional_currency_journal() -> None:
    prepared = prepare_lines(
        draft(line(debit="1500.50"), line(account_id=ACCT_B, credit="1500.50")), "PKR"
    )
    assert [(p.line_no, p.base_debit, p.base_credit) for p in prepared] == [
        (1, Decimal("1500.5000"), Decimal(0)),
        (2, Decimal(0), Decimal("1500.5000")),
    ]


def test_foreign_currency_balances_in_base() -> None:
    prepared = prepare_lines(
        draft(
            line(debit="100", currency="USD", fx_rate="281.255"),
            line(account_id=ACCT_B, credit="28125.5"),
        ),
        "PKR",
    )
    assert prepared[0].base_debit == Decimal("28125.5000")


@pytest.mark.parametrize(
    ("lines", "code"),
    [
        ((line(debit="100"), line(account_id=ACCT_B, credit="99.9999")), "unbalanced"),
        (
            (line(debit="100", fx_rate="2"), line(account_id=ACCT_B, credit="200")),
            "fx_rate_not_one",
        ),
        (
            (
                line(debit="0.0001", currency="USD", fx_rate="0.0001"),
                line(account_id=ACCT_B, credit="0.0001"),
            ),
            "zero_base_amount",
        ),
    ],
)
def test_rule_errors(lines: tuple[dict[str, Any], ...], code: str) -> None:
    with pytest.raises(LedgerRuleError) as err:
        prepare_lines(draft(*lines), "PKR")
    assert err.value.code == code


def test_base_amount_rounds_half_up() -> None:
    assert base_amount(Decimal("0.0001"), Decimal("0.5")) == Decimal("0.0001")
    assert base_amount(Decimal("0.0001"), Decimal("0.4999999999")) == Decimal(0)
    with pytest.raises(LedgerRuleError):
        base_amount(MAX_AMOUNT, Decimal(2))


# ------------------------------------------------------------------ properties
amounts = st.decimals(min_value=Decimal("0.0001"), max_value=Decimal("99999999.9999"), places=4)


@given(
    debits=st.lists(amounts, min_size=1, max_size=5),
    credits=st.lists(amounts, min_size=1, max_size=5),
)
def test_property_accepted_iff_balanced(debits: list[Decimal], credits: list[Decimal]) -> None:
    lines = [line(debit=str(d)) for d in debits] + [
        line(account_id=ACCT_B, credit=str(c)) for c in credits
    ]
    balanced = sum(debits, Decimal(0)) == sum(credits, Decimal(0))
    try:
        prepare_lines(draft(*lines), "PKR")
        accepted = True
    except LedgerRuleError:
        accepted = False
    assert accepted == balanced


@given(total=amounts, parts=st.integers(min_value=1, max_value=6))
def test_property_any_exact_split_is_accepted(total: Decimal, parts: int) -> None:
    # Split the total into `parts` credits that add up exactly - always balanced.
    unit = (total / parts).quantize(Decimal("0.0001"), rounding="ROUND_DOWN")
    credits = [unit] * (parts - 1) + [total - unit * (parts - 1)]
    credits = [c for c in credits if c > 0]
    lines = [line(debit=str(total))] + [line(account_id=ACCT_B, credit=str(c)) for c in credits]
    prepared = prepare_lines(draft(*lines), "PKR")
    assert sum((p.base_credit for p in prepared), Decimal(0)) == total


@given(
    amount=amounts,
    rate=st.decimals(min_value=Decimal("0.0001"), max_value=Decimal("1000"), places=10),
)
def test_property_base_amount_is_exact_and_bounded(amount: Decimal, rate: Decimal) -> None:
    value = base_amount(amount, rate)
    assert value == value.quantize(Decimal("0.0001"))
    assert abs(value - amount * rate) <= Decimal("0.00005")

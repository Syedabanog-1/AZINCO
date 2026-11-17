"""Unit and property-based tests for azinco_common.money."""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from azinco_common.money import (
    MAX_ABS_AMOUNT,
    CurrencyMismatchError,
    Money,
    MoneyError,
    sum_money,
)

CURRENCIES = ["PKR", "USD"]
# Amounts well inside NUMERIC(20,4) so sums of a few values never overflow.
amounts = st.decimals(
    min_value=Decimal("-1000000000000"),
    max_value=Decimal("1000000000000"),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)
currencies = st.sampled_from(CURRENCIES)


# ---------------------------------------------------------------- construction
def test_float_is_rejected() -> None:
    with pytest.raises(MoneyError, match="float"):
        Money(0.1, "PKR")  # type: ignore[arg-type]


def test_bool_is_rejected() -> None:
    with pytest.raises(MoneyError):
        Money(True, "PKR")


@pytest.mark.parametrize("code", ["pkr", "PK", "PKRR", "123", "XYZ"])
def test_invalid_or_unsupported_currency(code: str) -> None:
    with pytest.raises(MoneyError):
        Money("1", code)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "abc", "1e"])
def test_invalid_amounts(value: str) -> None:
    with pytest.raises(MoneyError):
        Money(value, "USD")


def test_quantized_to_four_places_half_up() -> None:
    assert Money("1.00005", "PKR").amount == Decimal("1.0001")
    assert Money("1.00004", "PKR").amount == Decimal("1.0000")
    assert Money("-1.00005", "PKR").amount == Decimal("-1.0001")


def test_numeric_20_4_range_enforced() -> None:
    assert Money(MAX_ABS_AMOUNT, "USD").amount == MAX_ABS_AMOUNT
    with pytest.raises(MoneyError, match="NUMERIC"):
        Money("10000000000000000", "USD")


def test_str_and_storage() -> None:
    m = Money("1234567.125", "PKR")
    assert m.to_storage() == "1234567.1250"
    assert str(m) == "PKR 1,234,567.13"


# ---------------------------------------------------------------- arithmetic
def test_currency_mismatch_raises() -> None:
    with pytest.raises(CurrencyMismatchError):
        Money("1", "PKR") + Money("1", "USD")
    with pytest.raises(CurrencyMismatchError):
        _ = Money("1", "PKR") < Money("1", "USD")


def test_multiply_and_round_to_minor() -> None:
    assert Money("10.10", "USD").multiply(3).amount == Decimal("30.3000")
    assert Money("2.345", "USD").round_to_minor().amount == Decimal("2.3500")
    assert Money("2.344", "USD").round_to_minor().amount == Decimal("2.3400")


def test_sum_money_empty_is_zero() -> None:
    assert sum_money([], "PKR") == Money.zero("PKR")


@given(a=amounts, b=amounts, c=amounts, cur=currencies)
def test_addition_commutative_and_associative(a: Decimal, b: Decimal, c: Decimal, cur: str) -> None:
    x, y, z = Money(a, cur), Money(b, cur), Money(c, cur)
    assert x + y == y + x
    assert (x + y) + z == x + (y + z)


@given(a=amounts, b=amounts, cur=currencies)
def test_add_then_subtract_is_identity(a: Decimal, b: Decimal, cur: str) -> None:
    x, y = Money(a, cur), Money(b, cur)
    assert (x + y) - y == x
    assert x + (-x) == Money.zero(cur)


@given(a=amounts, cur=currencies)
def test_storage_round_trip_is_exact(a: Decimal, cur: str) -> None:
    m = Money(a, cur)
    assert Money(m.to_storage(), cur) == m


# ---------------------------------------------------------------- allocation
def test_allocate_classic_example() -> None:
    parts = Money("100", "USD").allocate([1, 1, 1])
    assert [p.amount for p in parts] == [Decimal("33.34"), Decimal("33.33"), Decimal("33.33")]


def test_allocate_rejects_bad_ratios() -> None:
    with pytest.raises(MoneyError):
        Money("1", "PKR").allocate([])
    with pytest.raises(MoneyError):
        Money("1", "PKR").allocate([0, 0])
    with pytest.raises(MoneyError):
        Money("1", "PKR").allocate([1, -1])


@given(
    a=amounts,
    cur=currencies,
    ratios=st.lists(st.integers(min_value=0, max_value=1000), min_size=1, max_size=12).filter(
        lambda r: sum(r) > 0
    ),
)
def test_allocation_never_loses_or_creates_money(a: Decimal, cur: str, ratios: list[int]) -> None:
    total = Money(a, cur)
    parts = total.allocate(ratios)
    assert len(parts) == len(ratios)
    assert sum_money(parts, cur) == total.round_to_minor()
    for part, ratio in zip(parts, ratios, strict=True):
        if ratio == 0:
            assert part.is_zero()

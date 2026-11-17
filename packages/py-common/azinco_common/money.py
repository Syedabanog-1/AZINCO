"""Exact money arithmetic for AZINCO (Project Instructions §13, BS §8.1).

Rules enforced here:
* Amounts are `decimal.Decimal`, never `float` (constructing from a float raises).
* Stored precision is 4 decimal places, matching PostgreSQL `NUMERIC(20,4)`.
* Arithmetic is only allowed between amounts of the same currency.
* Rounding is explicit (ROUND_HALF_UP) and deterministic.
* Splitting a total never loses or creates a single unit (largest-remainder allocation).

Currency conversion is deliberately NOT here: FX needs a recorded rate, source and timestamp
(BS §5.1) and lives in the FX service.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal, InvalidOperation, localcontext
from typing import Final

STORAGE_PLACES: Final = 4
STORAGE_QUANTUM: Final = Decimal(1).scaleb(-STORAGE_PLACES)  # Decimal("0.0001")
# NUMERIC(20,4) holds at most 16 integer digits.
MAX_ABS_AMOUNT: Final = Decimal("9999999999999999.9999")

# ISO 4217 minor units for currencies the platform currently supports.
MINOR_UNITS: Final[dict[str, int]] = {
    "PKR": 2,
    "USD": 2,
    "GBP": 2,
    "CAD": 2,
    "AUD": 2,
}


class MoneyError(ValueError):
    """Base error for invalid money operations."""


class CurrencyMismatchError(MoneyError):
    """Raised when combining amounts of different currencies."""


def _validate_currency(code: str) -> str:
    if not isinstance(code, str) or len(code) != 3 or not code.isalpha() or not code.isupper():
        raise MoneyError(f"invalid ISO 4217 currency code: {code!r}")
    if code not in MINOR_UNITS:
        raise MoneyError(f"unsupported currency: {code}")
    return code


def _to_decimal(value: Decimal | int | str) -> Decimal:
    if isinstance(value, bool | float):
        raise MoneyError("money amounts must not be created from float or bool")
    if not isinstance(value, Decimal | int | str):
        raise MoneyError(f"unsupported amount type: {type(value).__name__}")
    try:
        dec = Decimal(value) if not isinstance(value, Decimal) else value
    except InvalidOperation as exc:
        raise MoneyError(f"invalid amount: {value!r}") from exc
    if not dec.is_finite():
        raise MoneyError("amount must be finite")
    return dec


def _quantize(value: Decimal) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = 40
        q = value.quantize(STORAGE_QUANTUM, rounding=ROUND_HALF_UP)
    if abs(q) > MAX_ABS_AMOUNT:
        raise MoneyError("amount exceeds NUMERIC(20,4) range")
    return q


@dataclass(frozen=True, slots=True)
class Money:
    """An exact amount in one currency, quantized to 4 decimal places."""

    amount: Decimal
    currency: str

    def __init__(self, amount: Decimal | int | str, currency: str) -> None:
        object.__setattr__(self, "currency", _validate_currency(currency))
        object.__setattr__(self, "amount", _quantize(_to_decimal(amount)))

    # ------------------------------------------------------------------ constructors
    @classmethod
    def zero(cls, currency: str) -> Money:
        return cls(Decimal(0), currency)

    # ------------------------------------------------------------------ helpers
    def _same(self, other: Money) -> None:
        if not isinstance(other, Money):
            raise MoneyError(f"cannot combine Money with {type(other).__name__}")
        if other.currency != self.currency:
            raise CurrencyMismatchError(f"{self.currency} vs {other.currency}")

    @property
    def minor_units(self) -> int:
        return MINOR_UNITS[self.currency]

    # ------------------------------------------------------------------ arithmetic
    def __add__(self, other: Money) -> Money:
        self._same(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._same(other)
        return Money(self.amount - other.amount, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.amount, self.currency)

    def __abs__(self) -> Money:
        return Money(abs(self.amount), self.currency)

    def multiply(self, factor: Decimal | int | str) -> Money:
        """Multiply by an exact factor (e.g. a quantity); result is rounded to 4 places."""
        return Money(self.amount * _to_decimal(factor), self.currency)

    # ------------------------------------------------------------------ comparison
    def _cmp_key(self, other: Money) -> tuple[Decimal, Decimal]:
        self._same(other)
        return self.amount, other.amount

    def __lt__(self, other: Money) -> bool:
        a, b = self._cmp_key(other)
        return a < b

    def __le__(self, other: Money) -> bool:
        a, b = self._cmp_key(other)
        return a <= b

    def __gt__(self, other: Money) -> bool:
        a, b = self._cmp_key(other)
        return a > b

    def __ge__(self, other: Money) -> bool:
        a, b = self._cmp_key(other)
        return a >= b

    def is_zero(self) -> bool:
        return self.amount == 0

    # ------------------------------------------------------------------ rounding & display
    def round_to_minor(self) -> Money:
        """Round to the currency's minor unit (e.g. paisa / cents) with ROUND_HALF_UP."""
        quantum = Decimal(1).scaleb(-self.minor_units)
        return Money(self.amount.quantize(quantum, rounding=ROUND_HALF_UP), self.currency)

    def to_storage(self) -> str:
        """Exact string for NUMERIC(20,4) columns and JSON (never a float)."""
        return f"{self.amount:.{STORAGE_PLACES}f}"

    def __str__(self) -> str:
        return f"{self.currency} {self.round_to_minor().amount:,.{self.minor_units}f}"

    # ------------------------------------------------------------------ allocation
    def allocate(self, ratios: Sequence[int]) -> list[Money]:
        """Split into parts proportional to integer ratios, at minor-unit precision.

        The parts always sum exactly to the minor-unit-rounded total; remainders go to the
        parts with the largest fractional share (ties: earlier index first).
        """
        if not ratios or any(not isinstance(r, int) or isinstance(r, bool) for r in ratios):
            raise MoneyError("ratios must be a non-empty list of integers")
        if any(r < 0 for r in ratios) or sum(ratios) == 0:
            raise MoneyError("ratios must be non-negative with a positive sum")

        unit = Decimal(1).scaleb(-self.minor_units)
        total_units = int(self.round_to_minor().amount / unit)
        sign = -1 if total_units < 0 else 1
        remaining = abs(total_units)
        ratio_sum = sum(ratios)

        shares: list[int] = []
        fractions: list[tuple[Decimal, int]] = []
        for index, ratio in enumerate(ratios):
            exact = Decimal(remaining) * ratio / ratio_sum
            whole = int(exact.to_integral_value(rounding=ROUND_DOWN))
            shares.append(whole)
            fractions.append((exact - whole, -index))
        leftover = remaining - sum(shares)
        for _, neg_index in sorted(fractions, reverse=True)[:leftover]:
            shares[-neg_index] += 1

        return [Money(Decimal(sign * s) * unit, self.currency) for s in shares]


def sum_money(items: Sequence[Money], currency: str) -> Money:
    """Sum a sequence of Money in one currency (empty sequence -> zero)."""
    total = Money.zero(currency)
    for item in items:
        total = total + item
    return total

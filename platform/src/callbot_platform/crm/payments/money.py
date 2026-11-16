"""Stripe amount conversion — Decimal only, no floats for money."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.invoices.money import require_money, serialize_money

_MONEY_QUANTUM = Decimal("0.0001")
_CENTS = Decimal("100")


def to_stripe_cents(amount: Decimal, *, currency: str) -> int:
    """Convert major units to Stripe integer minor units (USD/CAD/EUR/GBP/AUD)."""
    cur = (currency or "USD").upper()
    if cur not in {"USD", "CAD", "EUR", "GBP", "AUD"}:
        raise CrmError("unsupported_currency", f"Unsupported payment currency: {cur}")
    cents = (amount * _CENTS).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if cents <= 0:
        raise CrmError("invalid_amount", "Stripe amount must be at least 1 cent")
    return int(cents)


def from_stripe_cents(cents: int) -> Decimal:
    return (Decimal(int(cents)) / _CENTS).quantize(
        _MONEY_QUANTUM, rounding=ROUND_HALF_UP
    )


__all__ = [
    "from_stripe_cents",
    "require_money",
    "serialize_money",
    "to_stripe_cents",
]

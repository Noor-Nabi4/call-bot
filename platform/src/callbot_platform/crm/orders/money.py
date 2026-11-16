"""Order money helpers (Decimal only)."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.orders.constants import (
    DEFAULT_CURRENCY,
    SUPPORTED_CURRENCIES,
)
from callbot_platform.crm.products.normalize import money_to_str, parse_money

_MONEY_QUANTUM = Decimal("0.0001")


def require_money(
    value: object | None, *, field: str, default: Decimal | None = None
) -> Decimal:
    if value is None:
        if default is not None:
            return default
        raise CrmError(f"invalid_{field}", f"{field} is required")
    parsed = parse_money(value, field=field)
    if parsed is None:
        raise CrmError(f"invalid_{field}", f"{field} is required")
    return parsed


def money_or_zero(value: object | None, *, field: str) -> Decimal:
    if value is None:
        return Decimal("0").quantize(_MONEY_QUANTUM)
    return require_money(value, field=field)


def normalize_currency(value: str | None) -> str:
    raw = (value or DEFAULT_CURRENCY).strip().upper()
    if len(raw) != 3 or not raw.isalpha():
        raise CrmError("invalid_currency", "Currency must be a 3-letter ISO code")
    if raw not in SUPPORTED_CURRENCIES:
        raise CrmError(
            "unsupported_currency",
            f"Currency must be one of: {', '.join(sorted(SUPPORTED_CURRENCIES))}",
        )
    return raw


def line_subtotal(unit_price: Decimal, quantity: int) -> Decimal:
    return (unit_price * Decimal(quantity)).quantize(
        _MONEY_QUANTUM, rounding=ROUND_HALF_UP
    )


def line_total(
    *,
    subtotal: Decimal,
    discount: Decimal,
    tax: Decimal,
) -> Decimal:
    if discount > subtotal:
        raise CrmError(
            "invalid_discount_total", "Line discount cannot exceed line subtotal"
        )
    return (subtotal - discount + tax).quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def compute_tax_amount(
    *, taxable: Decimal, tax_rate_percent: Decimal | None
) -> Decimal:
    """Apply product tax_rate percent to taxable amount. Not a jurisdiction engine."""
    if tax_rate_percent is None or tax_rate_percent <= 0 or taxable <= 0:
        return Decimal("0").quantize(_MONEY_QUANTUM)
    return (taxable * tax_rate_percent / Decimal("100")).quantize(
        _MONEY_QUANTUM, rounding=ROUND_HALF_UP
    )


def serialize_money(value: Decimal) -> str:
    return money_to_str(value) or "0.0000"

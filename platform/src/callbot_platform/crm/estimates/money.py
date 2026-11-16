"""Estimate money helpers — reuse Order Decimal conventions."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.estimates.constants import (
    DEFAULT_CURRENCY,
    SUPPORTED_CURRENCIES,
)
from callbot_platform.crm.orders.money import (
    compute_tax_amount,
    line_total,
    money_or_zero,
    require_money,
    serialize_money,
)
from callbot_platform.crm.products.normalize import parse_money

_MONEY_QUANTUM = Decimal("0.0001")
_QTY_QUANTUM = Decimal("0.0001")


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


def require_quantity(value: object | None) -> Decimal:
    if value is None:
        raise CrmError("invalid_quantity", "quantity is required")
    if isinstance(value, bool):
        raise CrmError("invalid_quantity", "quantity must be a positive number")
    if isinstance(value, int):
        qty = Decimal(value)
    elif isinstance(value, Decimal):
        qty = value
    elif isinstance(value, float):
        raise CrmError("invalid_quantity", "quantity must not be a float")
    else:
        try:
            qty = Decimal(str(value).strip())
        except Exception as exc:
            raise CrmError("invalid_quantity", "quantity is invalid") from exc
    if qty <= 0:
        raise CrmError("invalid_quantity", "Quantity must be positive")
    return qty.quantize(_QTY_QUANTUM, rounding=ROUND_HALF_UP)


def line_subtotal(unit_price: Decimal, quantity: Decimal) -> Decimal:
    return (unit_price * quantity).quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP)


__all__ = [
    "compute_tax_amount",
    "line_subtotal",
    "line_total",
    "money_or_zero",
    "normalize_currency",
    "parse_money",
    "require_money",
    "require_quantity",
    "serialize_money",
]

"""Integer-micros money helpers — never use float for ledger arithmetic."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

MICROS_PER_USD = 1_000_000


def usd_to_micros(usd: Decimal | str | float | int) -> int:
    value = Decimal(str(usd))
    if value <= 0:
        return 0
    micros = (value * Decimal(MICROS_PER_USD)).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    return int(micros)


def micros_to_usd_decimal(micros: int | None) -> Decimal | None:
    if micros is None:
        return None
    return (Decimal(int(micros)) / Decimal(MICROS_PER_USD)).quantize(
        Decimal("0.000001")
    )


def micros_to_usd_float(micros: int | None) -> float | None:
    """API serialization only — never use for further money math."""
    dec = micros_to_usd_decimal(micros)
    return float(dec) if dec is not None else None


def multiply_unit_cost(quantity: int, unit_cost_micros: int | None) -> int | None:
    if unit_cost_micros is None:
        return None
    if quantity <= 0 or unit_cost_micros <= 0:
        return 0
    return int(quantity) * int(unit_cost_micros)


def cents_to_micros(cents: int) -> int:
    return int(cents) * 10_000

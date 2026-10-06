"""Derived inventory availability status."""

from __future__ import annotations

from callbot_platform.crm.inventory.constants import (
    STATUS_IN_STOCK,
    STATUS_LOW_STOCK,
    STATUS_OUT_OF_STOCK,
)


def available_quantity(stock: int, reserved: int) -> int:
    return stock - reserved


def derive_status(*, stock: int, reserved: int, minimum_stock: int) -> str:
    avail = available_quantity(stock, reserved)
    if avail <= 0:
        return STATUS_OUT_OF_STOCK
    if avail <= minimum_stock:
        return STATUS_LOW_STOCK
    return STATUS_IN_STOCK

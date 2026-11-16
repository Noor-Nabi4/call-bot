"""Canonical request fingerprint for Order create idempotency."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any
from uuid import UUID


def _norm_money(value: object | None) -> str | None:
    if value is None:
        return None
    return str(Decimal(str(value)))


def order_create_fingerprint(
    *,
    customer_id: UUID,
    currency: str,
    shipping_total: Decimal,
    order_discount: Decimal,
    fulfillment_location_id: UUID | None,
    items: list[dict[str, Any]],
    notes: str | None,
) -> str:
    """Stable hash of material create fields (ignores actor / timestamps)."""
    normalized_items = []
    for raw in items:
        normalized_items.append(
            {
                "product_id": str(raw.get("product_id")),
                "variant_id": (
                    str(raw["variant_id"]) if raw.get("variant_id") else None
                ),
                "quantity": int(raw.get("quantity") or 0),
                "unit_price": _norm_money(raw.get("unit_price")),
                "discount_total": _norm_money(raw.get("discount_total")),
                "tax_total": _norm_money(raw.get("tax_total")),
                "sort_order": (
                    int(raw["sort_order"])
                    if raw.get("sort_order") is not None
                    else None
                ),
            }
        )
    normalized_items.sort(
        key=lambda i: (
            i["sort_order"] if i["sort_order"] is not None else 10**9,
            i["product_id"],
            i["variant_id"] or "",
        )
    )
    payload = {
        "customer_id": str(customer_id),
        "currency": currency,
        "shipping_total": str(shipping_total),
        "order_discount": str(order_discount),
        "fulfillment_location_id": (
            str(fulfillment_location_id) if fulfillment_location_id else None
        ),
        "notes": notes,
        "items": normalized_items,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

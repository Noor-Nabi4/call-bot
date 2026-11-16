"""Idempotency fingerprints for estimate create/convert."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID


def estimate_create_fingerprint(
    *,
    customer_id: UUID,
    location_id: UUID | None,
    title: str,
    currency: str,
    estimate_discount: str,
    valid_until: str | None,
    items: list[dict[str, Any]],
    notes: str | None,
    terms: str | None,
) -> str:
    payload = {
        "customer_id": str(customer_id),
        "location_id": str(location_id) if location_id else None,
        "title": title,
        "currency": currency,
        "estimate_discount": estimate_discount,
        "valid_until": valid_until,
        "notes": notes,
        "terms": terms,
        "items": items,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def estimate_convert_fingerprint(*, estimate_id: UUID, target_type: str) -> str:
    payload = {"estimate_id": str(estimate_id), "target_type": target_type}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

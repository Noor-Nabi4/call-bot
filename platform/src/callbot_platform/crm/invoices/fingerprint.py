"""Idempotency fingerprints for invoice mutations."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID


def invoice_create_fingerprint(
    *,
    customer_id: UUID,
    job_id: UUID | None,
    order_id: UUID | None,
    estimate_id: UUID | None,
    currency: str,
    invoice_discount: str,
    issue_date: str,
    due_date: str,
    items: list[dict[str, Any]],
    notes: str | None,
    terms: str | None,
) -> str:
    payload = {
        "customer_id": str(customer_id),
        "job_id": str(job_id) if job_id else None,
        "order_id": str(order_id) if order_id else None,
        "estimate_id": str(estimate_id) if estimate_id else None,
        "currency": currency,
        "invoice_discount": invoice_discount,
        "issue_date": issue_date,
        "due_date": due_date,
        "notes": notes,
        "terms": terms,
        "items": items,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

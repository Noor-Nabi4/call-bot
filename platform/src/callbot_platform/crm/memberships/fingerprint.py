"""Idempotency fingerprints for membership mutations."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID


def _dump(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def subscribe_fingerprint(
    *,
    customer_id: UUID,
    plan_id: UUID,
    billing_interval: str,
) -> str:
    return _dump(
        {
            "op": "subscribe",
            "customer_id": str(customer_id),
            "plan_id": str(plan_id),
            "billing_interval": billing_interval,
        }
    )


def plan_change_fingerprint(
    *,
    membership_id: UUID,
    target_plan_id: UUID,
    billing_interval: str | None,
) -> str:
    return _dump(
        {
            "op": "plan_change",
            "membership_id": str(membership_id),
            "target_plan_id": str(target_plan_id),
            "billing_interval": billing_interval,
        }
    )

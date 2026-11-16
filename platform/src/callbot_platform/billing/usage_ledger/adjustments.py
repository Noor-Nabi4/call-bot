"""Historical corrections — never overwrite original ledger rows."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from callbot_platform.billing.usage_ledger.categories import (
    AccountingProvenance,
    BillingStatus,
    UsageType,
)
from callbot_platform.billing.usage_ledger.ledger import UsageLedgerService
from callbot_platform.db.models.usage_ledger import UsageLedgerEntry


def record_adjustment(
    session: Session,
    *,
    tenant_id: UUID,
    usage_type: UsageType | str,
    quantity_delta: int,
    original_idempotency_key: str,
    reason: str,
    actor: str,
    total_cost_micros_delta: int | None = None,
    occurred_at: datetime | None = None,
    metadata: dict[str, Any] | None = None,
) -> tuple[UsageLedgerEntry, bool]:
    """Append an adjustment row linked to an original usage event.

    ``quantity_delta`` / ``total_cost_micros_delta`` may be negative to reverse.
    """
    reason_clean = (reason or "").strip()
    if not reason_clean:
        raise ValueError("adjustment reason required")
    adj_key = f"adjustment:{original_idempotency_key}:{reason_clean[:64]}"
    meta = dict(metadata or {})
    meta.update(
        {
            "adjustment_of": original_idempotency_key,
            "reason": reason_clean,
            "actor": actor,
        }
    )
    ledger = UsageLedgerService(session)
    # Absolute quantity for storage constraints (>=0): store abs and sign in meta.
    qty = abs(int(quantity_delta))
    meta["quantity_delta_signed"] = int(quantity_delta)
    if total_cost_micros_delta is not None:
        meta["total_cost_micros_delta_signed"] = int(total_cost_micros_delta)

    return ledger.record(
        tenant_id=tenant_id,
        usage_type=usage_type,
        quantity=qty,
        idempotency_key=adj_key[:255],
        source_type="adjustment",
        source_id=original_idempotency_key[:128],
        occurred_at=occurred_at,
        provider="system",
        usage_provenance=AccountingProvenance.ACTUAL_INTERNAL,
        cost_provenance=(
            AccountingProvenance.CONFIGURED_RATE
            if total_cost_micros_delta is not None
            else AccountingProvenance.UNAVAILABLE
        ),
        billing_status=BillingStatus.ADJUSTED,
        total_cost_micros_override=(
            abs(int(total_cost_micros_delta))
            if total_cost_micros_delta is not None
            else None
        ),
        entry_kind="adjustment",
        metadata=meta,
    )

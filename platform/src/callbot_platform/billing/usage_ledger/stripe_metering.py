"""Future Stripe metering boundary — usage detected != usage billed/paid.

Does NOT send live Stripe meter events. Provides an idempotent contract for
when metered overage invoicing is wired.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID

from callbot_platform.billing.usage_ledger.categories import BillingStatus


class MeteringWireStatus(StrEnum):
    NOT_WIRED = "NOT_WIRED"
    READY = "READY"
    SENT = "SENT"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class BillableUsageCandidate:
    """Ledger → Stripe meter candidate (never auto-sent while NOT_WIRED)."""

    tenant_id: UUID
    usage_type: str
    quantity: int
    unit: str
    idempotency_key: str
    billing_period: str
    ledger_entry_id: UUID | None
    billing_status: str = BillingStatus.ESTIMATED.value


@dataclass(frozen=True, slots=True)
class MeteringResult:
    wired: bool
    status: MeteringWireStatus
    billable: BillableUsageCandidate | None
    stripe_event_id: str | None
    note: str


class StripeMeteringGateway:
    """Integration boundary for future Stripe meters.

    Flow when wired:
      usage ledger entry → billable usage → Stripe meter/event → invoice → actual revenue

    Current behavior: returns NOT_WIRED without side effects.
    """

    def __init__(self, *, enabled: bool = False) -> None:
        self._enabled = enabled

    @property
    def wired(self) -> bool:
        return self._enabled

    def status(self) -> dict[str, Any]:
        return {
            "wired": self._enabled,
            "status": (
                MeteringWireStatus.READY.value
                if self._enabled
                else MeteringWireStatus.NOT_WIRED.value
            ),
            "note": (
                "Stripe metered overage is not considered actual revenue until "
                "Stripe invoicing/metering confirms it. Estimated overage remains "
                "ESTIMATED / UNBILLED."
            ),
            "pipeline": [
                "usage_ledger_entry",
                "billable_usage",
                "stripe_meter_event",
                "stripe_invoice",
                "actual_revenue",
            ],
        }

    def enqueue_billable_usage(
        self, candidate: BillableUsageCandidate
    ) -> MeteringResult:
        """Idempotent enqueue — no-op while metering is not wired.

        Callers must pass a stable idempotency_key (typically the ledger key).
        """
        if not candidate.idempotency_key:
            raise ValueError("idempotency_key required")
        if not self._enabled:
            return MeteringResult(
                wired=False,
                status=MeteringWireStatus.NOT_WIRED,
                billable=candidate,
                stripe_event_id=None,
                note=(
                    "Metering not wired — candidate retained as ESTIMATED overage only. "
                    f"key={candidate.idempotency_key}"
                ),
            )
        # Future: call Stripe Billing Meters API with idempotency_key.
        return MeteringResult(
            wired=True,
            status=MeteringWireStatus.READY,
            billable=candidate,
            stripe_event_id=None,
            note="Metering enabled but live send not implemented in this build.",
        )

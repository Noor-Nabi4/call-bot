"""Charge voice overage against the wallet when a call ends."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from callbot_platform.billing.plans import ACTIVE_SUBSCRIPTION_STATUSES, plan_by_key
from callbot_platform.billing.usage import seconds_to_billable_minutes
from callbot_platform.billing.wallet.repos import WalletRepository
from callbot_platform.billing.wallet.service import WalletError, WalletService
from callbot_platform.db.models import Call
from callbot_platform.db.models.wallet import UsageCharge

logger = logging.getLogger(__name__)


class UsageBillingService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._wallets = WalletService(session)
        self._repo = WalletRepository(session)

    def charge_call_overage(
        self,
        tenant_id: UUID,
        call_id: UUID,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        existing = self._repo.get_usage_charge_for_call(tenant_id, call_id)
        if existing is not None:
            return self._serialize(existing)

        call = self._session.get(Call, call_id)
        if call is None or call.tenant_id != tenant_id:
            return {"status": "skipped", "reason": "call_not_found"}
        if call.ended_at is None:
            return {"status": "skipped", "reason": "call_not_ended"}

        from sqlalchemy import select

        from callbot_platform.db.models.billing import TenantSubscription

        sub = self._session.scalar(
            select(TenantSubscription)
            .where(TenantSubscription.tenant_id == tenant_id)
            .with_for_update()
        )
        if sub is None or sub.status not in ACTIVE_SUBSCRIPTION_STATUSES | {"past_due"}:
            return {"status": "skipped", "reason": "subscription_inactive"}

        # Re-check after lock in case a concurrent charge won.
        existing = self._repo.get_usage_charge_for_call(tenant_id, call_id)
        if existing is not None:
            return self._serialize(existing)

        moment = now or datetime.now(UTC)
        period = f"{moment.year:04d}-{moment.month:02d}"
        seconds = int(call.billable_seconds or 0)
        minutes = seconds_to_billable_minutes(seconds)
        included_cap = int(sub.included_minutes or 0)
        consumed = int(sub.included_minutes_consumed or 0)
        remaining_included = max(0, included_cap - consumed)
        included_used = min(minutes, remaining_included)
        overage = max(0, minutes - included_used)
        rate = int(
            sub.overage_rate_cents
            or (plan_by_key(sub.plan_key) or {}).get("overage_per_minute_cents")
            or 0
        )
        amount = overage * rate

        charge = UsageCharge(
            tenant_id=tenant_id,
            call_id=call_id,
            billing_period=period,
            billable_seconds=seconds,
            billable_minutes=minutes,
            included_minutes_used=included_used,
            overage_minutes=overage,
            rate_per_minute_cents=rate,
            total_amount_cents=amount,
            status="PENDING",
        )
        self._session.add(charge)
        self._session.flush()

        # Consume included minutes even when overage is zero.
        sub.included_minutes_consumed = consumed + included_used
        self._session.flush()

        if amount <= 0:
            charge.status = "SKIPPED"
            self._session.flush()
            return self._serialize(charge)

        try:
            txn = self._wallets.debit(
                tenant_id,
                amount_cents=amount,
                idempotency_key=f"usage_charge:{tenant_id}:{call_id}",
                reference_type="USAGE",
                reference_id=str(charge.id),
                description=(f"Voice overage {overage} min @ ${rate / 100:.2f}/min"),
            )
            charge.wallet_transaction_id = txn.id
            charge.status = "CHARGED"
        except WalletError as exc:
            charge.status = "FAILED"
            logger.warning(
                "usage charge failed tenant=%s call=%s code=%s",
                tenant_id,
                call_id,
                exc.code,
            )
        self._session.flush()
        return self._serialize(charge)

    @staticmethod
    def _serialize(row: UsageCharge) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "tenant_id": str(row.tenant_id),
            "call_id": str(row.call_id),
            "billing_period": row.billing_period,
            "billable_seconds": int(row.billable_seconds),
            "billable_minutes": int(row.billable_minutes),
            "included_minutes_used": int(row.included_minutes_used),
            "overage_minutes": int(row.overage_minutes),
            "rate_per_minute_cents": int(row.rate_per_minute_cents),
            "total_amount_cents": int(row.total_amount_cents),
            "status": row.status,
            "wallet_transaction_id": (
                str(row.wallet_transaction_id) if row.wallet_transaction_id else None
            ),
        }

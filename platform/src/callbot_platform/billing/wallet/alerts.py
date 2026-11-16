"""Low / critical wallet balance alerts via notification outbox."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.billing.wallet.constants import (
    DEFAULT_CRITICAL_BALANCE_CENTS,
    DEFAULT_LOW_BALANCE_CENTS,
)
from callbot_platform.billing.wallet.repos import WalletRepository
from callbot_platform.db.models import TenantUser
from callbot_platform.scheduling.notifications import NotificationService

logger = logging.getLogger(__name__)


class WalletAlertService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = WalletRepository(session)
        self._notifications = NotificationService(session)

    def evaluate_after_balance_change(
        self,
        tenant_id: UUID,
        *,
        balance_cents: int,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        settings = self._repo.get_settings(tenant_id)
        low = int(settings.low_balance_cents if settings else DEFAULT_LOW_BALANCE_CENTS)
        critical = int(
            settings.critical_balance_cents
            if settings
            else DEFAULT_CRITICAL_BALANCE_CENTS
        )
        moment = now or datetime.now(UTC)
        day = moment.date().isoformat()
        fired: list[dict[str, Any]] = []

        if balance_cents <= critical:
            if self._notify(
                tenant_id,
                level="critical",
                balance_cents=balance_cents,
                threshold_cents=critical,
                day=day,
            ):
                fired.append(
                    {
                        "level": "critical",
                        "balance_cents": balance_cents,
                        "threshold_cents": critical,
                    }
                )
        elif balance_cents <= low and self._notify(
            tenant_id,
            level="low",
            balance_cents=balance_cents,
            threshold_cents=low,
            day=day,
        ):
            fired.append(
                {
                    "level": "low",
                    "balance_cents": balance_cents,
                    "threshold_cents": low,
                }
            )
        return fired

    def scan_all_wallets(self, *, limit: int = 200) -> dict[str, Any]:
        """Used by renewal/ops jobs to catch tenants that crossed thresholds."""
        from callbot_platform.db.models.wallet import Wallet

        wallets = list(
            self._session.scalars(
                select(Wallet)
                .where(Wallet.status == "ACTIVE")
                .order_by(Wallet.available_balance_cents.asc())
                .limit(limit)
            ).all()
        )
        fired = 0
        for wallet in wallets:
            events = self.evaluate_after_balance_change(
                wallet.tenant_id,
                balance_cents=int(wallet.available_balance_cents),
            )
            fired += len(events)
        return {"examined": len(wallets), "alerts_fired": fired}

    def _notify(
        self,
        tenant_id: UUID,
        *,
        level: str,
        balance_cents: int,
        threshold_cents: int,
        day: str,
    ) -> bool:
        email = self._billing_contact_email(tenant_id)
        if not email:
            logger.info(
                "wallet_%s_balance_no_contact tenant=%s balance=%s",
                level,
                tenant_id,
                balance_cents,
            )
            return False
        dollars = balance_cents / 100
        threshold_dollars = threshold_cents / 100
        body = (
            f"Your Call & Flow wallet balance is ${dollars:.2f} "
            f"(at or below the ${threshold_dollars:.2f} {level} threshold).\n"
            "Add funds in Settings → Billing to keep voice calls running."
        )
        try:
            self._notifications.enqueue_email(
                tenant_id=tenant_id,
                to_address=email,
                body=body,
                idempotency_key=f"wallet-{level}:{tenant_id}:{day}",
            )
            return True
        except Exception:
            logger.exception("wallet_%s_alert_failed tenant_id=%s", level, tenant_id)
            return False

    def _billing_contact_email(self, tenant_id: UUID) -> str | None:
        user = self._session.scalar(
            select(TenantUser)
            .where(
                TenantUser.tenant_id == tenant_id,
                TenantUser.is_active.is_(True),
            )
            .order_by(TenantUser.created_at.asc())
            .limit(1)
        )
        if user is None:
            return None
        email = (user.email or "").strip()
        return email or None

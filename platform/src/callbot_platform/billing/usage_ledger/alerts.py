"""Usage threshold alerts — deduped per billing period via outbox."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.billing.usage import UsageService, calendar_month_bounds
from callbot_platform.billing.usage_ledger.ledger import billing_period_for
from callbot_platform.db.models.usage_ledger import UsageAlertDelivery
from callbot_platform.scheduling.notifications import NotificationService

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLDS: tuple[int, ...] = (50, 75, 90, 100)
ALERT_KEY_VOICE = "voice_minutes"


class UsageAlertService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._usage = UsageService(session)
        self._notifications = NotificationService(session)

    def evaluate_voice_limits(
        self,
        tenant_id: UUID,
        *,
        now: datetime | None = None,
        thresholds: tuple[int, ...] = DEFAULT_THRESHOLDS,
        notify_email: str | None = None,
    ) -> list[dict[str, Any]]:
        """Emit at most one alert per threshold per billing period.

        Soft limits: does not block service (matches existing minute entitlement).
        """
        usage = self._usage.usage_summary(tenant_id, now=now)
        included = usage.get("included_minutes")
        used = int(usage.get("voice_minutes") or 0)
        if included is None or int(included) <= 0:
            return []

        pct = int((used * 100) / int(included))
        period_start, _ = calendar_month_bounds(now)
        period = billing_period_for(period_start)
        fired: list[dict[str, Any]] = []

        for threshold in sorted(thresholds):
            if pct < threshold:
                continue
            if self._already_sent(tenant_id, ALERT_KEY_VOICE, threshold, period):
                continue
            meta = {
                "used_minutes": used,
                "included_minutes": included,
                "percent": pct,
                "threshold_pct": threshold,
                "overage_minutes": usage.get("overage_minutes"),
            }
            delivered = self._record_delivery(
                tenant_id=tenant_id,
                alert_key=ALERT_KEY_VOICE,
                threshold_pct=threshold,
                billing_period=period,
                meta=meta,
            )
            if not delivered:
                continue
            if notify_email:
                try:
                    self._notifications.enqueue_email(
                        tenant_id=tenant_id,
                        to_address=notify_email,
                        body=(
                            f"Voice usage at {threshold}% of plan limit.\n"
                            f"Your organization has used {used} of {included} "
                            f"included voice minutes ({pct}%)."
                        ),
                        idempotency_key=(
                            f"usage-alert:{ALERT_KEY_VOICE}:{threshold}:{period}"
                        ),
                    )
                except Exception:
                    logger.exception(
                        "usage_alert_notify_failed tenant_id=%s threshold=%s",
                        tenant_id,
                        threshold,
                    )
            fired.append(
                {
                    "alert_key": ALERT_KEY_VOICE,
                    "threshold_pct": threshold,
                    "billing_period": period,
                    **meta,
                }
            )
        return fired

    def limit_status(
        self, tenant_id: UUID, *, now: datetime | None = None
    ) -> dict[str, Any]:
        usage = self._usage.usage_summary(tenant_id, now=now)
        included = usage.get("included_minutes")
        used = int(usage.get("voice_minutes") or 0)
        pct = None
        state = "unlimited"
        if included is not None and int(included) > 0:
            pct = int((used * 100) / int(included))
            if pct >= 100:
                state = "overage_allowed"  # soft minutes — existing plan behavior
            elif pct >= 90:
                state = "approaching_limit"
            else:
                state = "normal"
        return {
            "usage_type": ALERT_KEY_VOICE,
            "used": used,
            "limit": included,
            "percent": pct,
            "state": state,
            "overage_minutes": usage.get("overage_minutes"),
            "blocking": False,
            "note": "Voice minutes are soft limits; overage is estimated, not blocked.",
        }

    def _already_sent(
        self, tenant_id: UUID, alert_key: str, threshold: int, period: str
    ) -> bool:
        row = self._session.scalar(
            select(UsageAlertDelivery).where(
                UsageAlertDelivery.tenant_id == tenant_id,
                UsageAlertDelivery.alert_key == alert_key,
                UsageAlertDelivery.threshold_pct == threshold,
                UsageAlertDelivery.billing_period == period,
            )
        )
        return row is not None

    def _record_delivery(
        self,
        *,
        tenant_id: UUID,
        alert_key: str,
        threshold_pct: int,
        billing_period: str,
        meta: dict[str, Any],
    ) -> bool:
        row = UsageAlertDelivery(
            tenant_id=tenant_id,
            alert_key=alert_key,
            threshold_pct=threshold_pct,
            billing_period=billing_period,
            channel="outbox",
            sent_at=datetime.now(UTC),
            meta_json=meta,
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
            return True
        except IntegrityError:
            return False

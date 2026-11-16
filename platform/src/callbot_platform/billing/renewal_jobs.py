"""Enqueue durable subscription renewal sweeps for the async job worker."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.async_jobs.service import AsyncJobService
from callbot_platform.async_jobs.types import JobType
from callbot_platform.config import Settings, get_settings
from callbot_platform.db.models.async_job import AsyncJob
from callbot_platform.db.models.billing import TenantSubscription

logger = logging.getLogger(__name__)


def enqueue_subscription_renewal(
    session: Session,
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> AsyncJob | None:
    """
    Enqueue an hourly all-tenant renewal sweep.

    Job is attached to any subscription tenant for FK/idempotency; the handler
    renews every due subscription regardless of that tenant.
    """
    moment = now or datetime.now(UTC)
    host = session.scalar(
        select(TenantSubscription)
        .where(TenantSubscription.status.in_(["active", "past_due", "suspended"]))
        .limit(1)
    )
    if host is None:
        return None

    cfg = settings or get_settings()
    key = f"billing:subscription_renewal:{moment.strftime('%Y-%m-%d-%H')}"
    job = AsyncJobService(session, settings=cfg).enqueue(
        tenant_id=host.tenant_id,
        job_type=JobType.BILLING_SUBSCRIPTION_RENEWAL,
        idempotency_key=key,
        payload={"scope": "all_tenants", "enqueued_at": moment.isoformat()},
    )
    logger.info(
        "billing_renewal_job_enqueued",
        extra={"job_id": str(job.id), "idempotency_key": key},
    )
    return job


def run_renewal_and_alerts(session: Session) -> dict[str, Any]:
    """Synchronous renewal sweep + low-balance alert scan (admin / job handler)."""
    from callbot_platform.billing.subscription_wallet import SubscriptionWalletService
    from callbot_platform.billing.wallet.alerts import WalletAlertService

    renewal = SubscriptionWalletService(session).renew_due()
    alerts = WalletAlertService(session).scan_all_wallets()
    return {"renewal": renewal, "alerts": alerts}

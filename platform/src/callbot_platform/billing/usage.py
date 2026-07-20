"""Tenant usage metering for plan entitlements.

Voice minutes are derived from wall-clock call duration stored on each Call as
``billable_seconds``. Usage periods are calendar months in UTC so included
``monthly_minutes`` aligns with a predictable reporting window (independent of
Stripe invoice timing until overage invoicing is wired).
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from callbot_platform.billing.plans import entitlements_for_plan, plan_by_key
from callbot_platform.billing.repos import BillingRepository
from callbot_platform.db.models import (
    Call,
    KnowledgeArticle,
    TenantPhoneNumber,
    TenantUser,
)


def calendar_month_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Return [start, end) for the UTC calendar month containing ``now``."""
    moment = now or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    else:
        moment = moment.astimezone(UTC)
    start = datetime(moment.year, moment.month, 1, tzinfo=UTC)
    if moment.month == 12:
        end = datetime(moment.year + 1, 1, 1, tzinfo=UTC)
    else:
        end = datetime(moment.year, moment.month + 1, 1, tzinfo=UTC)
    return start, end


def compute_billable_seconds(
    started_at: datetime,
    ended_at: datetime,
) -> int:
    """Whole seconds of wall-clock duration; never negative."""
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=UTC)
    if ended_at.tzinfo is None:
        ended_at = ended_at.replace(tzinfo=UTC)
    delta = (ended_at - started_at).total_seconds()
    if delta <= 0:
        return 0
    return math.ceil(delta)


def seconds_to_billable_minutes(seconds: int) -> int:
    """Round up partial minutes (standard telephony-style included-minute math)."""
    if seconds <= 0:
        return 0
    return math.ceil(seconds / 60.0)


class UsageService:
    """Aggregate and report tenant resource + voice usage against plan limits."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._billing = BillingRepository(session)

    def usage_summary(
        self,
        tenant_id: UUID,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        period_start, period_end = calendar_month_bounds(now)
        voice_seconds = self._sum_billable_seconds(
            tenant_id, period_start=period_start, period_end=period_end
        )
        call_count = self._count_ended_calls(
            tenant_id, period_start=period_start, period_end=period_end
        )
        voice_minutes = seconds_to_billable_minutes(voice_seconds)

        sub = self._billing.get_by_tenant(tenant_id)
        plan_key = sub.plan_key if sub is not None else None
        entitlements = entitlements_for_plan(plan_key) if plan_key else None
        included = (
            int(entitlements["monthly_minutes"])
            if entitlements and "monthly_minutes" in entitlements
            else None
        )
        overage_minutes = (
            max(0, voice_minutes - included) if included is not None else 0
        )
        overage_cents = None
        if plan_key:
            plan = plan_by_key(plan_key)
            if plan is not None:
                overage_cents = int(plan.get("overage_per_minute_cents") or 0)

        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "period_kind": "calendar_month_utc",
            "plan_key": plan_key,
            "voice_seconds": voice_seconds,
            "voice_minutes": voice_minutes,
            "included_minutes": included,
            "overage_minutes": overage_minutes,
            "overage_per_minute_cents": overage_cents,
            "estimated_overage_cents": (
                overage_minutes * overage_cents if overage_cents is not None else None
            ),
            "call_count": call_count,
            "resources": self._resource_usage(tenant_id, entitlements),
        }

    def _sum_billable_seconds(
        self,
        tenant_id: UUID,
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> int:
        # Prefer stored billable_seconds; fall back to wall-clock for legacy rows.
        stored = self._session.scalar(
            select(func.coalesce(func.sum(Call.billable_seconds), 0)).where(
                Call.tenant_id == tenant_id,
                Call.ended_at.is_not(None),
                Call.ended_at >= period_start,
                Call.ended_at < period_end,
                Call.billable_seconds.is_not(None),
            )
        )
        total_stored = int(stored or 0)
        legacy_rows = self._session.scalars(
            select(Call).where(
                Call.tenant_id == tenant_id,
                Call.ended_at.is_not(None),
                Call.ended_at >= period_start,
                Call.ended_at < period_end,
                Call.billable_seconds.is_(None),
            )
        ).all()
        legacy_total = 0
        for call in legacy_rows:
            if call.ended_at is None:
                continue
            legacy_total += compute_billable_seconds(call.started_at, call.ended_at)
        return total_stored + legacy_total

    def _count_ended_calls(
        self,
        tenant_id: UUID,
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> int:
        count = self._session.scalar(
            select(func.count())
            .select_from(Call)
            .where(
                Call.tenant_id == tenant_id,
                Call.ended_at.is_not(None),
                Call.ended_at >= period_start,
                Call.ended_at < period_end,
            )
        )
        return int(count or 0)

    def _resource_usage(
        self,
        tenant_id: UUID,
        entitlements: dict[str, Any] | None,
    ) -> dict[str, Any]:
        team_users = int(
            self._session.scalar(
                select(func.count())
                .select_from(TenantUser)
                .where(
                    TenantUser.tenant_id == tenant_id,
                    TenantUser.is_active.is_(True),
                )
            )
            or 0
        )
        phone_numbers = int(
            self._session.scalar(
                select(func.count())
                .select_from(TenantPhoneNumber)
                .where(TenantPhoneNumber.tenant_id == tenant_id)
            )
            or 0
        )
        knowledge_documents = int(
            self._session.scalar(
                select(func.count())
                .select_from(KnowledgeArticle)
                .where(
                    KnowledgeArticle.tenant_id == tenant_id,
                    KnowledgeArticle.is_active.is_(True),
                )
            )
            or 0
        )
        concurrent_calls = int(
            self._session.scalar(
                select(func.count())
                .select_from(Call)
                .where(Call.tenant_id == tenant_id, Call.status == "active")
            )
            or 0
        )

        def slot(used: int, key: str) -> dict[str, int | None]:
            limit = None
            if entitlements is not None and key in entitlements:
                limit = int(entitlements[key])
            return {"used": used, "limit": limit}

        return {
            "team_users": slot(team_users, "team_users"),
            "phone_numbers": slot(phone_numbers, "phone_numbers"),
            "knowledge_documents": slot(knowledge_documents, "knowledge_documents"),
            "concurrent_calls": slot(concurrent_calls, "concurrent_calls"),
        }

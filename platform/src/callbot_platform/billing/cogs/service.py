"""Persist and aggregate per-call COGS estimates."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from callbot_platform.billing.cogs.calculator import (
    apply_livekit_agent_included_bucket,
    estimate_call_cogs,
    micros_to_usd,
)
from callbot_platform.billing.cogs.rates import CogsRates, rates_from_settings
from callbot_platform.billing.cogs.scenarios import full_scenario_report
from callbot_platform.billing.cogs.types import (
    CHANNEL_BROWSER_WEBRTC,
    CHANNEL_PSTN_SIP,
    TRANSFER_COLD,
    TRANSFER_NONE,
    TRANSFER_WARM,
    CallCogsInput,
)
from callbot_platform.billing.plans import plan_by_key
from callbot_platform.billing.usage import UsageService, calendar_month_bounds
from callbot_platform.config import Settings, get_settings
from callbot_platform.db.models import Call, CallCogs, TenantSubscription

logger = logging.getLogger(__name__)


def infer_channel(
    *,
    metrics: dict[str, Any] | None,
    telephony_provider: str | None,
) -> str:
    raw = None
    if metrics:
        raw = metrics.get("call_channel")
    if isinstance(raw, str) and raw in {CHANNEL_PSTN_SIP, CHANNEL_BROWSER_WEBRTC}:
        return raw
    if (telephony_provider or "").strip().lower() == "twilio":
        return CHANNEL_PSTN_SIP
    return CHANNEL_BROWSER_WEBRTC


def infer_transfer_kind(metrics: dict[str, Any] | None) -> str:
    if not metrics:
        return TRANSFER_NONE
    raw = metrics.get("transfer_kind")
    if isinstance(raw, str) and raw in {TRANSFER_NONE, TRANSFER_WARM, TRANSFER_COLD}:
        return raw
    if metrics.get("handoff_requested") is True:
        # Legacy: handoff without mode — treat as cold for reporting.
        return TRANSFER_COLD
    return TRANSFER_NONE


class CogsService:
    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        rates: CogsRates | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._rates = rates or rates_from_settings(self._settings)
        self._usage = UsageService(session)

    def persist_for_call(self, call: Call) -> CallCogs:
        metrics = call.metrics if isinstance(call.metrics, dict) else {}
        channel = infer_channel(
            metrics=metrics,
            telephony_provider=call.telephony_provider,
        )
        transfer_kind = infer_transfer_kind(metrics)
        openai_usage = metrics.get("openai_usage")
        if openai_usage is not None and not isinstance(openai_usage, dict):
            openai_usage = None

        estimate = estimate_call_cogs(
            CallCogsInput(
                billable_seconds=int(call.billable_seconds or 0),
                channel=channel,  # type: ignore[arg-type]
                transfer_kind=transfer_kind,  # type: ignore[arg-type]
                openai_usage=openai_usage,
            ),
            self._rates,
        )

        row = self._session.get(CallCogs, call.id)
        if row is None:
            row = CallCogs(call_id=call.id, tenant_id=call.tenant_id)
            self._session.add(row)

        row.tenant_id = call.tenant_id
        row.billable_seconds = estimate.billable_seconds
        row.channel = estimate.channel
        row.transfer_kind = estimate.transfer_kind
        row.openai_cost_micros = estimate.openai_cost_micros
        row.livekit_agent_cost_micros = estimate.livekit_agent_cost_micros
        row.livekit_sip_cost_micros = estimate.livekit_sip_cost_micros
        row.livekit_bvc_cost_micros = estimate.livekit_bvc_cost_micros
        row.twilio_origination_cost_micros = estimate.twilio_origination_cost_micros
        row.twilio_termination_cost_micros = estimate.twilio_termination_cost_micros
        row.total_estimated_cogs_micros = estimate.total_estimated_cogs_micros
        row.openai_cost_source = estimate.openai_cost_source
        row.openai_usage = estimate.openai_usage or {}
        row.rate_snapshot = estimate.rate_snapshot
        row.notes = list(estimate.notes)
        self._session.flush()
        return row

    def tenant_summary(
        self,
        tenant_id: UUID,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        period_start, period_end = calendar_month_bounds(now)
        usage = self._usage.usage_summary(tenant_id, now=now)

        totals = self._session.execute(
            select(
                func.coalesce(func.sum(CallCogs.openai_cost_micros), 0),
                func.coalesce(func.sum(CallCogs.livekit_agent_cost_micros), 0),
                func.coalesce(func.sum(CallCogs.livekit_sip_cost_micros), 0),
                func.coalesce(func.sum(CallCogs.livekit_bvc_cost_micros), 0),
                func.coalesce(func.sum(CallCogs.twilio_origination_cost_micros), 0),
                func.coalesce(func.sum(CallCogs.twilio_termination_cost_micros), 0),
                func.coalesce(func.sum(CallCogs.total_estimated_cogs_micros), 0),
                func.coalesce(func.sum(CallCogs.billable_seconds), 0),
                func.count(),
            ).where(
                CallCogs.tenant_id == tenant_id,
                CallCogs.created_at >= period_start,
                CallCogs.created_at < period_end,
            )
        ).one()

        (
            openai_m,
            agent_m,
            sip_m,
            bvc_m,
            orig_m,
            term_m,
            total_m,
            seconds,
            call_count,
        ) = (int(x or 0) for x in totals)

        vendor_minutes = float(seconds) / 60.0 if seconds > 0 else 0.0
        variable_usd = micros_to_usd(total_m)
        agent_usd = micros_to_usd(agent_m)
        agent_adj = apply_livekit_agent_included_bucket(
            agent_cost_usd=agent_usd,
            vendor_minutes=vendor_minutes,
            rates=self._rates,
        )

        plan_key = usage.get("plan_key")
        plan = plan_by_key(plan_key) if plan_key else None
        subscription_cents = int(plan["unit_amount"]) if plan else 0
        overage_cents = int(usage.get("estimated_overage_cents") or 0)
        gross_revenue_cents = subscription_cents + overage_cents
        gross_revenue_usd = gross_revenue_cents / 100.0

        fixed = {
            "livekit_fixed_monthly_usd": self._rates.livekit_fixed_monthly_usd,
            "phone_rental_monthly_usd": self._rates.phone_rental_monthly_usd,
            "sms_monthly_usd": self._rates.sms_monthly_usd,
            "total_fixed_monthly_usd": (
                self._rates.livekit_fixed_monthly_usd
                + self._rates.phone_rental_monthly_usd
                + self._rates.sms_monthly_usd
            ),
            "note": "Fixed costs are configured fleet/tenant overlays; not derived from call CDRs.",
        }

        # Gross profit uses variable voice COGS only (fixed reported separately).
        gross_profit_usd = gross_revenue_usd - variable_usd
        margin_pct = (
            (gross_profit_usd / gross_revenue_usd) * 100.0
            if gross_revenue_usd > 0
            else None
        )
        cogs_per_minute = variable_usd / vendor_minutes if vendor_minutes > 0 else None

        by_channel = self._group_totals(
            tenant_id, period_start, period_end, CallCogs.channel
        )
        by_transfer = self._group_totals(
            tenant_id, period_start, period_end, CallCogs.transfer_kind
        )

        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "period_kind": "calendar_month_utc",
            "plan_key": plan_key,
            "call_count": call_count,
            "billable_seconds": seconds,
            "vendor_minutes": vendor_minutes,
            "customer_voice_minutes": usage.get("voice_minutes"),
            "included_minutes": usage.get("included_minutes"),
            "overage_minutes": usage.get("overage_minutes"),
            "variable_cogs": {
                "openai_usd": micros_to_usd(openai_m),
                "livekit_agent_usd": agent_usd,
                "livekit_sip_usd": micros_to_usd(sip_m),
                "livekit_bvc_usd": micros_to_usd(bvc_m),
                "twilio_origination_usd": micros_to_usd(orig_m),
                "twilio_termination_usd": micros_to_usd(term_m),
                "total_usd": variable_usd,
                "cogs_per_minute_usd": cogs_per_minute,
            },
            "livekit_agent_included_adjustment": agent_adj,
            "fixed_monthly": fixed,
            "gross_revenue": {
                "subscription_cents": subscription_cents,
                "estimated_overage_cents": overage_cents,
                "total_cents": gross_revenue_cents,
                "total_usd": gross_revenue_usd,
                "note": "Overage cents are estimated in-app; Stripe metered overage is not yet invoiced.",
            },
            "gross_profit_usd": gross_profit_usd,
            "gross_margin_pct": margin_pct,
            "by_channel": by_channel,
            "by_transfer_kind": by_transfer,
            "estimated": True,
        }

    def plan_summary(self, *, now: datetime | None = None) -> dict[str, Any]:
        """Aggregate COGS across tenants grouped by plan_key."""
        period_start, period_end = calendar_month_bounds(now)
        rows = self._session.execute(
            select(
                TenantSubscription.plan_key,
                func.coalesce(func.sum(CallCogs.total_estimated_cogs_micros), 0),
                func.coalesce(func.sum(CallCogs.billable_seconds), 0),
                func.count(CallCogs.call_id),
            )
            .select_from(CallCogs)
            .join(
                TenantSubscription,
                TenantSubscription.tenant_id == CallCogs.tenant_id,
                isouter=True,
            )
            .where(
                CallCogs.created_at >= period_start,
                CallCogs.created_at < period_end,
            )
            .group_by(TenantSubscription.plan_key)
        ).all()

        plans: list[dict[str, Any]] = []
        for plan_key, total_m, seconds, count in rows:
            vendor_minutes = float(seconds or 0) / 60.0
            total_usd = micros_to_usd(int(total_m or 0))
            plans.append(
                {
                    "plan_key": plan_key,
                    "call_count": int(count or 0),
                    "billable_seconds": int(seconds or 0),
                    "vendor_minutes": vendor_minutes,
                    "total_estimated_cogs_usd": total_usd,
                    "cogs_per_minute_usd": (
                        total_usd / vendor_minutes if vendor_minutes > 0 else None
                    ),
                }
            )
        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "plans": plans,
            "estimated": True,
        }

    def scenarios(self) -> dict[str, Any]:
        return full_scenario_report(self._rates)

    def _group_totals(
        self,
        tenant_id: UUID,
        period_start: datetime,
        period_end: datetime,
        column: Any,
    ) -> list[dict[str, Any]]:
        rows = self._session.execute(
            select(
                column,
                func.coalesce(func.sum(CallCogs.total_estimated_cogs_micros), 0),
                func.coalesce(func.sum(CallCogs.billable_seconds), 0),
                func.count(),
            )
            .where(
                CallCogs.tenant_id == tenant_id,
                CallCogs.created_at >= period_start,
                CallCogs.created_at < period_end,
            )
            .group_by(column)
        ).all()
        out: list[dict[str, Any]] = []
        for key, total_m, seconds, count in rows:
            vendor_minutes = float(seconds or 0) / 60.0
            total_usd = micros_to_usd(int(total_m or 0))
            out.append(
                {
                    "key": key,
                    "call_count": int(count or 0),
                    "billable_seconds": int(seconds or 0),
                    "vendor_minutes": vendor_minutes,
                    "total_estimated_cogs_usd": total_usd,
                }
            )
        return out

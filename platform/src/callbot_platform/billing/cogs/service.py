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
from callbot_platform.billing.cogs.periods import resolve_cogs_period
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
from callbot_platform.billing.usage import (
    UsageService,
    calendar_month_bounds,
    seconds_to_billable_minutes,
)
from callbot_platform.config import Settings, get_settings
from callbot_platform.db.models import Call, CallCogs, Customer, TenantSubscription

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
        period: str = "this_month",
        start: datetime | None = None,
        end: datetime | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        period_start, period_end, period_kind = resolve_cogs_period(
            period=period, start=start, end=end, now=now
        )
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
        subscription_cents: int | None = None
        overage_cents: int | None = None
        revenue_note = "Overage cents are estimated in-app; Stripe metered overage is not yet invoiced."
        if period_kind in {"this_month", "last_month"} and plan is not None:
            subscription_cents = int(plan["unit_amount"])
            if period_kind == "this_month":
                overage_cents = int(usage.get("estimated_overage_cents") or 0)
            else:
                included = usage.get("included_minutes")
                voice_minutes = seconds_to_billable_minutes(seconds)
                overage_minutes = (
                    max(0, voice_minutes - int(included)) if included is not None else 0
                )
                rate = int(plan.get("overage_per_minute_cents") or 0)
                overage_cents = overage_minutes * rate
        else:
            revenue_note = (
                "Subscription revenue is attributed to calendar months only; "
                "rolling windows report variable COGS without inventing daily revenue."
            )

        gross_revenue_cents = (subscription_cents or 0) + (overage_cents or 0)
        gross_revenue_usd = (
            gross_revenue_cents / 100.0 if subscription_cents is not None else None
        )

        fixed = {
            "livekit_fixed_monthly_usd": self._rates.livekit_fixed_monthly_usd,
            "phone_rental_monthly_usd": self._rates.phone_rental_monthly_usd,
            "sms_monthly_usd": self._rates.sms_monthly_usd,
            "total_fixed_monthly_usd": (
                self._rates.livekit_fixed_monthly_usd
                + self._rates.phone_rental_monthly_usd
                + self._rates.sms_monthly_usd
            ),
            "note": "Configured monthly estimate — not derived from vendor invoices.",
        }

        gross_profit_usd = (
            gross_revenue_usd - variable_usd if gross_revenue_usd is not None else None
        )
        margin_pct = (
            (gross_profit_usd / gross_revenue_usd) * 100.0
            if gross_revenue_usd is not None
            and gross_profit_usd is not None
            and gross_revenue_usd > 0
            else None
        )
        cogs_per_minute = variable_usd / vendor_minutes if vendor_minutes > 0 else None
        revenue_per_minute = (
            gross_revenue_usd / vendor_minutes
            if gross_revenue_usd is not None and vendor_minutes > 0
            else None
        )

        by_channel = self._group_totals(
            tenant_id, period_start, period_end, CallCogs.channel
        )
        by_transfer = self._group_totals(
            tenant_id, period_start, period_end, CallCogs.transfer_kind
        )
        daily = self.daily_series(
            tenant_id, period_start=period_start, period_end=period_end
        )

        plan_profitability: list[dict[str, Any]] = []
        if plan_key:
            plan_profitability.append(
                {
                    "plan_key": plan_key,
                    "customers": None,
                    "call_count": call_count,
                    "vendor_minutes": vendor_minutes,
                    "revenue_usd": gross_revenue_usd,
                    "cogs_usd": variable_usd,
                    "gross_profit_usd": gross_profit_usd,
                    "gross_margin_pct": margin_pct,
                    "customers_unavailable": True,
                }
            )

        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "period_kind": period_kind,
            "plan_key": plan_key,
            "call_count": call_count,
            "billable_seconds": seconds,
            "vendor_minutes": vendor_minutes,
            "customer_voice_minutes": (
                usage.get("voice_minutes")
                if period_kind == "this_month"
                else seconds_to_billable_minutes(seconds)
            ),
            "included_minutes": usage.get("included_minutes"),
            "overage_minutes": (
                usage.get("overage_minutes") if period_kind == "this_month" else None
            ),
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
                "total_cents": (
                    gross_revenue_cents if subscription_cents is not None else None
                ),
                "total_usd": gross_revenue_usd,
                "revenue_per_minute_usd": revenue_per_minute,
                "note": revenue_note,
            },
            "gross_profit_usd": gross_profit_usd,
            "gross_margin_pct": margin_pct,
            "by_channel": by_channel,
            "by_transfer_kind": by_transfer,
            "daily_series": daily,
            "plan_profitability": plan_profitability,
            "estimated": True,
        }

    def daily_series(
        self,
        tenant_id: UUID,
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> list[dict[str, Any]]:
        day_expr = func.date(CallCogs.created_at)
        rows = self._session.execute(
            select(
                day_expr,
                func.coalesce(func.sum(CallCogs.total_estimated_cogs_micros), 0),
                func.coalesce(func.sum(CallCogs.billable_seconds), 0),
                func.count(),
            )
            .where(
                CallCogs.tenant_id == tenant_id,
                CallCogs.created_at >= period_start,
                CallCogs.created_at < period_end,
            )
            .group_by(day_expr)
            .order_by(day_expr)
        ).all()
        out: list[dict[str, Any]] = []
        for day, total_m, seconds, count in rows:
            vendor_minutes = float(seconds or 0) / 60.0
            out.append(
                {
                    "date": str(day),
                    "call_count": int(count or 0),
                    "billable_seconds": int(seconds or 0),
                    "vendor_minutes": vendor_minutes,
                    "cogs_usd": micros_to_usd(int(total_m or 0)),
                    "revenue_usd": None,
                    "gross_profit_usd": None,
                    "gross_margin_pct": None,
                    "note": "Daily revenue attribution is unavailable; use period KPIs.",
                }
            )
        return out

    def list_call_cogs(
        self,
        tenant_id: UUID,
        *,
        period: str = "this_month",
        start: datetime | None = None,
        end: datetime | None = None,
        channel: str | None = None,
        transfer_kind: str | None = None,
        call_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        period_start, period_end, period_kind = resolve_cogs_period(
            period=period, start=start, end=end, now=now
        )
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))

        filters = [
            CallCogs.tenant_id == tenant_id,
            CallCogs.created_at >= period_start,
            CallCogs.created_at < period_end,
        ]
        if channel in {CHANNEL_PSTN_SIP, CHANNEL_BROWSER_WEBRTC}:
            filters.append(CallCogs.channel == channel)
        if transfer_kind in {TRANSFER_NONE, TRANSFER_WARM, TRANSFER_COLD}:
            filters.append(CallCogs.transfer_kind == transfer_kind)
        if call_id:
            try:
                filters.append(CallCogs.call_id == UUID(str(call_id).strip()))
            except ValueError as exc:
                raise ValueError("invalid call_id") from exc

        total = int(
            self._session.scalar(
                select(func.count()).select_from(CallCogs).where(*filters)
            )
            or 0
        )
        rows = self._session.execute(
            select(CallCogs, Call, Customer)
            .join(Call, Call.id == CallCogs.call_id)
            .outerjoin(Customer, Customer.id == Call.customer_id)
            .where(*filters)
            .order_by(CallCogs.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()

        items = [
            self._serialize_call_cogs(cogs, call, customer)
            for cogs, call, customer in rows
        ]
        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "period_kind": period_kind,
            "total": total,
            "limit": limit,
            "offset": offset,
            "calls": items,
            "estimated": True,
            "note": (
                "Per-call revenue/profit are unavailable; subscription revenue is "
                "not allocated per call."
            ),
        }

    def get_call_cogs(self, tenant_id: UUID, call_id: UUID) -> dict[str, Any] | None:
        row = self._session.execute(
            select(CallCogs, Call, Customer)
            .join(Call, Call.id == CallCogs.call_id)
            .outerjoin(Customer, Customer.id == Call.customer_id)
            .where(CallCogs.tenant_id == tenant_id, CallCogs.call_id == call_id)
        ).first()
        if row is None:
            return None
        cogs, call, customer = row
        return self._serialize_call_cogs(cogs, call, customer, detail=True)

    def _serialize_call_cogs(
        self,
        cogs: CallCogs,
        call: Call,
        customer: Customer | None,
        *,
        detail: bool = False,
    ) -> dict[str, Any]:
        vendor_minutes = (
            float(cogs.billable_seconds) / 60.0 if cogs.billable_seconds > 0 else 0.0
        )
        payload: dict[str, Any] = {
            "id": str(cogs.call_id),
            "call_id": str(cogs.call_id),
            "tenant_id": str(cogs.tenant_id),
            "customer_id": str(call.customer_id) if call.customer_id else None,
            "customer_name": customer.name if customer is not None else None,
            "started_at": call.started_at.isoformat() if call.started_at else None,
            "ended_at": call.ended_at.isoformat() if call.ended_at else None,
            "channel": cogs.channel,
            "transfer_kind": cogs.transfer_kind,
            "billable_seconds": cogs.billable_seconds,
            "vendor_minutes": vendor_minutes,
            "openai_cost_usd": micros_to_usd(cogs.openai_cost_micros),
            "livekit_agent_cost_usd": micros_to_usd(cogs.livekit_agent_cost_micros),
            "livekit_sip_cost_usd": micros_to_usd(cogs.livekit_sip_cost_micros),
            "livekit_bvc_cost_usd": micros_to_usd(cogs.livekit_bvc_cost_micros),
            "twilio_origination_cost_usd": micros_to_usd(
                cogs.twilio_origination_cost_micros
            ),
            "twilio_termination_cost_usd": micros_to_usd(
                cogs.twilio_termination_cost_micros
            ),
            "total_estimated_cogs_usd": micros_to_usd(cogs.total_estimated_cogs_micros),
            "openai_cost_source": cogs.openai_cost_source,
            "revenue_usd": None,
            "gross_profit_usd": None,
            "gross_margin_pct": None,
            "created_at": cogs.created_at.isoformat() if cogs.created_at else None,
            "estimated": True,
        }
        if detail:
            payload["openai_usage"] = cogs.openai_usage or {}
            payload["rate_snapshot"] = cogs.rate_snapshot or {}
            payload["notes"] = cogs.notes or []
            payload["caller_number"] = call.caller_number
            payload["called_number"] = call.called_number
            payload["status"] = call.status
            payload["room_name"] = call.room_name
        return payload

    def plan_summary(self, *, now: datetime | None = None) -> dict[str, Any]:
        """Fleet rollup — not exposed to tenant admins (cross-tenant leak risk)."""
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
                    "customers": None,
                    "revenue_usd": None,
                    "gross_profit_usd": None,
                    "gross_margin_pct": None,
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
                    "cogs_per_minute_usd": (
                        total_usd / vendor_minutes if vendor_minutes > 0 else None
                    ),
                    "revenue_usd": None,
                    "gross_profit_usd": None,
                }
            )
        return out

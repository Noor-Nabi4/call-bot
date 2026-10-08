"""Usage/COGS aggregations with explicit accounting provenance."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from callbot_platform.billing.plans import plan_by_key
from callbot_platform.billing.usage import UsageService, calendar_month_bounds
from callbot_platform.billing.usage_ledger.categories import (
    AccountingProvenance,
    BillingStatus,
    UsageType,
    cost_basis_to_provenance,
)
from callbot_platform.billing.usage_ledger.money import (
    cents_to_micros,
    micros_to_usd_float,
)
from callbot_platform.db.models import Tenant, TenantSubscription
from callbot_platform.db.models.usage_ledger import UsageLedgerEntry


def _money(micros: int | None, *, provenance: AccountingProvenance) -> dict[str, Any]:
    return {
        "usd": micros_to_usd_float(micros),
        "micros": micros,
        "provenance": provenance.value,
        "available": micros is not None
        and provenance != AccountingProvenance.UNAVAILABLE,
    }


class UsageCostAggregationService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._usage = UsageService(session)

    def customer_usage_summary(
        self,
        tenant_id: UUID,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Customer-facing usage/limits only — never platform COGS/margin/provider costs.

        Organization Owner may call this. Platform financial fields are omitted
        at the DTO boundary (not merely hidden in the UI).
        """
        full = self.organization_summary(tenant_id, now=now)
        limits = full.get("limits") or {}
        usage = full.get("usage") or {}
        rev = full.get("revenue") or {}
        daily = full.get("daily_series") or []
        return {
            "period_start": full.get("period_start"),
            "period_end": full.get("period_end"),
            "period_kind": full.get("period_kind"),
            "plan_key": full.get("plan_key"),
            "usage": {
                "voice_minutes": usage.get("voice_minutes", 0),
                "llm_input_tokens": usage.get("llm_input_tokens", 0),
                "llm_output_tokens": usage.get("llm_output_tokens", 0),
                "ai_requests": usage.get("ai_requests", 0),
                "tool_calls": usage.get("tool_calls", 0),
                "sms": usage.get("sms", 0),
                "transcription_seconds": usage.get("transcription_seconds", 0),
                "storage_bytes": usage.get("storage_bytes", 0),
                "provenance": usage.get("provenance") or {},
            },
            "limits": {
                "included_minutes": limits.get("included_minutes"),
                "voice_minutes_used": limits.get("voice_minutes_used"),
                "overage_minutes": limits.get("overage_minutes"),
                "overage_per_minute_cents": limits.get("overage_per_minute_cents"),
                "estimated_overage_cents": limits.get("estimated_overage_cents"),
            },
            "billing": {
                "currency": rev.get("currency", "usd"),
                "estimated_overage_cents": rev.get("estimated_overage_cents"),
                "estimated_overage_usd": rev.get("estimated_overage_revenue_usd"),
                "estimated_overage_status": rev.get(
                    "estimated_overage_billing_status", BillingStatus.ESTIMATED.value
                ),
                "plan_subscription_status": rev.get("stripe_subscription_status"),
                "note": (
                    "Estimated overage is usage above plan limits and is not a "
                    "finalized invoice. Provider COGS and platform margin are not "
                    "included in customer billing views."
                ),
            },
            "daily_series": [
                {
                    "date": d.get("date"),
                    "usage": d.get("usage") or {},
                }
                for d in daily
            ],
            "stripe_metering": {
                "wired": False,
                "status": "NOT_WIRED",
                "note": (
                    "Estimated overage reflects detected usage, not Stripe-invoiced "
                    "charges, until metering is connected."
                ),
            },
            "boundary": "organization",
        }

    def organization_summary(
        self,
        tenant_id: UUID,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Full platform accounting view for one tenant (COGS/margin included).

        Must only be served on platform-operator routes — never to org sessions.
        """
        period_start, period_end = calendar_month_bounds(now)
        usage = self._usage.usage_summary(tenant_id, now=now)
        by_type = self._aggregate_types(
            tenant_id, period_start=period_start, period_end=period_end
        )
        daily = self._daily_series(
            tenant_id, period_start=period_start, period_end=period_end
        )
        cost_buckets = self._cost_buckets(by_type)

        voice = by_type.get(UsageType.VOICE_MINUTES.value)
        llm_in = by_type.get(UsageType.LLM_INPUT_TOKENS.value)
        llm_out = by_type.get(UsageType.LLM_OUTPUT_TOKENS.value)
        sms = by_type.get(UsageType.SMS.value)
        tx = by_type.get(UsageType.TRANSCRIPTION.value)
        storage = by_type.get(UsageType.STORAGE.value)
        infra = by_type.get(UsageType.INFRASTRUCTURE.value)

        llm_cost = _sum_nullable(
            llm_in.get("cost_micros") if llm_in else None,
            llm_out.get("cost_micros") if llm_out else None,
        )

        # Infrastructure: missing row => UNAVAILABLE (never fabricate $0).
        infra_micros = infra.get("cost_micros") if infra else None
        infra_prov = (
            AccountingProvenance.ALLOCATED_COST
            if infra is not None and infra_micros is not None
            else AccountingProvenance.UNAVAILABLE
        )

        cost = {
            "voice": _money(
                voice.get("cost_micros") if voice else None,
                provenance=AccountingProvenance.CONFIGURED_RATE
                if voice and voice.get("cost_micros") is not None
                else AccountingProvenance.UNAVAILABLE,
            ),
            "llm": _money(
                llm_cost,
                provenance=AccountingProvenance.CONFIGURED_RATE
                if llm_cost is not None
                else AccountingProvenance.UNAVAILABLE,
            ),
            "sms": _money(
                sms.get("cost_micros") if sms else None,
                provenance=AccountingProvenance.CONFIGURED_RATE
                if sms and sms.get("cost_micros") is not None
                else AccountingProvenance.UNAVAILABLE,
            ),
            "transcription": _money(
                tx.get("cost_micros") if tx else None,
                provenance=AccountingProvenance.CONFIGURED_RATE
                if tx and tx.get("cost_micros") is not None
                else AccountingProvenance.UNAVAILABLE,
            ),
            "storage": _money(
                storage.get("cost_micros") if storage else None,
                provenance=AccountingProvenance.CONFIGURED_RATE
                if storage and storage.get("cost_micros") is not None
                else AccountingProvenance.UNAVAILABLE,
            ),
            "infrastructure": _money(infra_micros, provenance=infra_prov),
            "buckets": cost_buckets,
            "note": (
                "Configured-rate COGS = actual/internal usage x snapshotted rates. "
                "Not vendor invoices unless provenance=ACTUAL_PROVIDER."
            ),
        }

        # Totals by certainty — never coerce UNAVAILABLE to 0.
        configured_cogs = cost_buckets["configured_rate"]["micros"]
        allocated_cogs = cost_buckets["allocated"]["micros"]
        actual_provider_cogs = cost_buckets["actual_provider"]["micros"]
        calculated_cogs_parts = [
            p
            for p in (configured_cogs, allocated_cogs, actual_provider_cogs)
            if p is not None
        ]
        calculated_cogs = sum(calculated_cogs_parts) if calculated_cogs_parts else None

        revenue = self._revenue_block(tenant_id, usage)
        margin = self._margin_block(revenue, calculated_cogs, actual_provider_cogs)

        # Compat fields for existing UI (explicitly labeled in panel).
        compat_cost = {
            "voice_usd": cost["voice"]["usd"],
            "llm_usd": cost["llm"]["usd"],
            "sms_usd": cost["sms"]["usd"],
            "transcription_usd": cost["transcription"]["usd"],
            "storage_usd": cost["storage"]["usd"],
            "infrastructure_usd": cost["infrastructure"]["usd"],
            "total_cogs_usd": micros_to_usd_float(calculated_cogs),
            "cost_basis_note": cost["note"],
            "provenance": {
                "voice": cost["voice"]["provenance"],
                "llm": cost["llm"]["provenance"],
                "sms": cost["sms"]["provenance"],
                "transcription": cost["transcription"]["provenance"],
                "storage": cost["storage"]["provenance"],
                "infrastructure": cost["infrastructure"]["provenance"],
            },
        }

        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "period_kind": "calendar_month_utc",
            "plan_key": usage.get("plan_key"),
            "usage": {
                "voice_minutes": (voice or {}).get(
                    "quantity", usage.get("voice_minutes", 0)
                ),
                "llm_input_tokens": (llm_in or {}).get("quantity", 0),
                "llm_output_tokens": (llm_out or {}).get("quantity", 0),
                "ai_requests": by_type.get(UsageType.AI_REQUESTS.value, {}).get(
                    "quantity", 0
                ),
                "tool_calls": by_type.get(UsageType.TOOL_CALLS.value, {}).get(
                    "quantity", 0
                ),
                "sms": (sms or {}).get("quantity", 0),
                "transcription_seconds": (tx or {}).get("quantity", 0),
                "storage_bytes": (storage or {}).get("quantity", 0),
                "provenance": {
                    "voice_minutes": AccountingProvenance.ACTUAL_INTERNAL.value,
                    "llm_tokens": AccountingProvenance.ACTUAL_PROVIDER.value
                    if (llm_in or llm_out)
                    else AccountingProvenance.UNAVAILABLE.value,
                    "sms": AccountingProvenance.ACTUAL_PROVIDER.value
                    if sms
                    else AccountingProvenance.UNAVAILABLE.value,
                    "transcription": AccountingProvenance.ACTUAL_PROVIDER.value
                    if tx
                    else AccountingProvenance.UNAVAILABLE.value,
                    "storage": AccountingProvenance.ACTUAL_INTERNAL.value
                    if storage
                    else AccountingProvenance.UNAVAILABLE.value,
                },
            },
            "limits": {
                "included_minutes": usage.get("included_minutes"),
                "voice_minutes_used": usage.get("voice_minutes"),
                "overage_minutes": usage.get("overage_minutes"),
                "overage_per_minute_cents": usage.get("overage_per_minute_cents"),
                "estimated_overage_cents": usage.get("estimated_overage_cents"),
                "resources": usage.get("resources"),
            },
            "cost": compat_cost,
            "cogs": cost,
            "revenue": revenue,
            "gross_margin": margin,
            "by_type": by_type,
            "daily_series": daily,
            "billing_usage": usage,
            "stripe_metering": {
                "wired": False,
                "status": "NOT_WIRED",
                "note": (
                    "Estimated overage is usage detected, not usage billed/paid. "
                    "Stripe metering/invoicing is not connected."
                ),
            },
        }

    def _revenue_block(self, tenant_id: UUID, usage: dict[str, Any]) -> dict[str, Any]:
        plan_key = usage.get("plan_key")
        plan = plan_by_key(plan_key) if plan_key else None
        configured_sub_cents = int(plan["unit_amount"]) if plan else None
        estimated_overage_cents = usage.get("estimated_overage_cents")
        if estimated_overage_cents is not None:
            estimated_overage_cents = int(estimated_overage_cents)

        # No authoritative Stripe invoice amount store yet → actual revenue UNAVAILABLE.
        actual_cents: int | None = None
        sub = self._session.scalar(
            select(TenantSubscription).where(TenantSubscription.tenant_id == tenant_id)
        )
        stripe_status = sub.status if sub is not None else None

        return {
            "currency": "usd",
            "actual_revenue_cents": actual_cents,
            "actual_revenue_usd": (
                actual_cents / 100.0 if actual_cents is not None else None
            ),
            "actual_revenue_provenance": AccountingProvenance.UNAVAILABLE.value,
            "configured_subscription_revenue_cents": configured_sub_cents,
            "configured_subscription_revenue_usd": (
                configured_sub_cents / 100.0
                if configured_sub_cents is not None
                else None
            ),
            "configured_subscription_provenance": (
                AccountingProvenance.CONFIGURED_RATE.value
                if configured_sub_cents is not None
                else AccountingProvenance.UNAVAILABLE.value
            ),
            "estimated_overage_revenue_cents": estimated_overage_cents,
            "estimated_overage_revenue_usd": (
                estimated_overage_cents / 100.0
                if estimated_overage_cents is not None
                else None
            ),
            "estimated_overage_provenance": AccountingProvenance.ESTIMATED.value,
            "estimated_overage_billing_status": BillingStatus.ESTIMATED.value,
            # Compat — never a silent sum of actual+estimated as "revenue".
            "subscription_cents": configured_sub_cents,
            "estimated_overage_cents": estimated_overage_cents,
            "total_cents": None,
            "combined_configured_plus_estimated_cents": (
                (configured_sub_cents or 0) + int(estimated_overage_cents or 0)
                if configured_sub_cents is not None
                else None
            ),
            "stripe_subscription_status": stripe_status,
            "note": (
                "actual_revenue requires finalized Stripe invoice/payment records "
                "(not yet stored). configured_subscription_revenue is plan catalog. "
                "estimated_overage is NOT actual revenue and is NOT Stripe-invoiced."
            ),
            "source": "plan_catalog + usage_estimate; actual Stripe invoices unavailable",
        }

    def _margin_block(
        self,
        revenue: dict[str, Any],
        calculated_cogs_micros: int | None,
        actual_provider_cogs_micros: int | None,
    ) -> dict[str, Any]:
        actual_rev_cents = revenue.get("actual_revenue_cents")
        configured_sub = revenue.get("configured_subscription_revenue_cents")
        estimated_overage = revenue.get("estimated_overage_revenue_cents")

        actual_rev_micros = (
            cents_to_micros(int(actual_rev_cents))
            if actual_rev_cents is not None
            else None
        )
        # Actual gross margin only when actual revenue AND actual provider costs exist.
        actual_margin = None
        actual_margin_pct = None
        verified = False
        if actual_rev_micros is not None and actual_provider_cogs_micros is not None:
            actual_margin = actual_rev_micros - actual_provider_cogs_micros
            verified = True
            if actual_rev_micros > 0:
                actual_margin_pct = float(
                    (
                        Decimal(actual_margin)
                        / Decimal(actual_rev_micros)
                        * Decimal(100)
                    ).quantize(Decimal("0.01"))
                )

        # Calculated margin uses configured subscription only (not estimated overage).
        calc_rev_micros = (
            cents_to_micros(int(configured_sub)) if configured_sub is not None else None
        )
        calc_margin = None
        calc_margin_pct = None
        if calc_rev_micros is not None and calculated_cogs_micros is not None:
            calc_margin = calc_rev_micros - calculated_cogs_micros
            if calc_rev_micros > 0:
                calc_margin_pct = float(
                    (
                        Decimal(calc_margin) / Decimal(calc_rev_micros) * Decimal(100)
                    ).quantize(Decimal("0.01"))
                )

        return {
            "verified": verified,
            "actual_gross_margin_usd": micros_to_usd_float(actual_margin),
            "actual_gross_margin_pct": actual_margin_pct,
            "calculated_gross_margin_usd": micros_to_usd_float(calc_margin),
            "calculated_gross_margin_pct": calc_margin_pct,
            "inputs": {
                "actual_revenue_usd": revenue.get("actual_revenue_usd"),
                "configured_subscription_revenue_usd": revenue.get(
                    "configured_subscription_revenue_usd"
                ),
                "estimated_overage_revenue_usd": revenue.get(
                    "estimated_overage_revenue_usd"
                ),
                "calculated_cogs_usd": micros_to_usd_float(calculated_cogs_micros),
                "actual_provider_cogs_usd": micros_to_usd_float(
                    actual_provider_cogs_micros
                ),
                "estimated_overage_excluded_from_calculated_margin": True,
            },
            # Compat keys — map to calculated (configured) margin, not fake actual.
            "revenue_usd": revenue.get("configured_subscription_revenue_usd"),
            "cogs_usd": micros_to_usd_float(calculated_cogs_micros),
            "gross_margin_usd": micros_to_usd_float(calc_margin),
            "gross_margin_pct": calc_margin_pct,
            "note": (
                "calculated_gross_margin uses configured subscription revenue minus "
                "configured/allocated/actual-provider COGS. Estimated overage is "
                "excluded. actual_gross_margin requires Stripe invoice amounts."
            ),
            "estimated_overage_cents_for_reference": estimated_overage,
        }

    def _cost_buckets(self, by_type: dict[str, dict[str, Any]]) -> dict[str, Any]:
        buckets = {
            "actual_provider": 0,
            "configured_rate": 0,
            "allocated": 0,
            "estimated": 0,
        }
        present = dict.fromkeys(buckets, False)
        for payload in by_type.values():
            cost = payload.get("cost_micros")
            if cost is None:
                continue
            prov = AccountingProvenance(
                payload.get("cost_provenance")
                or cost_basis_to_provenance(payload.get("cost_basis")).value
            )
            if prov == AccountingProvenance.ACTUAL_PROVIDER:
                buckets["actual_provider"] += cost
                present["actual_provider"] = True
            elif prov == AccountingProvenance.CONFIGURED_RATE:
                buckets["configured_rate"] += cost
                present["configured_rate"] = True
            elif prov == AccountingProvenance.ALLOCATED_COST:
                buckets["allocated"] += cost
                present["allocated"] = True
            elif prov == AccountingProvenance.ESTIMATED:
                buckets["estimated"] += cost
                present["estimated"] = True
        return {
            "actual_provider": _money(
                buckets["actual_provider"] if present["actual_provider"] else None,
                provenance=AccountingProvenance.ACTUAL_PROVIDER,
            ),
            "configured_rate": _money(
                buckets["configured_rate"] if present["configured_rate"] else None,
                provenance=AccountingProvenance.CONFIGURED_RATE,
            ),
            "allocated": _money(
                buckets["allocated"] if present["allocated"] else None,
                provenance=AccountingProvenance.ALLOCATED_COST,
            ),
            "estimated": _money(
                buckets["estimated"] if present["estimated"] else None,
                provenance=AccountingProvenance.ESTIMATED,
            ),
            "unavailable": {
                "usd": None,
                "micros": None,
                "provenance": AccountingProvenance.UNAVAILABLE.value,
                "available": False,
            },
        }

    def fleet_summary(self, *, now: datetime | None = None) -> dict[str, Any]:
        """Cross-tenant COGS rollup — internal/admin only; estimated vs configured labeled."""
        period_start, period_end = calendar_month_bounds(now)
        rows = self._session.execute(
            select(
                UsageLedgerEntry.tenant_id,
                Tenant.name,
                TenantSubscription.plan_key,
                UsageLedgerEntry.usage_type,
                UsageLedgerEntry.cost_basis,
                func.coalesce(func.sum(UsageLedgerEntry.quantity), 0),
                func.sum(UsageLedgerEntry.total_cost_micros),
            )
            .select_from(UsageLedgerEntry)
            .join(Tenant, Tenant.id == UsageLedgerEntry.tenant_id)
            .outerjoin(
                TenantSubscription,
                TenantSubscription.tenant_id == UsageLedgerEntry.tenant_id,
            )
            .where(
                UsageLedgerEntry.occurred_at >= period_start,
                UsageLedgerEntry.occurred_at < period_end,
            )
            .group_by(
                UsageLedgerEntry.tenant_id,
                Tenant.name,
                TenantSubscription.plan_key,
                UsageLedgerEntry.usage_type,
                UsageLedgerEntry.cost_basis,
            )
        ).all()

        orgs: dict[str, dict[str, Any]] = {}
        composition: dict[str, dict[str, int]] = {}
        for tenant_id, name, plan_key, usage_type, cost_basis, qty, cost_m in rows:
            key = str(tenant_id)
            bucket = orgs.setdefault(
                key,
                {
                    "tenant_id": key,
                    "organization_name": name,
                    "plan_key": plan_key,
                    "configured_cogs_micros": 0,
                    "allocated_cogs_micros": 0,
                    "actual_provider_cogs_micros": 0,
                    "by_type": {},
                },
            )
            cost = int(cost_m) if cost_m is not None else None
            prov = cost_basis_to_provenance(cost_basis)
            if cost is not None:
                if prov == AccountingProvenance.CONFIGURED_RATE:
                    bucket["configured_cogs_micros"] += cost
                elif prov == AccountingProvenance.ALLOCATED_COST:
                    bucket["allocated_cogs_micros"] += cost
                elif prov == AccountingProvenance.ACTUAL_PROVIDER:
                    bucket["actual_provider_cogs_micros"] += cost
                composition.setdefault(usage_type, {"configured": 0, "allocated": 0})
                if prov == AccountingProvenance.CONFIGURED_RATE:
                    composition[usage_type]["configured"] += cost
                elif prov == AccountingProvenance.ALLOCATED_COST:
                    composition[usage_type]["allocated"] += cost
            bucket["by_type"][usage_type] = {
                "quantity": int(qty or 0),
                "cost_usd": micros_to_usd_float(cost),
                "cost_provenance": prov.value,
            }

        ranking = []
        for row in orgs.values():
            total = (
                row["configured_cogs_micros"]
                + row["allocated_cogs_micros"]
                + row["actual_provider_cogs_micros"]
            )
            ranking.append(
                {
                    "tenant_id": row["tenant_id"],
                    "organization_name": row["organization_name"],
                    "plan_key": row["plan_key"],
                    "configured_cogs_usd": micros_to_usd_float(
                        row["configured_cogs_micros"] or None
                    ),
                    "allocated_cogs_usd": micros_to_usd_float(
                        row["allocated_cogs_micros"] or None
                    ),
                    "actual_provider_cogs_usd": micros_to_usd_float(
                        row["actual_provider_cogs_micros"] or None
                    ),
                    "total_calculated_cogs_usd": micros_to_usd_float(total or None),
                    "by_type": row["by_type"],
                    "actual_revenue_usd": None,
                    "actual_revenue_provenance": AccountingProvenance.UNAVAILABLE.value,
                    "note": "Fleet totals are calculated/configured COGS — not Stripe invoices.",
                }
            )
        ranking.sort(key=lambda o: o["total_calculated_cogs_usd"] or 0.0, reverse=True)

        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "organizations": ranking,
            "composition": {
                k: {
                    "configured_usd": micros_to_usd_float(v["configured"] or None),
                    "allocated_usd": micros_to_usd_float(v["allocated"] or None),
                }
                for k, v in composition.items()
            },
            "total_cogs_usd": micros_to_usd_float(
                sum(
                    (o["configured_cogs_micros"] or 0)
                    + (o["allocated_cogs_micros"] or 0)
                    + (o["actual_provider_cogs_micros"] or 0)
                    for o in orgs.values()
                )
                or None
            ),
            "estimated": True,
            "actual_revenue_aggregated": False,
            "note": (
                "Estimated overage is never aggregated into actual revenue. "
                "actual_revenue remains unavailable until Stripe invoice amounts are stored."
            ),
        }

    def _aggregate_types(
        self,
        tenant_id: UUID,
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> dict[str, dict[str, Any]]:
        rows = self._session.execute(
            select(
                UsageLedgerEntry.usage_type,
                UsageLedgerEntry.cost_basis,
                UsageLedgerEntry.usage_provenance,
                func.coalesce(func.sum(UsageLedgerEntry.quantity), 0),
                func.sum(UsageLedgerEntry.total_cost_micros),
                func.count(),
            )
            .where(
                UsageLedgerEntry.tenant_id == tenant_id,
                UsageLedgerEntry.occurred_at >= period_start,
                UsageLedgerEntry.occurred_at < period_end,
                UsageLedgerEntry.entry_kind.in_(["usage", "adjustment"]),
            )
            .group_by(
                UsageLedgerEntry.usage_type,
                UsageLedgerEntry.cost_basis,
                UsageLedgerEntry.usage_provenance,
            )
        ).all()
        out: dict[str, dict[str, Any]] = {}
        for usage_type, cost_basis, usage_prov, qty, cost_m, count in rows:
            cost = int(cost_m) if cost_m is not None else None
            prev = out.get(usage_type)
            if prev is None:
                out[usage_type] = {
                    "quantity": int(qty or 0),
                    "events": int(count or 0),
                    "cost_micros": cost,
                    "cost_usd": micros_to_usd_float(cost),
                    "cost_basis": cost_basis,
                    "cost_provenance": cost_basis_to_provenance(cost_basis).value,
                    "usage_provenance": usage_prov
                    or AccountingProvenance.ACTUAL_INTERNAL.value,
                }
            else:
                prev["quantity"] += int(qty or 0)
                prev["events"] += int(count or 0)
                if cost is not None:
                    prev["cost_micros"] = int(prev["cost_micros"] or 0) + cost
                    prev["cost_usd"] = micros_to_usd_float(prev["cost_micros"])
        return out

    def _daily_series(
        self,
        tenant_id: UUID,
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> list[dict[str, Any]]:
        day_expr = func.date(UsageLedgerEntry.occurred_at)
        rows = self._session.execute(
            select(
                day_expr,
                UsageLedgerEntry.usage_type,
                func.coalesce(func.sum(UsageLedgerEntry.quantity), 0),
                func.sum(UsageLedgerEntry.total_cost_micros),
            )
            .where(
                UsageLedgerEntry.tenant_id == tenant_id,
                UsageLedgerEntry.occurred_at >= period_start,
                UsageLedgerEntry.occurred_at < period_end,
            )
            .group_by(day_expr, UsageLedgerEntry.usage_type)
            .order_by(day_expr)
        ).all()
        by_day: dict[str, dict[str, Any]] = {}
        for day, usage_type, qty, cost_m in rows:
            key = str(day)
            bucket = by_day.setdefault(
                key,
                {
                    "date": key,
                    "usage": {},
                    "cost_usd": None,
                    "_cost_micros": 0,
                    "_has_cost": False,
                },
            )
            bucket["usage"][usage_type] = int(qty or 0)
            if cost_m is not None:
                bucket["_cost_micros"] += int(cost_m)
                bucket["_has_cost"] = True
        out = []
        for bucket in by_day.values():
            has = bucket.pop("_has_cost")
            micros = bucket.pop("_cost_micros")
            bucket["cost_usd"] = micros_to_usd_float(micros if has else None)
            out.append(bucket)
        return out


def _sum_nullable(*values: int | None) -> int | None:
    present = [v for v in values if v is not None]
    if not present:
        return None
    return sum(present)

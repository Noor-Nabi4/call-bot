"""Tenant-scoped analytics aggregations (Phase 27)."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from callbot_platform.analytics.definitions import ALL_DEFINITIONS
from callbot_platform.analytics.range import (
    AnalyticsRange,
    AnalyticsRangeError,
    build_range,
    iter_local_dates,
)
from callbot_platform.billing.usage import compute_billable_seconds
from callbot_platform.crm.appointments.constants import AppointmentStatus
from callbot_platform.crm.jobs.constants import JobStatus
from callbot_platform.crm.leads.constants import LeadActivityType, LeadStatus
from callbot_platform.db.models import (
    Appointment,
    Call,
    Job,
    Lead,
    LeadActivity,
    Order,
    OrderItem,
    Payment,
    Technician,
)
from callbot_platform.scheduling.repos.settings_repo import ScheduleSettingsRepository


class AnalyticsService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def resolve_range(
        self,
        tenant_id: UUID,
        *,
        preset: str = "last_30_days",
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> AnalyticsRange:
        tz = ScheduleSettingsRepository(self._session).effective_timezone(tenant_id)
        return build_range(
            timezone=tz,
            preset=preset,
            from_date=from_date,
            to_date=to_date,
        )

    def overview(
        self,
        tenant_id: UUID,
        *,
        preset: str = "last_30_days",
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> dict[str, Any]:
        rng = self.resolve_range(
            tenant_id, preset=preset, from_date=from_date, to_date=to_date
        )
        return {
            "range": rng.as_dict(),
            "definitions": [d.as_dict() for d in ALL_DEFINITIONS],
            "calls": self._calls(tenant_id, rng),
            "sales": self._sales(tenant_id, rng),
            "operations": self._operations(tenant_id, rng),
        }

    def calls_section(
        self,
        tenant_id: UUID,
        *,
        preset: str = "last_30_days",
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> dict[str, Any]:
        rng = self.resolve_range(
            tenant_id, preset=preset, from_date=from_date, to_date=to_date
        )
        return {"range": rng.as_dict(), "calls": self._calls(tenant_id, rng)}

    def sales_section(
        self,
        tenant_id: UUID,
        *,
        preset: str = "last_30_days",
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> dict[str, Any]:
        rng = self.resolve_range(
            tenant_id, preset=preset, from_date=from_date, to_date=to_date
        )
        return {"range": rng.as_dict(), "sales": self._sales(tenant_id, rng)}

    def operations_section(
        self,
        tenant_id: UUID,
        *,
        preset: str = "last_30_days",
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> dict[str, Any]:
        rng = self.resolve_range(
            tenant_id, preset=preset, from_date=from_date, to_date=to_date
        )
        return {"range": rng.as_dict(), "operations": self._operations(tenant_id, rng)}

    # ------------------------------------------------------------------ calls

    def _calls(self, tenant_id: UUID, rng: AnalyticsRange) -> dict[str, Any]:
        call_rows = self._session.scalars(
            select(Call).where(
                Call.tenant_id == tenant_id,
                Call.started_at >= rng.starts_from,
                Call.started_at < rng.starts_to,
            )
        ).all()

        total = len(call_rows)
        ended = [c for c in call_rows if c.ended_at is not None]
        ended_count = len(ended)

        voice_seconds = 0
        transfers = 0
        reviewed = 0
        answered_reviewed = 0
        missed = 0
        abandoned = 0
        by_day: dict[str, int] = {}
        by_day_answered: dict[str, int] = {}
        by_day_missed: dict[str, int] = {}
        by_day_handoffs: dict[str, int] = {}
        by_day_ai: dict[str, int] = {}
        by_day_duration_sum: dict[str, float] = {}
        by_day_duration_n: dict[str, int] = {}
        disconnect_reasons: dict[str, int] = {}
        has_disposition_series = False

        tz = ZoneInfo(rng.timezone)
        for call in call_rows:
            local_day = call.started_at.astimezone(tz).date().isoformat()
            by_day[local_day] = by_day.get(local_day, 0) + 1

            if call.ended_at is None:
                continue
            if call.billable_seconds is not None:
                dur = float(int(call.billable_seconds))
            else:
                dur = float(
                    compute_billable_seconds(call.started_at, call.ended_at)
                )
            voice_seconds += int(dur)
            by_day_duration_sum[local_day] = (
                by_day_duration_sum.get(local_day, 0.0) + dur
            )
            by_day_duration_n[local_day] = by_day_duration_n.get(local_day, 0) + 1

            reason = (call.disconnect_reason or "unknown").strip() or "unknown"
            disconnect_reasons[reason] = disconnect_reasons.get(reason, 0) + 1

            metrics_blob = call.metrics if isinstance(call.metrics, dict) else {}
            transfer_kind = str(metrics_blob.get("transfer_kind") or "none").lower()
            is_transfer = bool(
                metrics_blob.get("handoff_requested")
                or (transfer_kind and transfer_kind != "none")
            )
            if is_transfer:
                transfers += 1
                by_day_handoffs[local_day] = by_day_handoffs.get(local_day, 0) + 1
            else:
                by_day_ai[local_day] = by_day_ai.get(local_day, 0) + 1

            disp = (call.disposition_code or "").strip().lower()
            if disp:
                has_disposition_series = True
                reviewed += 1
                if disp == "no_answer":
                    missed += 1
                    by_day_missed[local_day] = by_day_missed.get(local_day, 0) + 1
                elif disp == "abandoned":
                    abandoned += 1
                else:
                    answered_reviewed += 1
                    by_day_answered[local_day] = (
                        by_day_answered.get(local_day, 0) + 1
                    )

        avg_duration = (
            round(voice_seconds / ended_count, 1) if ended_count > 0 else None
        )
        transfer_rate = round(transfers / ended_count, 4) if ended_count > 0 else None
        ai_resolved = max(0, ended_count - transfers) if ended_count else 0
        ai_resolution_rate = (
            round(ai_resolved / ended_count, 4) if ended_count > 0 else None
        )

        if reviewed > 0:
            answer_rate: float | None = round(answered_reviewed / reviewed, 4)
            missed_value: int | None = missed
            answer_unavailable = None
            missed_unavailable = None
        else:
            answer_rate = None
            missed_value = None
            answer_unavailable = (
                "No quality disposition reviews in this period. "
                "True ring/answer rate requires telephony CDR."
            )
            missed_unavailable = answer_unavailable

        series = []
        for d in iter_local_dates(rng):
            key = d.isoformat()
            n = by_day_duration_n.get(key, 0)
            point: dict[str, Any] = {
                "date": key,
                "calls": by_day.get(key, 0),
                "ai_resolved": by_day_ai.get(key, 0),
                "handoffs": by_day_handoffs.get(key, 0),
                "avg_duration_seconds": (
                    round(by_day_duration_sum[key] / n, 1) if n > 0 else None
                ),
            }
            if has_disposition_series:
                point["answered"] = by_day_answered.get(key, 0)
                point["missed"] = by_day_missed.get(key, 0)
            series.append(point)

        # Mutually exclusive disposition composition (reviewed only).
        disposition_composition: list[dict[str, Any]] | None = None
        if reviewed > 0:
            disposition_composition = [
                {"name": "Answered", "value": answered_reviewed},
                {"name": "Missed", "value": missed},
                {"name": "Abandoned", "value": abandoned},
            ]
        # Mutually exclusive among ended: AI path vs handoff.
        resolution_composition = [
            {"name": "AI resolved", "value": ai_resolved},
            {"name": "Human handoff", "value": transfers},
        ]

        return {
            "total": total,
            "ended": ended_count,
            "answer_rate": answer_rate,
            "answer_rate_unavailable": answer_unavailable,
            "missed": missed_value,
            "missed_unavailable": missed_unavailable,
            "average_duration_seconds": avg_duration,
            "transfer_rate": transfer_rate,
            "transfers": transfers,
            "ai_resolution_rate": ai_resolution_rate,
            "ai_resolved": ai_resolved,
            "calls_by_day": series,
            "disconnect_reasons": disconnect_reasons,
            "reviewed_dispositions": reviewed,
            "disposition_composition": disposition_composition,
            "resolution_composition": resolution_composition,
            "has_disposition_series": has_disposition_series,
        }

    # ------------------------------------------------------------------ sales

    def _sales(self, tenant_id: UUID, rng: AnalyticsRange) -> dict[str, Any]:
        leads = self._session.scalars(
            select(Lead).where(
                Lead.tenant_id == tenant_id,
                Lead.archived_at.is_(None),
                Lead.created_at >= rng.starts_from,
                Lead.created_at < rng.starts_to,
            )
        ).all()
        lead_count = len(leads)
        qualified_statuses = {
            LeadStatus.QUALIFIED.value,
            LeadStatus.CONTACTED.value,
            LeadStatus.BOOKED.value,
            LeadStatus.WON.value,
        }
        converted_statuses = {LeadStatus.BOOKED.value, LeadStatus.WON.value}
        qualified = sum(1 for lead in leads if lead.status in qualified_statuses)
        converted = sum(1 for lead in leads if lead.status in converted_statuses)
        by_status: dict[str, int] = {}
        by_source: dict[str, int] = {}
        leads_by_day: dict[str, int] = {}
        qualified_by_day: dict[str, int] = {}
        tz = ZoneInfo(rng.timezone)
        for lead in leads:
            by_status[lead.status] = by_status.get(lead.status, 0) + 1
            src = (lead.source or "OTHER").strip() or "OTHER"
            by_source[src] = by_source.get(src, 0) + 1
            day = lead.created_at.astimezone(tz).date().isoformat()
            leads_by_day[day] = leads_by_day.get(day, 0) + 1
            if lead.status in qualified_statuses:
                qualified_by_day[day] = qualified_by_day.get(day, 0) + 1

        bookings = int(
            self._session.scalar(
                select(func.count())
                .select_from(Appointment)
                .where(
                    Appointment.tenant_id == tenant_id,
                    Appointment.created_at >= rng.starts_from,
                    Appointment.created_at < rng.starts_to,
                    Appointment.status != AppointmentStatus.CANCELLED.value,
                    Appointment.archived_at.is_(None),
                )
            )
            or 0
        )
        booking_appts = self._session.scalars(
            select(Appointment).where(
                Appointment.tenant_id == tenant_id,
                Appointment.created_at >= rng.starts_from,
                Appointment.created_at < rng.starts_to,
                Appointment.status != AppointmentStatus.CANCELLED.value,
                Appointment.archived_at.is_(None),
            )
        ).all()
        bookings_by_day: dict[str, int] = {}
        for a in booking_appts:
            day = a.created_at.astimezone(tz).date().isoformat()
            bookings_by_day[day] = bookings_by_day.get(day, 0) + 1

        product_sales = self._session.scalar(
            select(func.coalesce(func.sum(OrderItem.line_total), 0)).where(
                OrderItem.tenant_id == tenant_id,
                OrderItem.order_id.in_(
                    select(Order.id).where(
                        Order.tenant_id == tenant_id,
                        Order.created_at >= rng.starts_from,
                        Order.created_at < rng.starts_to,
                        Order.status.notin_(("DRAFT", "CANCELLED", "REFUNDED")),
                        Order.archived_at.is_(None),
                    )
                ),
            )
        )
        product_sales_value = float(product_sales or 0)

        # Product sales by day from qualifying orders (same exclusions).
        order_rows = self._session.scalars(
            select(Order).where(
                Order.tenant_id == tenant_id,
                Order.created_at >= rng.starts_from,
                Order.created_at < rng.starts_to,
                Order.status.notin_(("DRAFT", "CANCELLED", "REFUNDED")),
                Order.archived_at.is_(None),
            )
        ).all()
        order_ids = [o.id for o in order_rows]
        order_day = {
            o.id: o.created_at.astimezone(tz).date().isoformat() for o in order_rows
        }
        product_sales_by_day: dict[str, float] = {}
        if order_ids:
            item_rows = self._session.execute(
                select(OrderItem.order_id, OrderItem.line_total).where(
                    OrderItem.tenant_id == tenant_id,
                    OrderItem.order_id.in_(order_ids),
                )
            ).all()
            for oid, line_total in item_rows:
                day = order_day.get(oid)
                if not day:
                    continue
                product_sales_by_day[day] = product_sales_by_day.get(day, 0.0) + float(
                    line_total or 0
                )

        top_products = self._session.execute(
            select(
                OrderItem.product_id,
                OrderItem.product_name_snapshot,
                func.sum(OrderItem.quantity).label("units"),
                func.sum(OrderItem.line_total).label("revenue"),
            )
            .where(
                OrderItem.tenant_id == tenant_id,
                OrderItem.order_id.in_(
                    select(Order.id).where(
                        Order.tenant_id == tenant_id,
                        Order.created_at >= rng.starts_from,
                        Order.created_at < rng.starts_to,
                        Order.status.notin_(("DRAFT", "CANCELLED", "REFUNDED")),
                        Order.archived_at.is_(None),
                    )
                ),
            )
            .group_by(OrderItem.product_id, OrderItem.product_name_snapshot)
            .order_by(func.sum(OrderItem.line_total).desc())
            .limit(10)
        ).all()

        # Succeeded payment revenue (aggregate, not attributed)
        revenue = self._session.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.tenant_id == tenant_id,
                Payment.status == "SUCCEEDED",
                func.coalesce(Payment.succeeded_at, Payment.created_at)
                >= rng.starts_from,
                func.coalesce(Payment.succeeded_at, Payment.created_at) < rng.starts_to,
            )
        )
        revenue_value = float(revenue or 0)

        lead_series = [
            {
                "date": d.isoformat(),
                "leads": leads_by_day.get(d.isoformat(), 0),
                "qualified": qualified_by_day.get(d.isoformat(), 0),
                "bookings": bookings_by_day.get(d.isoformat(), 0),
            }
            for d in iter_local_dates(rng)
        ]
        booking_series = [
            {
                "date": d.isoformat(),
                "bookings": bookings_by_day.get(d.isoformat(), 0),
            }
            for d in iter_local_dates(rng)
        ]
        product_series = [
            {
                "date": d.isoformat(),
                "product_sales": round(
                    product_sales_by_day.get(d.isoformat(), 0.0), 4
                ),
            }
            for d in iter_local_dates(rng)
        ]

        return {
            "leads": lead_count,
            "qualified_leads": qualified,
            "qualification_rate": (
                round(qualified / lead_count, 4) if lead_count > 0 else None
            ),
            "bookings": bookings,
            "conversion_rate": (
                round(converted / lead_count, 4) if lead_count > 0 else None
            ),
            "converted_leads": converted,
            "revenue": revenue_value,
            "revenue_per_lead": None,
            "revenue_per_lead_unavailable": (
                "Lead→payment attribution is not modeled; "
                "aggregate revenue÷leads would be misleading."
            ),
            "revenue_per_call": None,
            "revenue_per_call_unavailable": (
                "Call→payment attribution is not modeled; "
                "aggregate revenue÷calls would be misleading."
            ),
            "product_sales": product_sales_value,
            "leads_by_status": by_status,
            "leads_by_source": by_source,
            "leads_by_day": lead_series,
            "bookings_by_day": booking_series,
            "product_sales_by_day": product_series,
            "top_products": [
                {
                    "product_id": str(row[0]) if row[0] else None,
                    "name": row[1],
                    "units": float(row[2] or 0),
                    "revenue": float(row[3] or 0),
                }
                for row in top_products
            ],
            "funnel": {
                "leads": lead_count,
                "qualified": qualified,
                "booked_or_won": converted,
                "bookings": bookings,
            },
        }

    # -------------------------------------------------------------- operations

    def _operations(self, tenant_id: UUID, rng: AnalyticsRange) -> dict[str, Any]:
        tz = ZoneInfo(rng.timezone)

        jobs_created = self._session.scalars(
            select(Job).where(
                Job.tenant_id == tenant_id,
                Job.created_at >= rng.starts_from,
                Job.created_at < rng.starts_to,
                Job.archived_at.is_(None),
            )
        ).all()

        completed = int(
            self._session.scalar(
                select(func.count())
                .select_from(Job)
                .where(
                    Job.tenant_id == tenant_id,
                    Job.status == JobStatus.COMPLETED.value,
                    Job.completed_at.is_not(None),
                    Job.completed_at >= rng.starts_from,
                    Job.completed_at < rng.starts_to,
                    Job.archived_at.is_(None),
                )
            )
            or 0
        )

        cancelled = sum(
            1 for j in jobs_created if j.status == JobStatus.CANCELLED.value
        )
        eligible_cancel_den = sum(
            1 for j in jobs_created if j.status != JobStatus.NEW.value
        )
        cancellation_rate = (
            round(cancelled / eligible_cancel_den, 4)
            if eligible_cancel_den > 0
            else None
        )

        job_no_show = sum(
            1 for j in jobs_created if j.status == JobStatus.NO_SHOW.value
        )
        job_terminal = sum(
            1
            for j in jobs_created
            if j.status
            in {
                JobStatus.COMPLETED.value,
                JobStatus.CANCELLED.value,
                JobStatus.NO_SHOW.value,
            }
        )
        appt_terminal_rows = self._session.scalars(
            select(Appointment).where(
                Appointment.tenant_id == tenant_id,
                Appointment.created_at >= rng.starts_from,
                Appointment.created_at < rng.starts_to,
                Appointment.status.in_(
                    (
                        AppointmentStatus.COMPLETED.value,
                        AppointmentStatus.CANCELLED.value,
                        AppointmentStatus.NO_SHOW.value,
                    )
                ),
                Appointment.archived_at.is_(None),
            )
        ).all()
        appt_no_show = sum(
            1 for a in appt_terminal_rows if a.status == AppointmentStatus.NO_SHOW.value
        )
        no_show_num = job_no_show + appt_no_show
        no_show_den = job_terminal + len(appt_terminal_rows)
        no_show_rate = round(no_show_num / no_show_den, 4) if no_show_den > 0 else None

        # Avg job duration from scheduled window on completed jobs in range
        completed_jobs = self._session.scalars(
            select(Job).where(
                Job.tenant_id == tenant_id,
                Job.status == JobStatus.COMPLETED.value,
                Job.completed_at.is_not(None),
                Job.completed_at >= rng.starts_from,
                Job.completed_at < rng.starts_to,
                Job.archived_at.is_(None),
            )
        ).all()
        duration_samples: list[float] = []
        for j in completed_jobs:
            if j.scheduled_starts_at and j.scheduled_ends_at:
                secs = (j.scheduled_ends_at - j.scheduled_starts_at).total_seconds()
                if secs > 0:
                    duration_samples.append(secs)
        avg_job_duration = (
            round(sum(duration_samples) / len(duration_samples), 1)
            if duration_samples
            else None
        )
        avg_job_unavailable = (
            None
            if duration_samples
            else "No completed jobs with scheduled start/end in this period."
        )

        # Lead response time: first CONTACTED activity - lead.created_at
        contact_acts = self._session.execute(
            select(LeadActivity.lead_id, func.min(LeadActivity.created_at))
            .where(
                LeadActivity.tenant_id == tenant_id,
                LeadActivity.activity_type == LeadActivityType.CONTACTED.value,
                LeadActivity.created_at >= rng.starts_from,
                LeadActivity.created_at < rng.starts_to,
            )
            .group_by(LeadActivity.lead_id)
        ).all()
        response_samples: list[float] = []
        if contact_acts:
            lead_ids = [row[0] for row in contact_acts]
            lead_created = {
                row.id: row.created_at
                for row in self._session.scalars(
                    select(Lead).where(
                        Lead.tenant_id == tenant_id,
                        Lead.id.in_(lead_ids),
                    )
                ).all()
            }
            for lead_id, contacted_at in contact_acts:
                created = lead_created.get(lead_id)
                if created is None or contacted_at is None:
                    continue
                delta = (contacted_at - created).total_seconds()
                if delta >= 0:
                    response_samples.append(delta)
        avg_response = (
            round(sum(response_samples) / len(response_samples), 1)
            if response_samples
            else None
        )
        response_unavailable = (
            None if response_samples else "No CONTACTED lead activities in this period."
        )

        # Jobs completed by day (tenant local)
        completed_by_day: dict[str, int] = {}
        for j in completed_jobs:
            assert j.completed_at is not None
            day = j.completed_at.astimezone(tz).date().isoformat()
            completed_by_day[day] = completed_by_day.get(day, 0) + 1
        completed_series = [
            {
                "date": d.isoformat(),
                "completed": completed_by_day.get(d.isoformat(), 0),
            }
            for d in iter_local_dates(rng)
        ]

        by_status = dict(
            self._session.execute(
                select(Job.status, func.count())
                .where(
                    Job.tenant_id == tenant_id,
                    Job.created_at >= rng.starts_from,
                    Job.created_at < rng.starts_to,
                    Job.archived_at.is_(None),
                )
                .group_by(Job.status)
            ).all()
        )

        # Technician table: assigned / completed in window (counts, not utilization %)
        tech_rows = self._session.execute(
            select(
                Job.assigned_technician_id,
                func.count().label("assigned"),
                func.sum(
                    case(
                        (Job.status == JobStatus.COMPLETED.value, 1),
                        else_=0,
                    )
                ).label("completed"),
            )
            .where(
                Job.tenant_id == tenant_id,
                Job.created_at >= rng.starts_from,
                Job.created_at < rng.starts_to,
                Job.archived_at.is_(None),
                Job.assigned_technician_id.is_not(None),
            )
            .group_by(Job.assigned_technician_id)
        ).all()

        tech_ids = [r[0] for r in tech_rows if r[0]]
        tech_names = (
            {
                t.id: t.display_name
                for t in self._session.scalars(
                    select(Technician).where(
                        Technician.tenant_id == tenant_id,
                        Technician.id.in_(tech_ids),
                    )
                ).all()
            }
            if tech_ids
            else {}
        )

        technicians = [
            {
                "technician_id": str(tid),
                "display_name": tech_names.get(tid) or "Technician",
                "assigned": int(assigned or 0),
                "completed": int(completed_count or 0),
                "utilization": None,
                "avg_duration_seconds": None,
            }
            for tid, assigned, completed_count in tech_rows
            if tid is not None
        ]

        return {
            "jobs_completed": completed,
            "jobs_created": len(jobs_created),
            "cancellation_rate": cancellation_rate,
            "cancelled_jobs": cancelled,
            "no_show_rate": no_show_rate,
            "no_show_count": no_show_num,
            "technician_utilization": None,
            "technician_utilization_unavailable": (
                "Utilization % requires clocked available hours; "
                "schedule templates alone are not production-safe."
            ),
            "average_job_duration_seconds": avg_job_duration,
            "average_job_duration_unavailable": avg_job_unavailable,
            "avg_lead_response_seconds": avg_response,
            "avg_lead_response_unavailable": response_unavailable,
            "jobs_completed_by_day": completed_series,
            "jobs_by_status": {str(k): int(v) for k, v in by_status.items()},
            "technicians": technicians,
        }


__all__ = ["AnalyticsRangeError", "AnalyticsService"]

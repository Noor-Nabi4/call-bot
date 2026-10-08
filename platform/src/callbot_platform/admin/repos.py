"""Tenant-scoped admin / analytics repositories."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from callbot_platform.billing.usage import (
    compute_billable_seconds,
    seconds_to_billable_minutes,
)
from callbot_platform.call_quality import CallQualityError, validate_quality_review
from callbot_platform.db.models import (
    Appointment,
    Call,
    Customer,
    Invoice,
    Job,
    Lead,
    Payment,
    TelephonyAuditEvent,
    TenantRetentionSettings,
    TenantUser,
)
from callbot_platform.telephony.audit import write_audit


class AdminError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class AdminRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_customers(
        self, tenant_id: UUID, *, limit: int = 100
    ) -> list[dict[str, Any]]:
        from callbot_platform.crm.customers import CustomerService

        page = CustomerService(self._session).list(
            tenant_id, include_archived=False, limit=max(1, min(limit, 200))
        )
        # Preserve legacy admin/v1 shape used by pickers and older clients.
        return [
            {
                "id": c["id"],
                "name": c["name"],
                "email": c.get("email"),
                "address": c.get("address"),
                "phones": c.get("phones") or [],
                "status": c.get("status"),
                "updated_at": c.get("updated_at"),
            }
            for c in page.get("customers") or []
        ]

    def list_calls(
        self,
        tenant_id: UUID,
        *,
        status: str | None = None,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """List tenant calls with optional status filter and keyset cursor."""
        from sqlalchemy import and_, or_

        from callbot_platform.db.cursor import CallCursor, parse_call_page

        page, decoded = parse_call_page(limit=limit, cursor=cursor)
        stmt = select(Call).where(Call.tenant_id == tenant_id)
        if status is not None:
            normalized = status.strip().lower()
            if not normalized or len(normalized) > 32:
                raise AdminError("invalid_status", "Invalid call status filter")
            stmt = stmt.where(Call.status == normalized)
        if decoded is not None:
            stmt = stmt.where(
                or_(
                    Call.started_at < decoded.started_at,
                    and_(
                        Call.started_at == decoded.started_at,
                        Call.id < decoded.id,
                    ),
                )
            )
        rows = list(
            self._session.scalars(
                stmt.order_by(Call.started_at.desc(), Call.id.desc()).limit(
                    page.limit + 1
                )
            ).all()
        )
        now = datetime.now(UTC)
        has_more = len(rows) > page.limit
        rows = rows[: page.limit]
        items = [self._serialize_call(c, now=now) for c in rows]
        next_cursor = None
        if has_more and rows:
            last = rows[-1]
            next_cursor = CallCursor(started_at=last.started_at, id=last.id).encode()
        return {"calls": items, "next_cursor": next_cursor, "limit": page.limit}

    def _serialize_call(
        self, c: Call, *, now: datetime | None = None
    ) -> dict[str, Any]:
        clock = now or datetime.now(UTC)
        metrics = c.metrics if isinstance(c.metrics, dict) else {}
        elapsed: int | None = None
        if c.started_at:
            start = c.started_at
            if start.tzinfo is None:
                start = start.replace(tzinfo=UTC)
            end = c.ended_at or clock
            if end.tzinfo is None:
                end = end.replace(tzinfo=UTC)
            elapsed = max(0, int((end - start).total_seconds()))
        return {
            "id": str(c.id),
            "room_name": c.room_name,
            "status": c.status,
            "caller_number": c.caller_number,
            "called_number": c.called_number,
            "started_at": c.started_at.isoformat() if c.started_at else None,
            "ended_at": c.ended_at.isoformat() if c.ended_at else None,
            "customer_id": str(c.customer_id) if c.customer_id else None,
            "billable_seconds": c.billable_seconds,
            "disconnect_reason": c.disconnect_reason,
            "elapsed_seconds": elapsed,
            "handoff_requested": bool(metrics.get("handoff_requested")),
            "disposition_code": c.disposition_code,
            "quality_score": c.quality_score,
            "quality_notes": c.quality_notes,
            "quality_reviewed_at": (
                c.quality_reviewed_at.isoformat() if c.quality_reviewed_at else None
            ),
            "quality_reviewed_by": c.quality_reviewed_by,
        }

    def review_call_quality(
        self,
        tenant_id: UUID,
        call_id: UUID,
        *,
        actor: str,
        quality_score: int | None = None,
        disposition_code: str | None = None,
        quality_notes: str | None = None,
    ) -> dict[str, Any]:
        """Record post-call QA for a tenant call (supervisor / admin)."""
        try:
            fields = validate_quality_review(
                quality_score=quality_score,
                disposition_code=disposition_code,
                quality_notes=quality_notes,
            )
        except CallQualityError as exc:
            raise AdminError(exc.code, str(exc)) from exc

        call = self._session.scalar(
            select(Call).where(Call.id == call_id, Call.tenant_id == tenant_id)
        )
        if call is None:
            raise AdminError("call_not_found", "Call not found for tenant")
        if call.status == "active" or call.ended_at is None:
            raise AdminError(
                "call_still_active",
                "Quality review is only allowed after the call ends",
            )

        if fields["quality_score"] is not None:
            call.quality_score = fields["quality_score"]
        if fields["disposition_code"] is not None:
            call.disposition_code = fields["disposition_code"]
        if quality_notes is not None:
            call.quality_notes = fields["quality_notes"]
        call.quality_reviewed_at = datetime.now(UTC)
        call.quality_reviewed_by = actor[:255]
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="call_quality_reviewed",
            resource_ids={"call_id": str(call.id)},
            payload_summary={
                "quality_score": call.quality_score,
                "disposition_code": call.disposition_code,
            },
        )
        return self._serialize_call(call)

    def supervisor_snapshot(
        self, tenant_id: UUID, *, recent_limit: int = 20
    ) -> dict[str, Any]:
        """Read-only call-center snapshot for supervisors (no listen-in)."""
        limit = max(1, min(recent_limit, 50))
        active = self.list_calls(tenant_id, status="active", limit=100)["calls"]
        recent_all = self.list_calls(tenant_id, limit=limit + len(active))["calls"]
        recent = [c for c in recent_all if c["status"] != "active"][:limit]
        attention = [c for c in active if c.get("handoff_requested")]
        today_metrics = self.metrics_summary(tenant_id, days=1)
        return {
            "active_calls": active,
            "recent_calls": recent,
            "attention": attention,
            "summary": {
                "calls_active": len(active),
                "handoffs_open": len(attention),
                "calls_today": int(today_metrics.get("calls") or 0),
                "handoffs_today": int(today_metrics.get("handoffs_requested") or 0),
                "avg_call_duration_seconds": float(
                    today_metrics.get("avg_call_duration_seconds") or 0
                ),
            },
        }

    def list_appointments(
        self, tenant_id: UUID, *, limit: int = 100
    ) -> list[dict[str, Any]]:
        rows = self._session.scalars(
            select(Appointment)
            .where(Appointment.tenant_id == tenant_id)
            .order_by(Appointment.starts_at.desc())
            .limit(max(1, min(limit, 200)))
        ).all()
        return [
            {
                "id": str(a.id),
                "confirmation_code": a.confirmation_code,
                "status": a.status,
                "service_type": a.service_type,
                "starts_at": a.starts_at.isoformat() if a.starts_at else None,
                "ends_at": a.ends_at.isoformat() if a.ends_at else None,
                "customer_id": str(a.customer_id),
            }
            for a in rows
        ]

    def metrics_summary(self, tenant_id: UUID, *, days: int = 30) -> dict[str, Any]:
        window_days = max(1, min(days, 365))
        since = datetime.now(UTC) - timedelta(days=window_days)
        calls = self._session.scalar(
            select(func.count())
            .select_from(Call)
            .where(Call.tenant_id == tenant_id, Call.started_at >= since)
        )
        calls_ended = self._session.scalar(
            select(func.count())
            .select_from(Call)
            .where(
                Call.tenant_id == tenant_id,
                Call.started_at >= since,
                Call.ended_at.is_not(None),
            )
        )
        calls_active = self._session.scalar(
            select(func.count())
            .select_from(Call)
            .where(Call.tenant_id == tenant_id, Call.status == "active")
        )
        jobs = self._session.scalar(
            select(func.count())
            .select_from(Job)
            .where(Job.tenant_id == tenant_id, Job.created_at >= since)
        )
        completed = self._session.scalar(
            select(func.count())
            .select_from(Job)
            .where(
                Job.tenant_id == tenant_id,
                Job.status == "completed",
                Job.updated_at >= since,
            )
        )
        appts = self._session.scalar(
            select(func.count())
            .select_from(Appointment)
            .where(Appointment.tenant_id == tenant_id, Appointment.created_at >= since)
        )
        customers = self._session.scalar(
            select(func.count())
            .select_from(Customer)
            .where(Customer.tenant_id == tenant_id)
        )
        leads = self._session.scalar(
            select(func.count())
            .select_from(Lead)
            .where(
                Lead.tenant_id == tenant_id,
                Lead.created_at >= since,
                Lead.archived_at.is_(None),
            )
        )
        leads_by_status = dict(
            self._session.execute(
                select(Lead.status, func.count())
                .where(
                    Lead.tenant_id == tenant_id,
                    Lead.archived_at.is_(None),
                )
                .group_by(Lead.status)
            ).all()
        )
        by_status = dict(
            self._session.execute(
                select(Job.status, func.count())
                .where(Job.tenant_id == tenant_id)
                .group_by(Job.status)
            ).all()
        )

        # Revenue from succeeded customer payments in the window (Phase 19).
        payment_rows = self._session.execute(
            select(Payment.amount, Payment.succeeded_at, Payment.created_at).where(
                Payment.tenant_id == tenant_id,
                Payment.status == "SUCCEEDED",
                func.coalesce(Payment.succeeded_at, Payment.created_at) >= since,
            )
        ).all()
        revenue_total = 0.0
        revenue_by_day: dict[str, float] = {}
        for amount, succeeded_at, created_at in payment_rows:
            ts = succeeded_at or created_at
            if ts is None:
                continue
            day_key = ts.astimezone(UTC).date().isoformat()
            value = float(amount or 0)
            revenue_total += value
            revenue_by_day[day_key] = revenue_by_day.get(day_key, 0.0) + value

        # Outstanding = open invoice balances (exclude draft/void/fully paid).
        outstanding_rows = self._session.execute(
            select(func.count(), func.coalesce(func.sum(Invoice.balance_due), 0)).where(
                Invoice.tenant_id == tenant_id,
                Invoice.balance_due > 0,
                Invoice.status.in_(("SENT", "PARTIALLY_PAID", "OVERDUE")),
            )
        ).one()
        outstanding_count = int(outstanding_rows[0] or 0)
        outstanding_balance = float(outstanding_rows[1] or 0)

        call_rows = self._session.scalars(
            select(Call).where(
                Call.tenant_id == tenant_id,
                Call.started_at >= since,
            )
        ).all()
        voice_seconds = 0
        handoffs = 0
        appointments_booked_flag = 0
        quality_scores: list[int] = []
        disconnect_reasons: dict[str, int] = {}
        calls_by_day: dict[str, int] = {}
        for call in call_rows:
            day_key = call.started_at.astimezone(UTC).date().isoformat()
            calls_by_day[day_key] = calls_by_day.get(day_key, 0) + 1
            if call.ended_at is not None:
                if call.billable_seconds is not None:
                    voice_seconds += int(call.billable_seconds)
                else:
                    voice_seconds += compute_billable_seconds(
                        call.started_at, call.ended_at
                    )
            reason = (call.disconnect_reason or "unknown").strip() or "unknown"
            if call.ended_at is not None:
                disconnect_reasons[reason] = disconnect_reasons.get(reason, 0) + 1
            metrics_blob = call.metrics if isinstance(call.metrics, dict) else {}
            if metrics_blob.get("handoff_requested"):
                handoffs += 1
            if metrics_blob.get("appointment_booked"):
                appointments_booked_flag += 1
            if call.quality_score is not None:
                quality_scores.append(int(call.quality_score))

        ended_count = int(calls_ended or 0)
        avg_duration = round(voice_seconds / ended_count, 1) if ended_count > 0 else 0.0
        avg_quality = (
            round(sum(quality_scores) / len(quality_scores), 2)
            if quality_scores
            else None
        )
        # AI resolved without human handoff among ended calls in the window.
        resolved_without_handoff = max(0, ended_count - handoffs)
        ai_resolution_rate = (
            round(resolved_without_handoff / ended_count, 3) if ended_count else None
        )
        # Fill every calendar day in the window so the Ops chart has a continuous axis.
        series: list[dict[str, Any]] = []
        revenue_series: list[dict[str, Any]] = []
        cursor = since.astimezone(UTC).date()
        today = datetime.now(UTC).date()
        while cursor <= today:
            key = cursor.isoformat()
            series.append({"date": key, "calls": calls_by_day.get(key, 0)})
            revenue_series.append(
                {
                    "date": key,
                    "revenue": round(revenue_by_day.get(key, 0.0), 4),
                }
            )
            cursor += timedelta(days=1)

        return {
            "window_days": window_days,
            "calls": int(calls or 0),
            "calls_ended": ended_count,
            "calls_active": int(calls_active or 0),
            "voice_seconds": voice_seconds,
            "voice_minutes": seconds_to_billable_minutes(voice_seconds),
            "avg_call_duration_seconds": avg_duration,
            "avg_quality_score": avg_quality,
            "quality_reviews": len(quality_scores),
            "handoffs_requested": handoffs,
            "handoff_rate": round(handoffs / ended_count, 3) if ended_count else 0.0,
            "ai_resolution_rate": ai_resolution_rate,
            "appointment_booked_calls": appointments_booked_flag,
            "appointments": int(appts or 0),
            "jobs": int(jobs or 0),
            "jobs_completed": int(completed or 0),
            "customers": int(customers or 0),
            "leads": int(leads or 0),
            "leads_by_status": {str(k): int(v) for k, v in leads_by_status.items()},
            "revenue": round(revenue_total, 4),
            "revenue_by_day": revenue_series,
            "outstanding_invoices": outstanding_count,
            "outstanding_balance": round(outstanding_balance, 4),
            "jobs_by_status": {str(k): int(v) for k, v in by_status.items()},
            "disconnect_reasons": disconnect_reasons,
            "calls_by_day": series,
        }

    def list_audit(self, tenant_id: UUID, *, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._session.scalars(
            select(TelephonyAuditEvent)
            .where(TelephonyAuditEvent.tenant_id == tenant_id)
            .order_by(TelephonyAuditEvent.created_at.desc())
            .limit(max(1, min(limit, 200)))
        ).all()
        return [
            {
                "id": str(r.id),
                "actor": r.actor,
                "action": r.action,
                "resource_ids": r.resource_ids,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    def list_users(self, tenant_id: UUID) -> list[dict[str, Any]]:
        rows = self._session.scalars(
            select(TenantUser)
            .where(TenantUser.tenant_id == tenant_id)
            .order_by(TenantUser.created_at.desc())
        ).all()
        from callbot_platform.rbac.errors import RbacError
        from callbot_platform.rbac.repos import RoleRepository

        role_repo = RoleRepository(self._session)
        result: list[dict[str, Any]] = []
        for u in rows:
            try:
                roles = role_repo.list_member_roles(tenant_id, u.id).get("roles") or []
            except RbacError:
                roles = []
            result.append(
                {
                    "id": str(u.id),
                    "email": u.email,
                    "name": u.name,
                    "role": u.role,
                    "status": u.status,
                    "is_active": u.is_active,
                    "roles": roles,
                }
            )
        return result

    def get_retention(self, tenant_id: UUID) -> dict[str, Any]:
        row = self._session.scalar(
            select(TenantRetentionSettings).where(
                TenantRetentionSettings.tenant_id == tenant_id
            )
        )
        if row is None:
            return {
                "tenant_id": str(tenant_id),
                "recording_retention_days": 30,
                "transcript_retention_days": 90,
                "audit_retention_days": 365,
            }
        return self._serialize_retention(row)

    def upsert_retention(
        self,
        tenant_id: UUID,
        *,
        recording_retention_days: int | None = None,
        transcript_retention_days: int | None = None,
        audit_retention_days: int | None = None,
        actor: str = "admin",
    ) -> dict[str, Any]:
        row = self._session.scalar(
            select(TenantRetentionSettings).where(
                TenantRetentionSettings.tenant_id == tenant_id
            )
        )
        if row is None:
            row = TenantRetentionSettings(tenant_id=tenant_id)
            self._session.add(row)
        if recording_retention_days is not None:
            row.recording_retention_days = max(0, recording_retention_days)
        if transcript_retention_days is not None:
            row.transcript_retention_days = max(0, transcript_retention_days)
        if audit_retention_days is not None:
            row.audit_retention_days = max(0, audit_retention_days)
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="retention_settings_upserted",
            resource_ids={"tenant_id": str(tenant_id)},
        )
        return self._serialize_retention(row)

    def _serialize_retention(self, row: TenantRetentionSettings) -> dict[str, Any]:
        return {
            "tenant_id": str(row.tenant_id),
            "recording_retention_days": row.recording_retention_days,
            "transcript_retention_days": row.transcript_retention_days,
            "audit_retention_days": row.audit_retention_days,
        }

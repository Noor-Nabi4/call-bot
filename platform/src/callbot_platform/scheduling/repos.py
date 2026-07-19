"""Tenant-scoped scheduling repositories."""

from __future__ import annotations

import secrets
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from callbot_platform.db.models import (
    Appointment,
    Call,
    Customer,
    Lead,
    Tenant,
    TenantScheduleSettings,
    default_weekly_hours,
)
from callbot_platform.scheduling.availability import (
    filter_free_slots,
    generate_candidate_slots,
    ranges_overlap,
    resolve_tz,
)
from callbot_platform.scheduling.notifications import NotificationService
from callbot_platform.telephony.audit import write_audit


class SchedulingError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _confirmation_code() -> str:
    return f"APT-{secrets.token_hex(3).upper()}"


def _ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


class ScheduleSettingsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_or_create(self, tenant_id: UUID) -> TenantScheduleSettings:
        row = self._session.scalar(
            select(TenantScheduleSettings).where(
                TenantScheduleSettings.tenant_id == tenant_id
            )
        )
        if row is not None:
            return row
        row = TenantScheduleSettings(
            tenant_id=tenant_id,
            timezone=None,
            slot_minutes=60,
            booking_horizon_days=14,
            weekly_hours=default_weekly_hours(),
        )
        self._session.add(row)
        self._session.flush()
        return row

    def effective_timezone(self, tenant_id: UUID) -> str:
        tenant = self._session.get(Tenant, tenant_id)
        if tenant is None:
            raise SchedulingError("tenant_not_found", "Tenant not found")
        settings = self.get_or_create(tenant_id)
        return (settings.timezone or tenant.timezone or "UTC").strip() or "UTC"

    def serialize(self, row: TenantScheduleSettings, tenant: Tenant) -> dict[str, Any]:
        return {
            "tenant_id": str(row.tenant_id),
            "timezone": row.timezone or tenant.timezone,
            "slot_minutes": row.slot_minutes,
            "booking_horizon_days": row.booking_horizon_days,
            "weekly_hours": row.weekly_hours,
        }


class AppointmentRepository:
    def __init__(
        self,
        session: Session,
        *,
        notification_service: NotificationService | None = None,
    ) -> None:
        self._session = session
        self._notifications = notification_service or NotificationService(session)
        self._settings = ScheduleSettingsRepository(session)

    def list_available_slots(
        self,
        tenant_id: UUID,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 40,
    ) -> dict[str, Any]:
        tenant = self._session.get(Tenant, tenant_id)
        if tenant is None:
            raise SchedulingError("tenant_not_found", "Tenant not found")

        settings = self._settings.get_or_create(tenant_id)
        tz_name = self._settings.effective_timezone(tenant_id)
        today_local = datetime.now(UTC).astimezone(resolve_tz(tz_name)).date()
        start_day = from_date or today_local
        end_day = to_date or (
            start_day + timedelta(days=max(1, settings.booking_horizon_days) - 1)
        )
        horizon_end = today_local + timedelta(days=settings.booking_horizon_days)
        if end_day > horizon_end:
            end_day = horizon_end
        if start_day > end_day:
            return {
                "timezone": tz_name,
                "slot_minutes": settings.slot_minutes,
                "slots": [],
            }

        candidates = generate_candidate_slots(
            timezone_name=tz_name,
            weekly_hours=settings.weekly_hours or default_weekly_hours(),
            slot_minutes=settings.slot_minutes,
            from_date=start_day,
            to_date=end_day,
        )
        booked = self._booked_ranges(
            tenant_id,
            window_start=candidates[0].starts_at if candidates else datetime.now(UTC),
            window_end=(
                candidates[-1].ends_at if candidates else datetime.now(UTC)
            ),
        )
        free = filter_free_slots(candidates, booked)[: max(1, min(limit, 100))]
        return {
            "timezone": tz_name,
            "slot_minutes": settings.slot_minutes,
            "slots": [
                {
                    "starts_at": s.starts_at.isoformat(),
                    "ends_at": s.ends_at.isoformat(),
                    "local_start": s.local_start,
                    "local_end": s.local_end,
                }
                for s in free
            ],
        }

    def book(
        self,
        tenant_id: UUID,
        *,
        customer_id: UUID,
        starts_at: datetime,
        service_type: str,
        notes: str | None = None,
        lead_id: UUID | None = None,
        call_id: UUID | None = None,
        idempotency_key: str | None = None,
        actor: str = "voice-agent",
    ) -> dict[str, Any]:
        if not service_type or not service_type.strip():
            raise SchedulingError("invalid_service_type", "service_type is required")

        tenant = self._session.get(Tenant, tenant_id)
        if tenant is None:
            raise SchedulingError("tenant_not_found", "Tenant not found")

        if idempotency_key:
            existing = self._session.scalar(
                select(Appointment).where(
                    Appointment.tenant_id == tenant_id,
                    Appointment.idempotency_key == idempotency_key,
                )
            )
            if existing is not None:
                from callbot_platform.jobs.repos import JobRepository

                job = JobRepository(self._session).create_from_appointment(existing)
                result = self._serialize(existing)
                if job is not None:
                    result["job"] = job
                return result

        customer = self._session.scalar(
            select(Customer)
            .where(Customer.id == customer_id, Customer.tenant_id == tenant_id)
            .options(selectinload(Customer.phones))
        )
        if customer is None:
            raise SchedulingError("customer_not_found", "Customer not found for tenant")

        if lead_id is not None:
            lead = self._session.scalar(
                select(Lead).where(Lead.id == lead_id, Lead.tenant_id == tenant_id)
            )
            if lead is None:
                raise SchedulingError("lead_not_found", "Lead not found for tenant")

        if call_id is not None:
            call = self._session.scalar(
                select(Call).where(Call.id == call_id, Call.tenant_id == tenant_id)
            )
            if call is None:
                raise SchedulingError("call_not_found", "Call not found for tenant")

        settings = self._settings.get_or_create(tenant_id)
        starts = _ensure_aware(starts_at)
        ends = starts + timedelta(minutes=settings.slot_minutes)

        if self._has_overlap(tenant_id, starts, ends):
            raise SchedulingError(
                "slot_unavailable",
                "That time is no longer available. Please choose another slot.",
            )

        appt = Appointment(
            tenant_id=tenant_id,
            customer_id=customer_id,
            lead_id=lead_id,
            call_id=call_id,
            starts_at=starts,
            ends_at=ends,
            status="scheduled",
            service_type=service_type.strip(),
            notes=notes.strip() if notes else None,
            confirmation_code=_confirmation_code(),
            idempotency_key=idempotency_key,
        )
        self._session.add(appt)
        self._session.flush()

        # Re-check overlap after insert race (best-effort for SQLite tests).
        if self._has_overlap(tenant_id, starts, ends, exclude_id=appt.id):
            self._session.delete(appt)
            self._session.flush()
            raise SchedulingError(
                "slot_unavailable",
                "That time is no longer available. Please choose another slot.",
            )

        tz_name = self._settings.effective_timezone(tenant_id)
        notifications = self._notifications.send_appointment_notifications(
            appt,
            customer=customer,
            business_name=tenant.name,
            timezone_name=tz_name,
            action="booked",
        )
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="appointment_booked",
            resource_ids={
                "appointment_id": str(appt.id),
                "customer_id": str(customer_id),
                "confirmation_code": appt.confirmation_code,
            },
            idempotency_key=idempotency_key,
            payload_summary={"starts_at": starts.isoformat()},
        )
        # Auto-create a scheduled job so ops can dispatch after voice booking.
        from callbot_platform.jobs.repos import JobRepository

        job = JobRepository(self._session).create_from_appointment(appt)
        result = self._serialize(appt)
        result["notifications"] = notifications
        if job is not None:
            result["job"] = job
        return result

    def reschedule(
        self,
        tenant_id: UUID,
        appointment_id: UUID,
        *,
        starts_at: datetime,
        actor: str = "voice-agent",
    ) -> dict[str, Any]:
        appt = self._get_active(tenant_id, appointment_id)
        settings = self._settings.get_or_create(tenant_id)
        starts = _ensure_aware(starts_at)
        ends = starts + timedelta(minutes=settings.slot_minutes)

        if self._has_overlap(tenant_id, starts, ends, exclude_id=appt.id):
            raise SchedulingError(
                "slot_unavailable",
                "That time is no longer available. Please choose another slot.",
            )

        appt.starts_at = starts
        appt.ends_at = ends
        appt.status = "scheduled"
        appt.updated_at = datetime.now(UTC)
        self._session.flush()

        customer = self._session.scalar(
            select(Customer)
            .where(Customer.id == appt.customer_id, Customer.tenant_id == tenant_id)
            .options(selectinload(Customer.phones))
        )
        tenant = self._session.get(Tenant, tenant_id)
        notifications: list[dict[str, Any]] = []
        if customer is not None and tenant is not None:
            tz_name = self._settings.effective_timezone(tenant_id)
            notifications = self._notifications.send_appointment_notifications(
                appt,
                customer=customer,
                business_name=tenant.name,
                timezone_name=tz_name,
                action="rescheduled",
            )

        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="appointment_rescheduled",
            resource_ids={"appointment_id": str(appt.id)},
            payload_summary={"starts_at": starts.isoformat()},
        )
        result = self._serialize(appt)
        result["notifications"] = notifications
        return result

    def cancel(
        self,
        tenant_id: UUID,
        appointment_id: UUID,
        *,
        actor: str = "voice-agent",
    ) -> dict[str, Any]:
        appt = self._get_active(tenant_id, appointment_id)
        appt.status = "canceled"
        appt.updated_at = datetime.now(UTC)
        self._session.flush()

        customer = self._session.scalar(
            select(Customer)
            .where(Customer.id == appt.customer_id, Customer.tenant_id == tenant_id)
            .options(selectinload(Customer.phones))
        )
        tenant = self._session.get(Tenant, tenant_id)
        notifications: list[dict[str, Any]] = []
        if customer is not None and tenant is not None:
            tz_name = self._settings.effective_timezone(tenant_id)
            notifications = self._notifications.send_appointment_notifications(
                appt,
                customer=customer,
                business_name=tenant.name,
                timezone_name=tz_name,
                action="canceled",
            )

        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="appointment_canceled",
            resource_ids={"appointment_id": str(appt.id)},
        )
        result = self._serialize(appt)
        result["notifications"] = notifications
        return result

    def get(self, tenant_id: UUID, appointment_id: UUID) -> dict[str, Any] | None:
        appt = self._session.scalar(
            select(Appointment).where(
                Appointment.id == appointment_id,
                Appointment.tenant_id == tenant_id,
            )
        )
        if appt is None:
            return None
        return self._serialize(appt)

    def _get_active(self, tenant_id: UUID, appointment_id: UUID) -> Appointment:
        appt = self._session.scalar(
            select(Appointment).where(
                Appointment.id == appointment_id,
                Appointment.tenant_id == tenant_id,
            )
        )
        if appt is None:
            raise SchedulingError(
                "appointment_not_found", "Appointment not found for tenant"
            )
        if appt.status == "canceled":
            raise SchedulingError(
                "appointment_canceled", "Appointment is already canceled"
            )
        return appt

    def _booked_ranges(
        self,
        tenant_id: UUID,
        *,
        window_start: datetime,
        window_end: datetime,
        exclude_id: UUID | None = None,
    ) -> list[tuple[datetime, datetime]]:
        q = select(Appointment).where(
            Appointment.tenant_id == tenant_id,
            Appointment.status == "scheduled",
            Appointment.starts_at < window_end,
            Appointment.ends_at > window_start,
        )
        if exclude_id is not None:
            q = q.where(Appointment.id != exclude_id)
        rows = self._session.scalars(q).all()
        return [(_ensure_aware(r.starts_at), _ensure_aware(r.ends_at)) for r in rows]

    def _has_overlap(
        self,
        tenant_id: UUID,
        starts: datetime,
        ends: datetime,
        *,
        exclude_id: UUID | None = None,
    ) -> bool:
        for b_start, b_end in self._booked_ranges(
            tenant_id,
            window_start=starts,
            window_end=ends,
            exclude_id=exclude_id,
        ):
            if ranges_overlap(starts, ends, b_start, b_end):
                return True
        return False

    def _serialize(self, appt: Appointment) -> dict[str, Any]:
        return {
            "id": str(appt.id),
            "tenant_id": str(appt.tenant_id),
            "customer_id": str(appt.customer_id),
            "lead_id": str(appt.lead_id) if appt.lead_id else None,
            "call_id": str(appt.call_id) if appt.call_id else None,
            "starts_at": appt.starts_at.isoformat() if appt.starts_at else None,
            "ends_at": appt.ends_at.isoformat() if appt.ends_at else None,
            "status": appt.status,
            "service_type": appt.service_type,
            "notes": appt.notes,
            "confirmation_code": appt.confirmation_code,
            "idempotency_key": appt.idempotency_key,
            "created_at": appt.created_at.isoformat() if appt.created_at else None,
            "updated_at": appt.updated_at.isoformat() if appt.updated_at else None,
        }

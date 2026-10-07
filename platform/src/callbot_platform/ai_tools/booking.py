"""Authoritative voice booking orchestration (job + appointment).

The AI must not coordinate partial job/appointment state. This service runs both
creates in one session; on appointment conflict the transaction rolls back so
no orphan job is committed.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.crm.appointments.service import AppointmentService
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.jobs.service import JobService
from callbot_platform.scheduling.errors import ensure_aware

logger = logging.getLogger(__name__)


def _parse_aware(value: str, *, timezone: str) -> datetime:
    raw = value.strip()
    if not raw:
        raise CrmError("booking_invalid", "starts_at/ends_at is required")
    try:
        if raw.endswith("Z"):
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise CrmError("booking_invalid", "Invalid datetime") from exc
    if dt.tzinfo is None:
        try:
            tz = ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            raise CrmError("booking_invalid", "Invalid timezone") from exc
        dt = dt.replace(tzinfo=tz)
    return ensure_aware(dt)


class BookingOrchestrationService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._jobs = JobService(session)
        self._appointments = AppointmentService(session)

    def create_booking(
        self,
        tenant_id: UUID,
        *,
        customer_id: UUID,
        service_id: UUID,
        starts_at: str,
        ends_at: str,
        timezone: str,
        actor: str,
        location_id: UUID | None = None,
        technician_id: UUID | None = None,
        description: str | None = None,
        priority: str | None = None,
        notes: str | None = None,
        emergency: bool = False,
        call_id: UUID | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        start = _parse_aware(starts_at, timezone=timezone)
        end = _parse_aware(ends_at, timezone=timezone)
        if end <= start:
            raise CrmError("booking_invalid", "ends_at must be after starts_at")

        job_key = f"{idempotency_key}:job" if idempotency_key else None
        appt_key = f"{idempotency_key}:appointment" if idempotency_key else None

        desc = (description or notes or "Voice booking").strip()
        job = self._jobs.create(
            tenant_id,
            customer_id=customer_id,
            actor=actor,
            service_id=service_id,
            location_id=location_id,
            description=desc,
            priority=priority,
            call_id=call_id,
            idempotency_key=job_key,
        )
        job_id = UUID(str(job["id"]))

        try:
            appointment = self._appointments.create(
                tenant_id,
                customer_id=customer_id,
                starts_at=start,
                ends_at=end,
                actor=actor,
                service_id=service_id,
                location_id=location_id,
                technician_id=technician_id,
                job_id=job_id,
                call_id=call_id,
                is_emergency=bool(emergency),
                notes=notes,
                idempotency_key=appt_key,
            )
        except (CrmError, IntegrityError) as exc:
            code = getattr(exc, "code", "") or ""
            if isinstance(exc, IntegrityError) or code in {
                "slot_conflict",
                "booking_conflict",
                "appointment_conflict",
            }:
                logger.info(
                    "booking_conflict tenant_id=%s job_id=%s",
                    tenant_id,
                    job_id,
                )
                # Roll back so a flushed job is not left without an appointment.
                self._session.rollback()
                raise CrmError(
                    "booking_conflict",
                    "Selected appointment slot is no longer available",
                ) from exc
            raise

        return {
            "booking": "CREATED",
            "job": {
                "id": job["id"],
                "jobNumber": job.get("job_number") or job.get("jobNumber") or "",
                "status": job.get("status"),
                "customerId": str(customer_id),
            },
            "appointment": {
                "id": appointment["id"],
                "appointmentNumber": (
                    appointment.get("appointment_number")
                    or appointment.get("appointmentNumber")
                    or ""
                ),
                "status": appointment.get("status"),
                "startsAt": appointment.get("starts_at") or appointment.get("startsAt"),
                "endsAt": appointment.get("ends_at") or appointment.get("endsAt"),
                "timezone": timezone,
                "jobId": str(job_id),
            },
        }

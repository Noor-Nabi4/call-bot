"""Appointment status transition policy and service."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.appointments.constants import (
    REQUIRES_TECHNICIAN,
    VALID_TRANSITIONS,
    AppointmentStatus,
    normalize_status,
)
from callbot_platform.crm.appointments.serialize import (
    serialize_appointment,
    serialize_status_history,
)
from callbot_platform.crm.errors import CrmError
from callbot_platform.db.models.scheduling import Appointment, AppointmentStatusHistory
from callbot_platform.telephony.audit import write_audit


class AppointmentTransitionService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def history(self, tenant_id: UUID, appointment_id: UUID) -> list[dict[str, Any]]:
        appt = self._session.scalar(
            select(Appointment).where(
                Appointment.id == appointment_id, Appointment.tenant_id == tenant_id
            )
        )
        if appt is None:
            raise CrmError("not_found", "Appointment not found for tenant")
        rows = list(
            self._session.scalars(
                select(AppointmentStatusHistory)
                .where(
                    AppointmentStatusHistory.tenant_id == tenant_id,
                    AppointmentStatusHistory.appointment_id == appointment_id,
                )
                .order_by(
                    AppointmentStatusHistory.created_at.asc(),
                    AppointmentStatusHistory.id.asc(),
                )
            ).all()
        )
        return [serialize_status_history(r) for r in rows]

    def transition(
        self,
        tenant_id: UUID,
        appointment_id: UUID,
        *,
        to_status: str,
        actor: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        try:
            target = normalize_status(to_status)
        except ValueError as exc:
            raise CrmError(
                "invalid_status", f"Unknown appointment status: {to_status}"
            ) from exc

        appt = self._session.scalar(
            select(Appointment)
            .where(Appointment.id == appointment_id, Appointment.tenant_id == tenant_id)
            .options(
                selectinload(Appointment.customer),
                selectinload(Appointment.assigned_technician),
                selectinload(Appointment.location),
                selectinload(Appointment.service),
                selectinload(Appointment.status_history),
            )
            .with_for_update()
        )
        if appt is None:
            raise CrmError("not_found", "Appointment not found for tenant")
        if appt.archived_at is not None:
            raise CrmError(
                "appointment_archived", "Cannot transition an archived appointment"
            )

        current = appt.status
        if current == target:
            return serialize_appointment(appt, include_history=True)

        if (current, target) not in VALID_TRANSITIONS:
            raise CrmError(
                "invalid_transition",
                f"Cannot move appointment from {current} to {target}",
            )

        if target in REQUIRES_TECHNICIAN and appt.assigned_technician_id is None:
            raise CrmError(
                "technician_required",
                "Assign a technician before this status transition",
            )

        if target == AppointmentStatus.COMPLETED.value:
            appt.completed_at = datetime.now(UTC)
        if target in {
            AppointmentStatus.CANCELLED.value,
            AppointmentStatus.NO_SHOW.value,
        }:
            appt.cancelled_at = datetime.now(UTC)

        history = AppointmentStatusHistory(
            tenant_id=tenant_id,
            appointment_id=appt.id,
            from_status=current,
            to_status=target,
            changed_by=actor,
            reason=(reason.strip() if reason and reason.strip() else None),
        )
        self._session.add(history)
        appt.status = target
        appt.updated_by = actor
        appt.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="appointment_status_changed",
            resource_ids={
                "appointment_id": str(appt.id),
                "appointment_number": appt.appointment_number,
            },
            payload_summary={"from": current, "to": target},
        )
        return serialize_appointment(appt, include_history=True)

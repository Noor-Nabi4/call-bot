"""Appointment serialization."""

from __future__ import annotations

from typing import Any

from callbot_platform.db.models.scheduling import Appointment, AppointmentStatusHistory


def serialize_status_history(row: AppointmentStatusHistory) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "appointment_id": str(row.appointment_id),
        "from_status": row.from_status,
        "to_status": row.to_status,
        "changed_by": row.changed_by,
        "reason": row.reason,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def serialize_appointment(
    appt: Appointment, *, include_history: bool = False
) -> dict[str, Any]:
    customer = None
    if appt.customer is not None:
        customer = {
            "id": str(appt.customer.id),
            "name": appt.customer.name,
            "display_name": appt.customer.name,
            "email": appt.customer.email,
            "status": appt.customer.status,
        }
    location = None
    if appt.location is not None:
        location = {
            "id": str(appt.location.id),
            "label": appt.location.label,
            "address_line_1": appt.location.address_line_1,
            "city": appt.location.city,
            "state": appt.location.state,
            "postal_code": appt.location.postal_code,
        }
    service = None
    if appt.service is not None:
        service = {
            "id": str(appt.service.id),
            "name": appt.service.name,
            "code": getattr(appt.service, "code", None),
            "duration_minutes": appt.service.duration_minutes,
        }
    technician = None
    if appt.assigned_technician is not None:
        technician = {
            "id": str(appt.assigned_technician.id),
            "display_name": appt.assigned_technician.display_name,
        }

    payload: dict[str, Any] = {
        "id": str(appt.id),
        "tenant_id": str(appt.tenant_id),
        "appointment_number": appt.appointment_number,
        "confirmation_code": appt.confirmation_code,
        "customer_id": str(appt.customer_id),
        "customer": customer,
        "location_id": str(appt.location_id) if appt.location_id else None,
        "location": location,
        "service_id": str(appt.service_id) if appt.service_id else None,
        "service": service,
        "service_type": appt.service_type,
        "job_id": str(appt.job_id) if appt.job_id else None,
        "lead_id": str(appt.lead_id) if appt.lead_id else None,
        "call_id": str(appt.call_id) if appt.call_id else None,
        "assigned_technician_id": (
            str(appt.assigned_technician_id) if appt.assigned_technician_id else None
        ),
        "assigned_technician": technician,
        "starts_at": appt.starts_at.isoformat() if appt.starts_at else None,
        "ends_at": appt.ends_at.isoformat() if appt.ends_at else None,
        "duration_minutes": appt.duration_minutes,
        "timezone": appt.timezone,
        "status": appt.status,
        "priority": appt.priority,
        "is_emergency": appt.is_emergency,
        "notes": appt.notes,
        "idempotency_key": appt.idempotency_key,
        "created_by": appt.created_by,
        "updated_by": appt.updated_by,
        "cancelled_at": appt.cancelled_at.isoformat() if appt.cancelled_at else None,
        "completed_at": appt.completed_at.isoformat() if appt.completed_at else None,
        "archived_at": appt.archived_at.isoformat() if appt.archived_at else None,
        "created_at": appt.created_at.isoformat() if appt.created_at else None,
        "updated_at": appt.updated_at.isoformat() if appt.updated_at else None,
    }
    if include_history:
        history = sorted(
            appt.status_history or [],
            key=lambda h: (
                h.created_at.isoformat() if h.created_at else "",
                str(h.id),
            ),
        )
        payload["status_history"] = [serialize_status_history(h) for h in history]
    return payload

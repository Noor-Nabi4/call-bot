"""Internal scheduling HTTP API (service-token authenticated)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from callbot_platform.api.deps import db_dep, require_internal_token
from callbot_platform.scheduling.repos import AppointmentRepository, SchedulingError

router = APIRouter(
    prefix="/internal/scheduling",
    dependencies=[Depends(require_internal_token)],
)


class SlotsBody(BaseModel):
    tenant_id: UUID
    from_date: date | None = None
    to_date: date | None = None
    limit: int = Field(default=40, ge=1, le=100)


class BookAppointmentBody(BaseModel):
    tenant_id: UUID
    customer_id: UUID
    starts_at: datetime
    service_type: str
    notes: str | None = None
    lead_id: UUID | None = None
    call_id: UUID | None = None
    idempotency_key: str | None = None


class RescheduleBody(BaseModel):
    tenant_id: UUID
    starts_at: datetime


class CancelBody(BaseModel):
    tenant_id: UUID


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, SchedulingError):
        if "not_found" in exc.code:
            status = 404
        elif exc.code == "slot_unavailable":
            status = 409
        else:
            status = 400
        return HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        )
    return HTTPException(
        status_code=500, detail={"code": "internal", "message": str(exc)}
    )


@router.post("/slots")
def list_slots(body: SlotsBody, session: Session = Depends(db_dep)) -> dict[str, Any]:
    try:
        return AppointmentRepository(session).list_available_slots(
            body.tenant_id,
            from_date=body.from_date,
            to_date=body.to_date,
            limit=body.limit,
        )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/appointments")
def book_appointment(
    body: BookAppointmentBody, session: Session = Depends(db_dep)
) -> dict[str, Any]:
    try:
        appointment = AppointmentRepository(session).book(
            body.tenant_id,
            customer_id=body.customer_id,
            starts_at=body.starts_at,
            service_type=body.service_type,
            notes=body.notes,
            lead_id=body.lead_id,
            call_id=body.call_id,
            idempotency_key=body.idempotency_key,
        )
        return {"appointment": appointment}
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/appointments/{appointment_id}")
def get_appointment(
    appointment_id: UUID,
    tenant_id: UUID,
    session: Session = Depends(db_dep),
) -> dict[str, Any]:
    appointment = AppointmentRepository(session).get(tenant_id, appointment_id)
    if appointment is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "appointment_not_found",
                "message": "Appointment not found for tenant",
            },
        )
    return {"appointment": appointment}


@router.post("/appointments/{appointment_id}/reschedule")
def reschedule_appointment(
    appointment_id: UUID,
    body: RescheduleBody,
    session: Session = Depends(db_dep),
) -> dict[str, Any]:
    try:
        appointment = AppointmentRepository(session).reschedule(
            body.tenant_id,
            appointment_id,
            starts_at=body.starts_at,
        )
        return {"appointment": appointment}
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/appointments/{appointment_id}/cancel")
def cancel_appointment(
    appointment_id: UUID,
    body: CancelBody,
    session: Session = Depends(db_dep),
) -> dict[str, Any]:
    try:
        appointment = AppointmentRepository(session).cancel(
            body.tenant_id,
            appointment_id,
        )
        return {"appointment": appointment}
    except Exception as exc:
        raise _http_error(exc) from exc

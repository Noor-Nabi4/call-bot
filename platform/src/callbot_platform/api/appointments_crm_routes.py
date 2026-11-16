"""Admin Appointment CRM + Availability + Business Hours + Technician
Schedule APIs (Phase 11).

Mirrors ``api/jobs_crm_routes.py`` patterns: resource-scoped RBAC via
``ResourceContext.assigned_technician_user_id``, 404-before-403 for
tenant-owned resources, and ``CrmError`` → HTTP status mapping.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.api.deps import (
    CurrentUser,
    db_dep,
    require_entitled_permission,
    require_entitled_tenant_user,
)
from callbot_platform.crm.appointments import (
    AppointmentService,
    AvailabilityEngine,
    BusinessHoursService,
    TechnicianAvailabilityService,
)
from callbot_platform.crm.errors import CrmError
from callbot_platform.db.models.jobs import Technician
from callbot_platform.rbac.errors import RbacError
from callbot_platform.rbac.service import AuthorizationService, ResourceContext

router = APIRouter(prefix="/api/admin/crm", tags=["appointments"])

_require_create = require_entitled_permission("appointments.create")
_require_business_hours_read = require_entitled_permission(
    "appointments.business_hours.read"
)
_require_business_hours_update = require_entitled_permission(
    "appointments.business_hours.update"
)
_require_technician_schedule_read = require_entitled_permission(
    "appointments.technician_schedule.read"
)
_require_technician_schedule_update = require_entitled_permission(
    "appointments.technician_schedule.update"
)
_require_availability_read = require_entitled_permission(
    "appointments.availability.read"
)


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, RbacError):
        return HTTPException(
            status_code=403, detail={"code": exc.code, "message": str(exc)}
        )
    if isinstance(exc, CrmError):
        status = 404 if exc.code == "not_found" else 400
        if exc.code == "forbidden":
            status = 403
        if exc.code.endswith("_not_found"):
            status = 404
        if exc.code in {
            "invalid_transition",
            "appointment_archived",
            "use_transition",
            "archive_not_allowed",
            "appointment_conflict",
            "slot_conflict",
            "technician_required",
            "idempotency_conflict",
            "appointment_immutable",
            "holiday_conflict",
            "skill_conflict",
            "service_area_conflict",
            "period_overlap",
            "break_overlap",
            "time_off_overlap",
        }:
            status = 409
        return HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        )
    if isinstance(exc, IntegrityError):
        return HTTPException(
            status_code=409,
            detail={"code": "conflict", "message": "Conflicting write"},
        )
    return HTTPException(
        status_code=500, detail={"code": "internal", "message": "Internal error"}
    )


def _actor(user: CurrentUser) -> str:
    return user.email or str(user.user_id)


def _appointment_resource(
    session: Session, tenant_id: UUID, appt: dict[str, Any]
) -> ResourceContext:
    tech_id = appt.get("assigned_technician_id")
    tech_user_id: UUID | None = None
    if tech_id:
        tech_user_id = session.scalar(
            select(Technician.user_id).where(
                Technician.id == UUID(str(tech_id)), Technician.tenant_id == tenant_id
            )
        )
    return ResourceContext(
        tenant_id=tenant_id, assigned_technician_user_id=tech_user_id
    )


def _require_appointment_permission(
    session: Session,
    user: CurrentUser,
    permission_key: str,
    *,
    resource: ResourceContext | None = None,
) -> None:
    try:
        AuthorizationService(session).require_permission(
            user.tenant_id, user.user_id, permission_key, resource=resource
        )
    except RbacError as exc:
        raise _http(exc) from exc


def _get_appointment_or_404(
    session: Session, user: CurrentUser, appointment_id: UUID
) -> dict[str, Any]:
    try:
        return AppointmentService(session).get(user.tenant_id, appointment_id)
    except Exception as exc:
        raise _http(exc) from exc


def _require_technician_or_404(
    session: Session, tenant_id: UUID, technician_id: UUID
) -> None:
    row = session.scalar(
        select(Technician).where(
            Technician.id == technician_id, Technician.tenant_id == tenant_id
        )
    )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "technician_not_found",
                "message": "Technician not found for tenant",
            },
        )


# --- Request bodies ---


class AppointmentCreateBody(BaseModel):
    model_config = {"extra": "forbid"}
    customer_id: UUID
    starts_at: datetime
    ends_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    service_type: str | None = None
    service_id: UUID | None = None
    location_id: UUID | None = None
    technician_id: UUID | None = None
    job_id: UUID | None = None
    lead_id: UUID | None = None
    call_id: UUID | None = None
    priority: str | None = None
    is_emergency: bool = False
    notes: str | None = None
    status: str | None = Field(default=None, max_length=32)
    idempotency_key: str | None = Field(default=None, max_length=128)


class AppointmentUpdateBody(BaseModel):
    model_config = {"extra": "forbid"}
    notes: str | None = None
    clear_notes: bool = False
    priority: str | None = None
    is_emergency: bool | None = None
    location_id: UUID | None = None
    clear_location: bool = False
    service_type: str | None = None
    status: str | None = Field(default=None, max_length=32)


class AssignBody(BaseModel):
    model_config = {"extra": "forbid"}
    technician_id: UUID | None = None


class TransitionBody(BaseModel):
    model_config = {"extra": "forbid"}
    to_status: str = Field(min_length=1, max_length=32)
    reason: str | None = Field(default=None, max_length=500)


class CancelBody(BaseModel):
    model_config = {"extra": "forbid"}
    reason: str | None = Field(default=None, max_length=500)


class RescheduleBody(BaseModel):
    model_config = {"extra": "forbid"}
    starts_at: datetime
    ends_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=1440)


class AvailabilityQueryBody(BaseModel):
    model_config = {"extra": "forbid"}
    from_date: date
    to_date: date
    service_id: UUID | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    technician_id: UUID | None = None
    is_emergency: bool = False
    location_id: UUID | None = None
    limit: int = Field(default=50, ge=1, le=500)


class BusinessHoursUpdateBody(BaseModel):
    model_config = {"extra": "forbid"}
    timezone: str | None = None
    slot_minutes: int | None = Field(default=None, ge=1, le=1440)
    booking_horizon_days: int | None = Field(default=None, ge=1, le=365)
    weekly_hours: dict[str, Any] | None = None
    emergency_weekly_hours: dict[str, Any] | None = None


class HolidayCreateBody(BaseModel):
    model_config = {"extra": "forbid"}
    holiday_date: date
    name: str = Field(min_length=1, max_length=255)
    is_full_day: bool = True


class SchedulePeriodBody(BaseModel):
    model_config = {"extra": "forbid"}
    day_of_week: int = Field(ge=0, le=6)
    open_time: str
    close_time: str


class BreakBody(BaseModel):
    model_config = {"extra": "forbid"}
    day_of_week: int = Field(ge=0, le=6)
    start_time: str
    end_time: str
    label: str | None = Field(default=None, max_length=128)


class TimeOffBody(BaseModel):
    model_config = {"extra": "forbid"}
    starts_at: datetime
    ends_at: datetime
    time_off_type: str = Field(min_length=1, max_length=32)
    reason: str | None = Field(default=None, max_length=500)


class SkillCreateBody(BaseModel):
    model_config = {"extra": "forbid"}
    key: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)


class ServiceAreaCreateBody(BaseModel):
    model_config = {"extra": "forbid"}
    key: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    match_type: str = Field(min_length=1, max_length=32)
    match_value: str = Field(min_length=1, max_length=128)


class RequiredSkillsBody(BaseModel):
    model_config = {"extra": "forbid"}
    skill_ids: list[UUID] = Field(default_factory=list)


# --- Appointments CRUD + lifecycle ---


@router.get("/appointments")
def list_appointments(
    q: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    customer_id: UUID | None = None,
    technician_id: UUID | None = None,
    service_id: UUID | None = None,
    location_id: UUID | None = None,
    job_id: UUID | None = None,
    is_emergency: bool | None = None,
    starts_from: datetime | None = None,
    starts_to: datetime | None = None,
    include_archived: bool = False,
    limit: int | None = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
) -> dict[str, Any]:
    mode = AuthorizationService(session).list_access_mode(
        user.tenant_id, user.user_id, "appointments.read"
    )
    if mode is None:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "permission_denied",
                "message": "Missing permission: appointments.read",
            },
        )
    tech_filter = technician_id
    if mode == "assigned":
        if not user.technician_id:
            return {"appointments": [], "next_cursor": None, "limit": limit or 50}
        tech_filter = user.technician_id
    try:
        return AppointmentService(session).list(
            user.tenant_id,
            q=q,
            status=status,
            priority=priority,
            customer_id=customer_id,
            technician_id=tech_filter,
            service_id=service_id,
            location_id=location_id,
            job_id=job_id,
            is_emergency=is_emergency,
            starts_from=starts_from,
            starts_to=starts_to,
            include_archived=include_archived,
            limit=limit,
            cursor=cursor,
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/appointments", status_code=201)
def create_appointment(
    body: AppointmentCreateBody,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_create),  # noqa: B008
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    try:
        appt = AppointmentService(session).create(
            user.tenant_id,
            customer_id=body.customer_id,
            starts_at=body.starts_at,
            actor=_actor(user),
            service_type=body.service_type,
            service_id=body.service_id,
            duration_minutes=body.duration_minutes,
            ends_at=body.ends_at,
            location_id=body.location_id,
            technician_id=body.technician_id,
            job_id=body.job_id,
            lead_id=body.lead_id,
            call_id=body.call_id,
            priority=body.priority,
            is_emergency=body.is_emergency,
            notes=body.notes,
            status=body.status,
            idempotency_key=idempotency_key or body.idempotency_key,
        )
        return {"appointment": appt}
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/appointments/{appointment_id}")
def get_appointment(
    appointment_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
) -> dict[str, Any]:
    appt = _get_appointment_or_404(session, user, appointment_id)
    _require_appointment_permission(
        session,
        user,
        "appointments.read",
        resource=_appointment_resource(session, user.tenant_id, appt),
    )
    return {"appointment": appt}


@router.patch("/appointments/{appointment_id}")
def update_appointment(
    appointment_id: UUID,
    body: AppointmentUpdateBody,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
) -> dict[str, Any]:
    existing = _get_appointment_or_404(session, user, appointment_id)
    _require_appointment_permission(
        session,
        user,
        "appointments.update",
        resource=_appointment_resource(session, user.tenant_id, existing),
    )
    try:
        appt = AppointmentService(session).update(
            user.tenant_id,
            appointment_id,
            actor=_actor(user),
            notes=body.notes,
            clear_notes=body.clear_notes,
            priority=body.priority,
            is_emergency=body.is_emergency,
            location_id=body.location_id,
            clear_location=body.clear_location,
            service_type=body.service_type,
            status=body.status,
        )
        return {"appointment": appt}
    except Exception as exc:
        raise _http(exc) from exc


@router.delete("/appointments/{appointment_id}")
def archive_appointment(
    appointment_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
) -> dict[str, Any]:
    existing = _get_appointment_or_404(session, user, appointment_id)
    _require_appointment_permission(
        session,
        user,
        "appointments.update",
        resource=_appointment_resource(session, user.tenant_id, existing),
    )
    try:
        return {
            "appointment": AppointmentService(session).archive(
                user.tenant_id, appointment_id, actor=_actor(user)
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/appointments/{appointment_id}/restore")
def restore_appointment(
    appointment_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
) -> dict[str, Any]:
    existing = _get_appointment_or_404(session, user, appointment_id)
    _require_appointment_permission(
        session,
        user,
        "appointments.update",
        resource=_appointment_resource(session, user.tenant_id, existing),
    )
    try:
        return {
            "appointment": AppointmentService(session).restore(
                user.tenant_id, appointment_id, actor=_actor(user)
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/appointments/{appointment_id}/assign")
def assign_appointment(
    appointment_id: UUID,
    body: AssignBody,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
) -> dict[str, Any]:
    existing = _get_appointment_or_404(session, user, appointment_id)
    _require_appointment_permission(
        session,
        user,
        "appointments.assign",
        resource=_appointment_resource(session, user.tenant_id, existing),
    )
    try:
        return {
            "appointment": AppointmentService(session).assign(
                user.tenant_id,
                appointment_id,
                technician_id=body.technician_id,
                actor=_actor(user),
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/appointments/{appointment_id}/transition")
def transition_appointment(
    appointment_id: UUID,
    body: TransitionBody,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
) -> dict[str, Any]:
    existing = _get_appointment_or_404(session, user, appointment_id)
    _require_appointment_permission(
        session,
        user,
        "appointments.transition",
        resource=_appointment_resource(session, user.tenant_id, existing),
    )
    try:
        return {
            "appointment": AppointmentService(session).transition(
                user.tenant_id,
                appointment_id,
                to_status=body.to_status,
                actor=_actor(user),
                reason=body.reason,
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/appointments/{appointment_id}/cancel")
def cancel_appointment(
    appointment_id: UUID,
    body: CancelBody,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
) -> dict[str, Any]:
    existing = _get_appointment_or_404(session, user, appointment_id)
    _require_appointment_permission(
        session,
        user,
        "appointments.cancel",
        resource=_appointment_resource(session, user.tenant_id, existing),
    )
    try:
        return {
            "appointment": AppointmentService(session).cancel(
                user.tenant_id, appointment_id, actor=_actor(user), reason=body.reason
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/appointments/{appointment_id}/reschedule")
def reschedule_appointment(
    appointment_id: UUID,
    body: RescheduleBody,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
) -> dict[str, Any]:
    existing = _get_appointment_or_404(session, user, appointment_id)
    _require_appointment_permission(
        session,
        user,
        "appointments.update",
        resource=_appointment_resource(session, user.tenant_id, existing),
    )
    try:
        return {
            "appointment": AppointmentService(session).reschedule(
                user.tenant_id,
                appointment_id,
                starts_at=body.starts_at,
                ends_at=body.ends_at,
                duration_minutes=body.duration_minutes,
                actor=_actor(user),
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/appointments/{appointment_id}/history")
def appointment_history(
    appointment_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
) -> dict[str, Any]:
    existing = _get_appointment_or_404(session, user, appointment_id)
    _require_appointment_permission(
        session,
        user,
        "appointments.read",
        resource=_appointment_resource(session, user.tenant_id, existing),
    )
    try:
        return {
            "history": AppointmentService(session).history(
                user.tenant_id, appointment_id
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


# --- Availability ---


@router.post("/appointments/availability")
def query_availability(
    body: AvailabilityQueryBody,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_availability_read),  # noqa: B008
) -> dict[str, Any]:
    try:
        return AvailabilityEngine(session).compute(
            user.tenant_id,
            from_date=body.from_date,
            to_date=body.to_date,
            service_id=body.service_id,
            duration_minutes=body.duration_minutes,
            technician_id=body.technician_id,
            is_emergency=body.is_emergency,
            location_id=body.location_id,
            limit=body.limit,
        )
    except Exception as exc:
        raise _http(exc) from exc


# --- Business hours + holidays ---


@router.get("/business-hours")
def get_business_hours(
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_business_hours_read),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {"business_hours": BusinessHoursService(session).get(user.tenant_id)}
    except Exception as exc:
        raise _http(exc) from exc


@router.patch("/business-hours")
def update_business_hours(
    body: BusinessHoursUpdateBody,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_business_hours_update),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "business_hours": BusinessHoursService(session).update(
                user.tenant_id,
                actor=_actor(user),
                timezone=body.timezone,
                slot_minutes=body.slot_minutes,
                booking_horizon_days=body.booking_horizon_days,
                weekly_hours=body.weekly_hours,
                emergency_weekly_hours=body.emergency_weekly_hours,
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/business-hours/holidays")
def list_holidays(
    from_date: date | None = None,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_business_hours_read),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "holidays": BusinessHoursService(session).list_holidays(
                user.tenant_id, from_date=from_date
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/business-hours/holidays", status_code=201)
def create_holiday(
    body: HolidayCreateBody,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_business_hours_update),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "holiday": BusinessHoursService(session).create_holiday(
                user.tenant_id,
                holiday_date=body.holiday_date,
                name=body.name,
                is_full_day=body.is_full_day,
                actor=_actor(user),
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.delete("/business-hours/holidays/{holiday_id}")
def delete_holiday(
    holiday_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_business_hours_update),  # noqa: B008
) -> dict[str, Any]:
    try:
        BusinessHoursService(session).delete_holiday(
            user.tenant_id, holiday_id, actor=_actor(user)
        )
        return {"deleted": True}
    except Exception as exc:
        raise _http(exc) from exc


# --- Technician schedule: periods / breaks / time off ---


@router.get("/technicians/{technician_id}/schedule-periods")
def list_schedule_periods(
    technician_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_technician_schedule_read),  # noqa: B008
) -> dict[str, Any]:
    _require_technician_or_404(session, user.tenant_id, technician_id)
    try:
        return {
            "periods": TechnicianAvailabilityService(session).list_periods(
                user.tenant_id, technician_id
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/technicians/{technician_id}/schedule-periods", status_code=201)
def create_schedule_period(
    technician_id: UUID,
    body: SchedulePeriodBody,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_technician_schedule_update),  # noqa: B008
) -> dict[str, Any]:
    _require_technician_or_404(session, user.tenant_id, technician_id)
    try:
        return {
            "period": TechnicianAvailabilityService(session).create_period(
                user.tenant_id,
                technician_id,
                day_of_week=body.day_of_week,
                open_time=body.open_time,
                close_time=body.close_time,
                actor=_actor(user),
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.delete("/technicians/{technician_id}/schedule-periods/{period_id}")
def delete_schedule_period(
    technician_id: UUID,
    period_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_technician_schedule_update),  # noqa: B008
) -> dict[str, Any]:
    _require_technician_or_404(session, user.tenant_id, technician_id)
    try:
        TechnicianAvailabilityService(session).delete_period(
            user.tenant_id, technician_id, period_id, actor=_actor(user)
        )
        return {"deleted": True}
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/technicians/{technician_id}/breaks")
def list_breaks(
    technician_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_technician_schedule_read),  # noqa: B008
) -> dict[str, Any]:
    _require_technician_or_404(session, user.tenant_id, technician_id)
    try:
        return {
            "breaks": TechnicianAvailabilityService(session).list_breaks(
                user.tenant_id, technician_id
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/technicians/{technician_id}/breaks", status_code=201)
def create_break(
    technician_id: UUID,
    body: BreakBody,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_technician_schedule_update),  # noqa: B008
) -> dict[str, Any]:
    _require_technician_or_404(session, user.tenant_id, technician_id)
    try:
        return {
            "break": TechnicianAvailabilityService(session).create_break(
                user.tenant_id,
                technician_id,
                day_of_week=body.day_of_week,
                start_time=body.start_time,
                end_time=body.end_time,
                label=body.label,
                actor=_actor(user),
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.delete("/technicians/{technician_id}/breaks/{break_id}")
def delete_break(
    technician_id: UUID,
    break_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_technician_schedule_update),  # noqa: B008
) -> dict[str, Any]:
    _require_technician_or_404(session, user.tenant_id, technician_id)
    try:
        TechnicianAvailabilityService(session).delete_break(
            user.tenant_id, technician_id, break_id, actor=_actor(user)
        )
        return {"deleted": True}
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/technicians/{technician_id}/time-off")
def list_time_off(
    technician_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_technician_schedule_read),  # noqa: B008
) -> dict[str, Any]:
    _require_technician_or_404(session, user.tenant_id, technician_id)
    try:
        return {
            "time_off": TechnicianAvailabilityService(session).list_time_off(
                user.tenant_id, technician_id
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/technicians/{technician_id}/time-off", status_code=201)
def create_time_off(
    technician_id: UUID,
    body: TimeOffBody,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_technician_schedule_update),  # noqa: B008
) -> dict[str, Any]:
    _require_technician_or_404(session, user.tenant_id, technician_id)
    try:
        return {
            "time_off": TechnicianAvailabilityService(session).create_time_off(
                user.tenant_id,
                technician_id,
                starts_at=body.starts_at,
                ends_at=body.ends_at,
                time_off_type=body.time_off_type,
                reason=body.reason,
                actor=_actor(user),
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.delete("/technicians/{technician_id}/time-off/{time_off_id}")
def delete_time_off(
    technician_id: UUID,
    time_off_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_technician_schedule_update),  # noqa: B008
) -> dict[str, Any]:
    _require_technician_or_404(session, user.tenant_id, technician_id)
    try:
        TechnicianAvailabilityService(session).delete_time_off(
            user.tenant_id, technician_id, time_off_id, actor=_actor(user)
        )
        return {"deleted": True}
    except Exception as exc:
        raise _http(exc) from exc


# --- Skills (tenant catalog + technician/service links) ---


@router.get("/skills")
def list_skills(
    include_archived: bool = False,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_technician_schedule_read),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "skills": TechnicianAvailabilityService(session).list_skills(
                user.tenant_id, include_archived=include_archived
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/skills", status_code=201)
def create_skill(
    body: SkillCreateBody,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_technician_schedule_update),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "skill": TechnicianAvailabilityService(session).create_skill(
                user.tenant_id, key=body.key, name=body.name, actor=_actor(user)
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.delete("/skills/{skill_id}")
def archive_skill(
    skill_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_technician_schedule_update),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "skill": TechnicianAvailabilityService(session).archive_skill(
                user.tenant_id, skill_id, actor=_actor(user)
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/technicians/{technician_id}/skills")
def list_technician_skills(
    technician_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_technician_schedule_read),  # noqa: B008
) -> dict[str, Any]:
    _require_technician_or_404(session, user.tenant_id, technician_id)
    try:
        return {
            "skills": TechnicianAvailabilityService(session).list_technician_skills(
                user.tenant_id, technician_id
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/technicians/{technician_id}/skills/{skill_id}", status_code=201)
def assign_technician_skill(
    technician_id: UUID,
    skill_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_technician_schedule_update),  # noqa: B008
) -> dict[str, Any]:
    _require_technician_or_404(session, user.tenant_id, technician_id)
    try:
        return TechnicianAvailabilityService(session).assign_technician_skill(
            user.tenant_id, technician_id, skill_id, actor=_actor(user)
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.delete("/technicians/{technician_id}/skills/{skill_id}")
def unassign_technician_skill(
    technician_id: UUID,
    skill_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_technician_schedule_update),  # noqa: B008
) -> dict[str, Any]:
    _require_technician_or_404(session, user.tenant_id, technician_id)
    try:
        TechnicianAvailabilityService(session).unassign_technician_skill(
            user.tenant_id, technician_id, skill_id, actor=_actor(user)
        )
        return {"deleted": True}
    except Exception as exc:
        raise _http(exc) from exc


@router.put("/services/{service_id}/required-skills")
def set_service_required_skills(
    service_id: UUID,
    body: RequiredSkillsBody,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_technician_schedule_update),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "skills": TechnicianAvailabilityService(
                session
            ).set_service_required_skills(
                user.tenant_id, service_id, body.skill_ids, actor=_actor(user)
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/services/{service_id}/required-skills")
def get_service_required_skills(
    service_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_technician_schedule_read),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "skills": TechnicianAvailabilityService(
                session
            ).list_service_required_skills(user.tenant_id, service_id)
        }
    except Exception as exc:
        raise _http(exc) from exc


# --- Service areas (tenant catalog + technician links) ---


@router.get("/service-areas")
def list_service_areas(
    include_archived: bool = False,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_technician_schedule_read),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "service_areas": TechnicianAvailabilityService(session).list_service_areas(
                user.tenant_id, include_archived=include_archived
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/service-areas", status_code=201)
def create_service_area(
    body: ServiceAreaCreateBody,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_technician_schedule_update),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "service_area": TechnicianAvailabilityService(session).create_service_area(
                user.tenant_id,
                key=body.key,
                name=body.name,
                match_type=body.match_type,
                match_value=body.match_value,
                actor=_actor(user),
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.delete("/service-areas/{service_area_id}")
def archive_service_area(
    service_area_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_technician_schedule_update),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "service_area": TechnicianAvailabilityService(session).archive_service_area(
                user.tenant_id, service_area_id, actor=_actor(user)
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/technicians/{technician_id}/service-areas")
def list_technician_service_areas(
    technician_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_technician_schedule_read),  # noqa: B008
) -> dict[str, Any]:
    _require_technician_or_404(session, user.tenant_id, technician_id)
    try:
        return {
            "service_areas": TechnicianAvailabilityService(
                session
            ).list_technician_service_areas(user.tenant_id, technician_id)
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.post(
    "/technicians/{technician_id}/service-areas/{service_area_id}", status_code=201
)
def assign_technician_service_area(
    technician_id: UUID,
    service_area_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_technician_schedule_update),  # noqa: B008
) -> dict[str, Any]:
    _require_technician_or_404(session, user.tenant_id, technician_id)
    try:
        return TechnicianAvailabilityService(session).assign_technician_service_area(
            user.tenant_id, technician_id, service_area_id, actor=_actor(user)
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.delete("/technicians/{technician_id}/service-areas/{service_area_id}")
def unassign_technician_service_area(
    technician_id: UUID,
    service_area_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_technician_schedule_update),  # noqa: B008
) -> dict[str, Any]:
    _require_technician_or_404(session, user.tenant_id, technician_id)
    try:
        TechnicianAvailabilityService(session).unassign_technician_service_area(
            user.tenant_id, technician_id, service_area_id, actor=_actor(user)
        )
        return {"deleted": True}
    except Exception as exc:
        raise _http(exc) from exc

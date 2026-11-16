"""Admin Dispatch CRM APIs (Phase 12)."""

from __future__ import annotations

from datetime import datetime
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
from callbot_platform.crm.dispatch.assignment import DispatchAssignmentService
from callbot_platform.crm.dispatch.board import DispatchBoardService
from callbot_platform.crm.dispatch.events import list_events_after
from callbot_platform.crm.dispatch.status import TechnicianStatusService
from callbot_platform.crm.errors import CrmError
from callbot_platform.db.models.jobs import Technician
from callbot_platform.rbac.errors import RbacError
from callbot_platform.rbac.service import AuthorizationService, ResourceContext

router = APIRouter(prefix="/api/admin/crm/dispatch", tags=["dispatch"])

_require_read = require_entitled_permission("dispatch.read")
_require_assign = require_entitled_permission("jobs.assign")
_require_tech_read = require_entitled_permission("technicians.read")
_require_status = require_entitled_permission("dispatch.status.update")


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, RbacError):
        return HTTPException(
            status_code=403, detail={"code": exc.code, "message": str(exc)}
        )
    if isinstance(exc, CrmError):
        status = (
            404 if exc.code == "not_found" or exc.code.endswith("_not_found") else 400
        )
        if exc.code == "forbidden":
            status = 403
        if exc.code in {
            "status_transition_invalid",
            "job_not_assignable",
            "job_archived",
            "idempotency_conflict",
            "assignment_conflict",
            "technician_unavailable",
            "technician_ineligible",
            "skill_mismatch",
            "service_area_mismatch",
            "schedule_conflict",
            "time_off_conflict",
            "invalid_transition",
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


class StatusBody(BaseModel):
    model_config = {"extra": "forbid"}
    to_status: str = Field(min_length=1, max_length=32)
    reason: str | None = Field(default=None, max_length=500)


class AssignBody(BaseModel):
    model_config = {"extra": "forbid"}
    technician_id: UUID | None = None
    reason: str | None = Field(default=None, max_length=500)
    eta: datetime | None = None
    eta_source: str | None = Field(default=None, max_length=32)
    idempotency_key: str | None = Field(default=None, max_length=128)


@router.get("/board")
def get_board(
    date: str | None = Query(default=None),
    technician_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    assigned: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=1000),
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_read),  # noqa: B008
) -> dict[str, Any]:
    try:
        svc = DispatchBoardService(session)
        return svc.board(
            user.tenant_id,
            board_date=svc.parse_date(date),
            technician_id=technician_id,
            status=status,
            priority=priority,
            assigned=assigned,
            q=q,
            limit=limit,
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/events")
def get_events(
    after_id: UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_read),  # noqa: B008
) -> dict[str, Any]:
    events = list_events_after(session, user.tenant_id, after_id=after_id, limit=limit)
    return {"events": events}


@router.post("/jobs/{job_id}/assign")
def assign_job(
    job_id: UUID,
    body: AssignBody,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_assign),  # noqa: B008
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    try:
        job = DispatchAssignmentService(session).assign(
            user.tenant_id,
            job_id,
            technician_id=body.technician_id,
            actor=_actor(user),
            reason=body.reason,
            idempotency_key=idempotency_key or body.idempotency_key,
            eta=body.eta,
            eta_source=body.eta_source,
        )
        return {"job": job}
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/jobs/{job_id}/assignment-history")
def assignment_history(
    job_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_read),  # noqa: B008
) -> dict[str, Any]:
    try:
        rows = DispatchAssignmentService(session).history(user.tenant_id, job_id)
        return {"history": rows}
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/technicians/{technician_id}/status")
def get_technician_status(
    technician_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_tech_read),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "status": TechnicianStatusService(session).get(
                user.tenant_id, technician_id
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/technicians/{technician_id}/status")
def set_technician_status(
    technician_id: UUID,
    body: StatusBody,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
) -> dict[str, Any]:
    """Dispatchers use dispatch.status.update; technicians may update own status."""
    try:
        auth = AuthorizationService(session)
        allow_self_only = False
        try:
            auth.require_permission(
                user,
                "dispatch.status.update",
                resource=ResourceContext(tenant_id=user.tenant_id),
            )
        except RbacError:
            # Fall back: technician updating own status via technicians.manage? No —
            # use jobs.update SCOPE_ASSIGNED pattern: allow if linked technician user.
            tech = session.scalar(
                select(Technician).where(
                    Technician.id == technician_id,
                    Technician.tenant_id == user.tenant_id,
                )
            )
            if tech is None or tech.user_id != user.user_id:
                raise CrmError(
                    "forbidden", "Not allowed to update this status"
                ) from None
            allow_self_only = True

        result = TechnicianStatusService(session).transition(
            user.tenant_id,
            technician_id,
            to_status=body.to_status,
            actor=_actor(user),
            reason=body.reason,
            actor_user_id=user.user_id,
            allow_self_only=allow_self_only,
        )
        return {"status": result}
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/technicians/{technician_id}/status-history")
def technician_status_history(
    technician_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_read),  # noqa: B008
) -> dict[str, Any]:
    try:
        rows = TechnicianStatusService(session).history(user.tenant_id, technician_id)
        return {"history": rows}
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/technicians/{technician_id}")
def technician_ops_detail(
    technician_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_tech_read),  # noqa: B008
) -> dict[str, Any]:
    """Composite technician operations view (profile + status + schedule facts)."""
    try:
        tech = session.scalar(
            select(Technician).where(
                Technician.id == technician_id,
                Technician.tenant_id == user.tenant_id,
            )
        )
        if tech is None:
            raise CrmError("technician_not_found", "Technician not found for tenant")
        from callbot_platform.crm.appointments.technician_availability import (
            TechnicianAvailabilityService,
        )

        avail = TechnicianAvailabilityService(session)
        status = TechnicianStatusService(session).get(user.tenant_id, technician_id)
        return {
            "technician": {
                "id": str(tech.id),
                "display_name": tech.display_name,
                "phone": tech.phone,
                "is_active": tech.is_active,
                "user_id": str(tech.user_id),
            },
            "status": status,
            "skills": avail.list_technician_skills(user.tenant_id, technician_id),
            "service_areas": avail.list_technician_service_areas(
                user.tenant_id, technician_id
            ),
            "schedule_periods": avail.list_periods(user.tenant_id, technician_id),
            "breaks": avail.list_breaks(user.tenant_id, technician_id),
            "time_off": avail.list_time_off(user.tenant_id, technician_id),
            "status_history": TechnicianStatusService(session).history(
                user.tenant_id, technician_id, limit=50
            ),
        }
    except Exception as exc:
        raise _http(exc) from exc

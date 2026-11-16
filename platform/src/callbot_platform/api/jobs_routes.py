"""Session-authenticated jobs / technicians ops API."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.api.deps import (
    CurrentUser,
    db_dep,
    require_entitled_permission,
    require_entitled_tenant_user,
)
from callbot_platform.db.models.jobs import Technician
from callbot_platform.jobs.repos import JobRepository, JobsError, TechnicianRepository
from callbot_platform.rbac.errors import RbacError
from callbot_platform.rbac.service import AuthorizationService, ResourceContext

router = APIRouter(prefix="/api", tags=["ops"])

_require_tech_read = require_entitled_permission("technicians.read")
_require_tech_manage = require_entitled_permission("technicians.manage")
_require_jobs_create = require_entitled_permission("jobs.create")
_require_jobs_assign = require_entitled_permission("jobs.assign")


class CreateTechnicianBody(BaseModel):
    email: str
    password: str = Field(min_length=8)
    name: str
    phone: str | None = None


class CreateJobBody(BaseModel):
    customer_id: UUID
    service_type: str
    status: str = "NEW"
    scheduled_starts_at: datetime | None = None
    scheduled_ends_at: datetime | None = None


class AssignBody(BaseModel):
    technician_id: UUID


class TransitionBody(BaseModel):
    status: str
    completion_notes: str | None = None


class ChecklistBody(BaseModel):
    checklist: list[dict[str, Any]]


class NoteBody(BaseModel):
    body: str


class LocationBody(BaseModel):
    lat: float
    lng: float


def _jobs_http(exc: Exception) -> HTTPException:
    if isinstance(exc, JobsError):
        status = 404 if "not_found" in exc.code else 400
        if exc.code in {
            "invalid_transition",
            "job_archived",
            "idempotency_conflict",
            "assignment_conflict",
            "technician_unavailable",
            "technician_ineligible",
            "skill_mismatch",
            "service_area_mismatch",
            "schedule_conflict",
            "time_off_conflict",
            "job_not_assignable",
            "status_transition_invalid",
        }:
            status = 409
        return HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        )
    return HTTPException(
        status_code=500, detail={"code": "internal", "message": "Internal error"}
    )


def _rbac_http(exc: RbacError) -> HTTPException:
    return HTTPException(
        status_code=403, detail={"code": exc.code, "message": str(exc)}
    )


def _assigned_user_id(
    session: Session, tenant_id: UUID, job: dict[str, Any]
) -> UUID | None:
    tech_id = job.get("assigned_technician_id")
    if not tech_id:
        return None
    tech = session.scalar(
        select(Technician).where(
            Technician.id == UUID(str(tech_id)),
            Technician.tenant_id == tenant_id,
        )
    )
    return tech.user_id if tech is not None else None


def _job_resource(
    session: Session, tenant_id: UUID, job: dict[str, Any]
) -> ResourceContext:
    return ResourceContext(
        tenant_id=tenant_id,
        assigned_technician_user_id=_assigned_user_id(session, tenant_id, job),
    )


def _require_job_permission(
    session: Session,
    user: CurrentUser,
    permission_key: str,
    *,
    resource: ResourceContext | None = None,
) -> None:
    try:
        AuthorizationService(session).require_permission(
            user.tenant_id,
            user.user_id,
            permission_key,
            resource=resource,
        )
    except RbacError as exc:
        raise _rbac_http(exc) from exc


@router.get("/technicians")
def list_technicians(
    user: CurrentUser = Depends(_require_tech_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    techs = TechnicianRepository(session).list(user.tenant_id)
    return {"technicians": techs}


@router.post("/technicians")
def create_technician(
    body: CreateTechnicianBody,
    user: CurrentUser = Depends(_require_tech_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        tech = TechnicianRepository(session).create(
            user.tenant_id,
            email=body.email,
            password=body.password,
            name=body.name,
            phone=body.phone,
            actor=user.email,
        )
        return {"technician": tech}
    except Exception as exc:
        from callbot_platform.auth.repos import AuthError

        if isinstance(exc, AuthError):
            raise HTTPException(
                status_code=400, detail={"code": exc.code, "message": str(exc)}
            ) from exc
        raise _jobs_http(exc) from exc


@router.get("/jobs")
def list_jobs(
    status: str | None = None,
    technician_id: UUID | None = None,
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    mode = AuthorizationService(session).list_access_mode(
        user.tenant_id, user.user_id, "jobs.read"
    )
    if mode is None:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "permission_denied",
                "message": "Missing permission: jobs.read",
            },
        )
    tech_filter = technician_id
    if mode == "assigned":
        if not user.technician_id:
            return {"jobs": []}
        tech_filter = user.technician_id
    jobs = JobRepository(session).list(
        user.tenant_id, status=status, technician_id=tech_filter
    )
    return {"jobs": jobs}


@router.post("/jobs")
def create_job(
    body: CreateJobBody,
    user: CurrentUser = Depends(_require_jobs_create),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        job = JobRepository(session).create(
            user.tenant_id,
            customer_id=body.customer_id,
            service_type=body.service_type,
            status=body.status,
            scheduled_starts_at=body.scheduled_starts_at,
            scheduled_ends_at=body.scheduled_ends_at,
            actor=user.email,
        )
        return {"job": job}
    except Exception as exc:
        raise _jobs_http(exc) from exc


@router.get("/jobs/{job_id}")
def get_job(
    job_id: UUID,
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    job = JobRepository(session).get(user.tenant_id, job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "job_not_found", "message": "Job not found"},
        )
    _require_job_permission(
        session,
        user,
        "jobs.read",
        resource=_job_resource(session, user.tenant_id, job),
    )
    return {"job": job}


@router.post("/jobs/{job_id}/assign")
def assign_job(
    job_id: UUID,
    body: AssignBody,
    user: CurrentUser = Depends(_require_jobs_assign),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        job = JobRepository(session).assign(
            user.tenant_id,
            job_id,
            technician_id=body.technician_id,
            actor=user.email,
        )
        return {"job": job}
    except Exception as exc:
        raise _jobs_http(exc) from exc


@router.post("/jobs/{job_id}/transition")
def transition_job(
    job_id: UUID,
    body: TransitionBody,
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    job = JobRepository(session).get(user.tenant_id, job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "job_not_found", "message": "Job not found"},
        )
    resource = _job_resource(session, user.tenant_id, job)
    _require_job_permission(session, user, "jobs.update", resource=resource)

    # Field techs with ASSIGNED-only access may only start/complete.
    mode = AuthorizationService(session).list_access_mode(
        user.tenant_id, user.user_id, "jobs.update"
    )
    grants = AuthorizationService(session).resolve_member_permissions(
        user.tenant_id, user.user_id
    )
    has_org_wide_update = any(
        g.key == "jobs.update" and g.scope == "ALL_ORGANIZATION" for g in grants
    )
    if not has_org_wide_update and mode == "assigned":
        allowed = {"IN_PROGRESS", "COMPLETED", "in_progress", "completed"}
        if body.status not in allowed and body.status.upper().replace("-", "_") not in {
            "IN_PROGRESS",
            "COMPLETED",
        }:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "permission_denied",
                    "message": "Assigned scope may only start or complete jobs",
                },
            )
    try:
        job = JobRepository(session).transition(
            user.tenant_id,
            job_id,
            status=body.status,
            completion_notes=body.completion_notes,
            actor_user_id=user.user_id,
            actor=user.email,
        )
        return {"job": job}
    except Exception as exc:
        raise _jobs_http(exc) from exc


@router.put("/jobs/{job_id}/checklist")
def update_checklist(
    job_id: UUID,
    body: ChecklistBody,
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    job = JobRepository(session).get(user.tenant_id, job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "job_not_found", "message": "Job not found"},
        )
    _require_job_permission(
        session,
        user,
        "jobs.update",
        resource=_job_resource(session, user.tenant_id, job),
    )
    try:
        job = JobRepository(session).update_checklist(
            user.tenant_id,
            job_id,
            checklist=body.checklist,
            actor=user.email,
        )
        return {"job": job}
    except Exception as exc:
        raise _jobs_http(exc) from exc


@router.post("/jobs/{job_id}/notes")
def add_note(
    job_id: UUID,
    body: NoteBody,
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    job = JobRepository(session).get(user.tenant_id, job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "job_not_found", "message": "Job not found"},
        )
    _require_job_permission(
        session,
        user,
        "jobs.update",
        resource=_job_resource(session, user.tenant_id, job),
    )
    try:
        job = JobRepository(session).add_note(
            user.tenant_id,
            job_id,
            body=body.body,
            author_user_id=user.user_id,
            actor=user.email,
        )
        return {"job": job}
    except Exception as exc:
        raise _jobs_http(exc) from exc


@router.post("/tech/location")
def update_location(
    body: LocationBody,
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    if not user.technician_id:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "permission_denied",
                "message": "Technician profile required",
            },
        )
    # Treat self-location as an ASSIGNED self-resource (fail-closed without identity).
    _require_job_permission(
        session,
        user,
        "jobs.update",
        resource=ResourceContext(
            tenant_id=user.tenant_id,
            assigned_technician_user_id=user.user_id,
        ),
    )
    try:
        tech = TechnicianRepository(session).update_location(
            user.tenant_id,
            user.technician_id,
            lat=body.lat,
            lng=body.lng,
        )
        return {"technician": tech}
    except Exception as exc:
        raise _jobs_http(exc) from exc

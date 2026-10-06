"""Session-authenticated jobs / technicians ops API."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from callbot_platform.api.deps import (
    CurrentUser,
    db_dep,
    require_entitled_ops_roles,
    require_entitled_tenant_user,
)
from callbot_platform.jobs.repos import JobRepository, JobsError, TechnicianRepository
from callbot_platform.security.session import (
    OPS_ROLES,
    ROLE_ADMIN,
    ROLE_DISPATCHER,
    ROLE_TECHNICIAN,
)

router = APIRouter(prefix="/api", tags=["ops"])


class CreateTechnicianBody(BaseModel):
    email: str
    password: str = Field(min_length=8)
    name: str
    phone: str | None = None


class CreateJobBody(BaseModel):
    customer_id: UUID
    service_type: str
    status: str = "new"
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
        if exc.code == "invalid_transition":
            status = 409
        return HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        )
    return HTTPException(
        status_code=500, detail={"code": "internal", "message": str(exc)}
    )


@router.get("/technicians")
def list_technicians(
    user: CurrentUser = Depends(require_entitled_ops_roles(*OPS_ROLES)),
    session: Session = Depends(db_dep),
) -> dict[str, Any]:
    techs = TechnicianRepository(session).list(user.tenant_id)
    return {"technicians": techs}


@router.post("/technicians")
def create_technician(
    body: CreateTechnicianBody,
    user: CurrentUser = Depends(
        require_entitled_ops_roles(ROLE_ADMIN, ROLE_DISPATCHER)
    ),
    session: Session = Depends(db_dep),
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
    user: CurrentUser = Depends(require_entitled_tenant_user),
    session: Session = Depends(db_dep),
) -> dict[str, Any]:
    tech_filter = technician_id
    if user.role == ROLE_TECHNICIAN:
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
    user: CurrentUser = Depends(
        require_entitled_ops_roles(ROLE_ADMIN, ROLE_DISPATCHER)
    ),
    session: Session = Depends(db_dep),
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
    user: CurrentUser = Depends(require_entitled_tenant_user),
    session: Session = Depends(db_dep),
) -> dict[str, Any]:
    job = JobRepository(session).get(user.tenant_id, job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "job_not_found", "message": "Job not found"},
        )
    if user.role == ROLE_TECHNICIAN:
        if job.get("assigned_technician_id") != (
            str(user.technician_id) if user.technician_id else None
        ):
            raise HTTPException(status_code=403, detail="Not assigned to this job")
    return {"job": job}


@router.post("/jobs/{job_id}/assign")
def assign_job(
    job_id: UUID,
    body: AssignBody,
    user: CurrentUser = Depends(
        require_entitled_ops_roles(ROLE_ADMIN, ROLE_DISPATCHER)
    ),
    session: Session = Depends(db_dep),
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
    user: CurrentUser = Depends(require_entitled_tenant_user),
    session: Session = Depends(db_dep),
) -> dict[str, Any]:
    # Technicians may start/complete; dispatchers/admins may dispatch/cancel/etc.
    if user.role == ROLE_TECHNICIAN:
        allowed = {"in_progress", "completed"}
        if body.status not in allowed:
            raise HTTPException(
                status_code=403,
                detail="Technicians may only start or complete jobs",
            )
        job = JobRepository(session).get(user.tenant_id, job_id)
        if job is None or job.get("assigned_technician_id") != (
            str(user.technician_id) if user.technician_id else None
        ):
            raise HTTPException(status_code=403, detail="Not assigned to this job")
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
    user: CurrentUser = Depends(require_entitled_tenant_user),
    session: Session = Depends(db_dep),
) -> dict[str, Any]:
    if user.role == ROLE_TECHNICIAN:
        job = JobRepository(session).get(user.tenant_id, job_id)
        if job is None or job.get("assigned_technician_id") != (
            str(user.technician_id) if user.technician_id else None
        ):
            raise HTTPException(status_code=403, detail="Not assigned to this job")
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
    user: CurrentUser = Depends(require_entitled_tenant_user),
    session: Session = Depends(db_dep),
) -> dict[str, Any]:
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
    user: CurrentUser = Depends(require_entitled_tenant_user),
    session: Session = Depends(db_dep),
) -> dict[str, Any]:
    if user.role != ROLE_TECHNICIAN or not user.technician_id:
        raise HTTPException(status_code=403, detail="Technician role required")
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

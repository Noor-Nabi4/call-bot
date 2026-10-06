"""Admin Job CRM APIs (Phase 10).

Several job permissions (``jobs.read``, ``jobs.update``, ``jobs.notes.read``,
``jobs.notes.create``, ``jobs.attachments.read``, ``jobs.attachments.create``)
support an ``ASSIGNED`` scope for the Technician role (see
``rbac/catalog.py``). ``AuthorizationService.require_permission`` fails
closed for scoped grants unless a ``ResourceContext`` is supplied, so every
job-scoped endpoint here fetches the job first (404 before 403, matching the
legacy ``/api/jobs`` behavior) and then checks permission with the job's
assigned-technician resource context — mirroring ``api/jobs_routes.py``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    UploadFile,
)
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
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.jobs import JobService
from callbot_platform.crm.jobs.attachments import JobAttachmentService
from callbot_platform.crm.jobs.constants import ATTACHMENT_MAX_BYTES
from callbot_platform.crm.jobs.notes import JobNotesService
from callbot_platform.db.models.jobs import Technician
from callbot_platform.rbac.errors import RbacError
from callbot_platform.rbac.service import AuthorizationService, ResourceContext

router = APIRouter(prefix="/api/admin/crm", tags=["jobs"])

# Create has no per-resource scope (Technician is never granted jobs.create).
_require_create = require_entitled_permission("jobs.create")


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, RbacError):
        return HTTPException(
            status_code=403,
            detail={"code": exc.code, "message": str(exc)},
        )
    if isinstance(exc, CrmError):
        status = 404 if exc.code == "not_found" else 400
        if exc.code == "forbidden":
            status = 403
        if exc.code.endswith("_not_found"):
            status = 404
        if exc.code in {
            "invalid_transition",
            "job_archived",
            "use_transition",
            "archive_not_allowed",
            "job_conflict",
            "technician_required",
            "idempotency_conflict",
            "job_immutable",
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


def _job_resource(
    session: Session, tenant_id: UUID, job: dict[str, Any]
) -> ResourceContext:
    tech_id = job.get("assigned_technician_id")
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


def _require_job_permission(
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


def _get_job_or_404(
    session: Session, user: CurrentUser, job_id: UUID
) -> dict[str, Any]:
    try:
        return JobService(session).get(user.tenant_id, job_id)
    except Exception as exc:
        raise _http(exc) from exc


class JobCreateBody(BaseModel):
    model_config = {"extra": "forbid"}
    customer_id: UUID
    service_type: str | None = None
    service_id: UUID | None = None
    location_id: UUID | None = None
    description: str | None = None
    priority: str | None = None
    technician_id: UUID | None = None
    scheduled_starts_at: datetime | None = None
    scheduled_ends_at: datetime | None = None
    appointment_id: UUID | None = None
    lead_id: UUID | None = None
    call_id: UUID | None = None
    status: str | None = Field(default=None, max_length=32)
    idempotency_key: str | None = Field(default=None, max_length=128)


class JobUpdateBody(BaseModel):
    model_config = {"extra": "forbid"}
    description: str | None = None
    clear_description: bool = False
    priority: str | None = None
    location_id: UUID | None = None
    clear_location: bool = False
    service_id: UUID | None = None
    clear_service: bool = False
    service_type: str | None = None
    scheduled_starts_at: datetime | None = None
    scheduled_ends_at: datetime | None = None
    clear_schedule: bool = False
    status: str | None = Field(default=None, max_length=32)


class AssignBody(BaseModel):
    model_config = {"extra": "forbid"}
    technician_id: UUID | None = None


class TransitionBody(BaseModel):
    model_config = {"extra": "forbid"}
    to_status: str = Field(min_length=1, max_length=32)
    reason: str | None = Field(default=None, max_length=500)
    completion_notes: str | None = Field(default=None, max_length=8000)


class NoteCreateBody(BaseModel):
    model_config = {"extra": "forbid"}
    body: str = Field(min_length=1, max_length=8000)


class NoteUpdateBody(BaseModel):
    model_config = {"extra": "forbid"}
    body: str = Field(min_length=1, max_length=8000)


@router.get("/jobs")
def list_jobs(
    q: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    customer_id: UUID | None = None,
    technician_id: UUID | None = None,
    service_id: UUID | None = None,
    location_id: UUID | None = None,
    scheduled_from: datetime | None = None,
    scheduled_to: datetime | None = None,
    include_archived: bool = False,
    limit: int | None = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
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
            return {"jobs": [], "next_cursor": None, "limit": limit or 50}
        tech_filter = user.technician_id
    try:
        return JobService(session).list(
            user.tenant_id,
            q=q,
            status=status,
            priority=priority,
            customer_id=customer_id,
            technician_id=tech_filter,
            service_id=service_id,
            location_id=location_id,
            scheduled_from=scheduled_from,
            scheduled_to=scheduled_to,
            include_archived=include_archived,
            limit=limit,
            cursor=cursor,
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/jobs", status_code=201)
def create_job(
    body: JobCreateBody,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_create),  # noqa: B008
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    try:
        job = JobService(session).create(
            user.tenant_id,
            customer_id=body.customer_id,
            actor=_actor(user),
            service_type=body.service_type,
            service_id=body.service_id,
            location_id=body.location_id,
            description=body.description,
            priority=body.priority,
            technician_id=body.technician_id,
            scheduled_starts_at=body.scheduled_starts_at,
            scheduled_ends_at=body.scheduled_ends_at,
            appointment_id=body.appointment_id,
            lead_id=body.lead_id,
            call_id=body.call_id,
            status=body.status,
            idempotency_key=idempotency_key or body.idempotency_key,
        )
        return {"job": job}
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/jobs/{job_id}")
def get_job(
    job_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
) -> dict[str, Any]:
    job = _get_job_or_404(session, user, job_id)
    _require_job_permission(
        session, user, "jobs.read", resource=_job_resource(session, user.tenant_id, job)
    )
    return {"job": job}


@router.patch("/jobs/{job_id}")
def update_job(
    job_id: UUID,
    body: JobUpdateBody,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
) -> dict[str, Any]:
    existing = _get_job_or_404(session, user, job_id)
    _require_job_permission(
        session,
        user,
        "jobs.update",
        resource=_job_resource(session, user.tenant_id, existing),
    )
    try:
        job = JobService(session).update(
            user.tenant_id,
            job_id,
            actor=_actor(user),
            description=body.description,
            clear_description=body.clear_description,
            priority=body.priority,
            location_id=body.location_id,
            clear_location=body.clear_location,
            service_id=body.service_id,
            clear_service=body.clear_service,
            service_type=body.service_type,
            scheduled_starts_at=body.scheduled_starts_at,
            scheduled_ends_at=body.scheduled_ends_at,
            clear_schedule=body.clear_schedule,
            status=body.status,
        )
        return {"job": job}
    except Exception as exc:
        raise _http(exc) from exc


@router.delete("/jobs/{job_id}")
def archive_job(
    job_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
) -> dict[str, Any]:
    existing = _get_job_or_404(session, user, job_id)
    _require_job_permission(
        session,
        user,
        "jobs.delete",
        resource=_job_resource(session, user.tenant_id, existing),
    )
    try:
        return {
            "job": JobService(session).archive(
                user.tenant_id, job_id, actor=_actor(user)
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/jobs/{job_id}/restore")
def restore_job(
    job_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
) -> dict[str, Any]:
    existing = _get_job_or_404(session, user, job_id)
    _require_job_permission(
        session,
        user,
        "jobs.update",
        resource=_job_resource(session, user.tenant_id, existing),
    )
    try:
        return {
            "job": JobService(session).restore(
                user.tenant_id, job_id, actor=_actor(user)
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/jobs/{job_id}/assign")
def assign_job(
    job_id: UUID,
    body: AssignBody,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
) -> dict[str, Any]:
    existing = _get_job_or_404(session, user, job_id)
    _require_job_permission(
        session,
        user,
        "jobs.assign",
        resource=_job_resource(session, user.tenant_id, existing),
    )
    try:
        return {
            "job": JobService(session).assign(
                user.tenant_id,
                job_id,
                technician_id=body.technician_id,
                actor=_actor(user),
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/jobs/{job_id}/transition")
def transition_job(
    job_id: UUID,
    body: TransitionBody,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
) -> dict[str, Any]:
    existing = _get_job_or_404(session, user, job_id)
    _require_job_permission(
        session,
        user,
        "jobs.transition",
        resource=_job_resource(session, user.tenant_id, existing),
    )
    try:
        return {
            "job": JobService(session).transition(
                user.tenant_id,
                job_id,
                to_status=body.to_status,
                actor=_actor(user),
                reason=body.reason,
                completion_notes=body.completion_notes,
                actor_user_id=user.user_id,
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/jobs/{job_id}/history")
def job_history(
    job_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
) -> dict[str, Any]:
    existing = _get_job_or_404(session, user, job_id)
    _require_job_permission(
        session,
        user,
        "jobs.read",
        resource=_job_resource(session, user.tenant_id, existing),
    )
    try:
        return {"history": JobService(session).history(user.tenant_id, job_id)}
    except Exception as exc:
        raise _http(exc) from exc


# --- Notes ---


@router.get("/jobs/{job_id}/notes")
def list_job_notes(
    job_id: UUID,
    include_archived: bool = False,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
) -> dict[str, Any]:
    existing = _get_job_or_404(session, user, job_id)
    _require_job_permission(
        session,
        user,
        "jobs.notes.read",
        resource=_job_resource(session, user.tenant_id, existing),
    )
    try:
        notes = JobNotesService(session).list(
            user.tenant_id, job_id, include_archived=include_archived
        )
        return {"notes": notes}
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/jobs/{job_id}/notes", status_code=201)
def create_job_note(
    job_id: UUID,
    body: NoteCreateBody,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
) -> dict[str, Any]:
    existing = _get_job_or_404(session, user, job_id)
    _require_job_permission(
        session,
        user,
        "jobs.notes.create",
        resource=_job_resource(session, user.tenant_id, existing),
    )
    try:
        note = JobNotesService(session).create(
            user.tenant_id,
            job_id,
            body=body.body,
            actor=_actor(user),
            author_user_id=user.user_id,
        )
        return {"note": note}
    except Exception as exc:
        raise _http(exc) from exc


@router.patch("/jobs/{job_id}/notes/{note_id}")
def update_job_note(
    job_id: UUID,
    note_id: UUID,
    body: NoteUpdateBody,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
) -> dict[str, Any]:
    existing = _get_job_or_404(session, user, job_id)
    _require_job_permission(
        session,
        user,
        "jobs.notes.update",
        resource=_job_resource(session, user.tenant_id, existing),
    )
    try:
        note = JobNotesService(session).update(
            user.tenant_id,
            job_id,
            note_id,
            body=body.body,
            actor=_actor(user),
        )
        return {"note": note}
    except Exception as exc:
        raise _http(exc) from exc


@router.delete("/jobs/{job_id}/notes/{note_id}")
def archive_job_note(
    job_id: UUID,
    note_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
) -> dict[str, Any]:
    existing = _get_job_or_404(session, user, job_id)
    _require_job_permission(
        session,
        user,
        "jobs.notes.delete",
        resource=_job_resource(session, user.tenant_id, existing),
    )
    try:
        note = JobNotesService(session).archive(
            user.tenant_id, job_id, note_id, actor=_actor(user)
        )
        return {"note": note}
    except Exception as exc:
        raise _http(exc) from exc


# --- Attachments ---


@router.get("/jobs/{job_id}/attachments")
def list_job_attachments(
    job_id: UUID,
    include_archived: bool = False,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
) -> dict[str, Any]:
    existing = _get_job_or_404(session, user, job_id)
    _require_job_permission(
        session,
        user,
        "jobs.attachments.read",
        resource=_job_resource(session, user.tenant_id, existing),
    )
    try:
        attachments = JobAttachmentService(session).list(
            user.tenant_id, job_id, include_archived=include_archived
        )
        return {"attachments": attachments}
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/jobs/{job_id}/attachments", status_code=201)
async def upload_job_attachment(
    job_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
    file: UploadFile = File(...),  # noqa: B008
    filename: str | None = Form(default=None),
) -> dict[str, Any]:
    existing = _get_job_or_404(session, user, job_id)
    _require_job_permission(
        session,
        user,
        "jobs.attachments.create",
        resource=_job_resource(session, user.tenant_id, existing),
    )
    try:
        # Bound read so oversized uploads fail before buffering the whole body.
        chunk = await file.read(ATTACHMENT_MAX_BYTES + 1)
        if len(chunk) > ATTACHMENT_MAX_BYTES:
            raise CrmError("invalid_attachment", "File exceeds size limit")
        content_type = file.content_type or "application/octet-stream"
        attachment = JobAttachmentService(session).upload(
            user.tenant_id,
            job_id,
            filename=filename or file.filename or "attachment",
            content_type=content_type,
            data=chunk,
            actor=_actor(user),
        )
        return {"attachment": attachment}
    except Exception as exc:
        raise _http(exc) from exc


@router.delete("/jobs/{job_id}/attachments/{attachment_id}")
def archive_job_attachment(
    job_id: UUID,
    attachment_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(require_entitled_tenant_user),  # noqa: B008
) -> dict[str, Any]:
    existing = _get_job_or_404(session, user, job_id)
    _require_job_permission(
        session,
        user,
        "jobs.attachments.delete",
        resource=_job_resource(session, user.tenant_id, existing),
    )
    try:
        attachment = JobAttachmentService(session).archive(
            user.tenant_id, job_id, attachment_id, actor=_actor(user)
        )
        return {"attachment": attachment}
    except Exception as exc:
        raise _http(exc) from exc

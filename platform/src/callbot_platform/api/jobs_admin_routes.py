"""Admin APIs for async job DLQ inspection and replay."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from callbot_platform.api.deps import CurrentUser, db_dep, require_entitled_permission
from callbot_platform.async_jobs.service import AsyncJobError, AsyncJobService

router = APIRouter(prefix="/api/admin/jobs", tags=["async-jobs"])

_require_admin = require_entitled_permission("automations.manage")


class RetryBatchBody(BaseModel):
    job_ids: list[UUID] = Field(min_length=1, max_length=100)


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, AsyncJobError):
        status = 404 if exc.code == "not_found" else 400
        return HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        )
    return HTTPException(
        status_code=500, detail={"code": "internal", "message": str(exc)}
    )


@router.get("/dead-letter")
def list_dead_letter(
    user: CurrentUser = Depends(_require_admin),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    job_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    items = AsyncJobService(session).list_dead_letter(
        tenant_id=user.tenant_id,
        job_type=job_type,
        limit=min(limit, 100),
        offset=max(offset, 0),
    )
    return {"items": items, "count": len(items)}


@router.get("/{job_id}")
def get_job(
    job_id: UUID,
    user: CurrentUser = Depends(_require_admin),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    row = AsyncJobService(session).get(job_id, tenant_id=user.tenant_id)
    if row is None:
        raise HTTPException(
            status_code=404, detail={"code": "not_found", "message": "Job not found"}
        )
    return {"job": AsyncJobService(session).serialize(row)}


@router.post("/{job_id}/retry")
def retry_job(
    job_id: UUID,
    user: CurrentUser = Depends(_require_admin),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {"job": AsyncJobService(session).retry(job_id, tenant_id=user.tenant_id)}
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/retry-batch")
def retry_batch(
    body: RetryBatchBody,
    user: CurrentUser = Depends(_require_admin),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        items = AsyncJobService(session).retry_batch(
            body.job_ids, tenant_id=user.tenant_id
        )
        return {"items": items, "count": len(items)}
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/{job_id}/cancel")
def cancel_job(
    job_id: UUID,
    user: CurrentUser = Depends(_require_admin),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "job": AsyncJobService(session).cancel(job_id, tenant_id=user.tenant_id)
        }
    except Exception as exc:
        raise _http(exc) from exc

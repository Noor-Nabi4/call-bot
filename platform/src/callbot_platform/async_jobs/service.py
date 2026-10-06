"""Enqueue, inspect, replay, and cancel durable async jobs."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.async_jobs.types import JobStatus
from callbot_platform.config import Settings, get_settings
from callbot_platform.db.models.async_job import AsyncJob

logger = logging.getLogger(__name__)


class AsyncJobError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class AsyncJobService:
    def __init__(self, session: Session, *, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()

    def enqueue(
        self,
        *,
        tenant_id: UUID,
        job_type: str,
        idempotency_key: str,
        resource_id: str | None = None,
        payload: dict[str, Any] | None = None,
        max_attempts: int | None = None,
    ) -> AsyncJob:
        key = idempotency_key.strip()
        if not key:
            raise AsyncJobError("idempotency_required", "idempotency_key is required")

        existing = self._session.scalar(
            select(AsyncJob).where(
                AsyncJob.tenant_id == tenant_id,
                AsyncJob.idempotency_key == key,
            )
        )
        if existing is not None:
            return existing

        row = AsyncJob(
            tenant_id=tenant_id,
            job_type=job_type,
            resource_id=resource_id,
            idempotency_key=key,
            status=JobStatus.PENDING,
            max_attempts=int(
                max_attempts
                if max_attempts is not None
                else self._settings.job_max_attempts
            ),
            payload=dict(payload or {}),
            result={},
        )
        self._session.add(row)
        self._session.flush()
        logger.info(
            "async_job_enqueued",
            extra={
                "job_id": str(row.id),
                "tenant_id": str(tenant_id),
                "job_type": job_type,
                "resource_id": resource_id,
            },
        )
        return row

    def get(self, job_id: UUID, *, tenant_id: UUID | None = None) -> AsyncJob | None:
        row = self._session.get(AsyncJob, job_id)
        if row is None:
            return None
        if tenant_id is not None and row.tenant_id != tenant_id:
            return None
        return row

    def serialize(self, row: AsyncJob) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "tenant_id": str(row.tenant_id),
            "job_type": row.job_type,
            "resource_id": row.resource_id,
            "idempotency_key": row.idempotency_key,
            "status": row.status,
            "attempt_count": row.attempt_count,
            "max_attempts": row.max_attempts,
            "next_attempt_at": row.next_attempt_at.isoformat()
            if row.next_attempt_at
            else None,
            "claimed_by": row.claimed_by,
            "lease_expires_at": row.lease_expires_at.isoformat()
            if row.lease_expires_at
            else None,
            "last_error": row.last_error,
            "first_failed_at": row.first_failed_at.isoformat()
            if row.first_failed_at
            else None,
            "last_failed_at": row.last_failed_at.isoformat()
            if row.last_failed_at
            else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "payload": dict(row.payload or {}),
            "result": dict(row.result or {}),
        }

    def list_dead_letter(
        self,
        *,
        tenant_id: UUID | None = None,
        job_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        q = select(AsyncJob).where(AsyncJob.status == JobStatus.DEAD_LETTER)
        if tenant_id is not None:
            q = q.where(AsyncJob.tenant_id == tenant_id)
        if job_type:
            q = q.where(AsyncJob.job_type == job_type)
        q = q.order_by(AsyncJob.updated_at.desc()).offset(offset).limit(limit)
        return [self.serialize(r) for r in self._session.scalars(q).all()]

    def retry(self, job_id: UUID, *, tenant_id: UUID | None = None) -> dict[str, Any]:
        row = self.get(job_id, tenant_id=tenant_id)
        if row is None:
            raise AsyncJobError("not_found", "Job not found")
        if row.status not in {
            JobStatus.DEAD_LETTER,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        }:
            raise AsyncJobError(
                "not_retryable",
                f"Job status {row.status} cannot be replayed",
            )
        now = datetime.now(UTC)
        row.status = JobStatus.PENDING
        row.next_attempt_at = now
        row.claimed_at = None
        row.claimed_by = None
        row.lease_expires_at = None
        row.last_error = None
        row.updated_at = now
        # Preserve attempt_count for audit; allow another full cycle via max_attempts bump.
        row.max_attempts = max(
            int(row.max_attempts),
            int(row.attempt_count) + int(self._settings.job_max_attempts),
        )
        self._session.flush()
        logger.info(
            "async_job_replayed",
            extra={"job_id": str(row.id), "tenant_id": str(row.tenant_id)},
        )
        return self.serialize(row)

    def retry_batch(
        self,
        job_ids: list[UUID],
        *,
        tenant_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for jid in job_ids:
            out.append(self.retry(jid, tenant_id=tenant_id))
        return out

    def cancel(self, job_id: UUID, *, tenant_id: UUID | None = None) -> dict[str, Any]:
        row = self.get(job_id, tenant_id=tenant_id)
        if row is None:
            raise AsyncJobError("not_found", "Job not found")
        if row.status == JobStatus.SUCCEEDED:
            raise AsyncJobError("already_succeeded", "Cannot cancel succeeded job")
        now = datetime.now(UTC)
        row.status = JobStatus.CANCELLED
        row.claimed_at = None
        row.claimed_by = None
        row.lease_expires_at = None
        row.updated_at = now
        self._session.flush()
        return self.serialize(row)

    def queue_depth(self) -> int:
        from sqlalchemy import func

        return int(
            self._session.scalar(
                select(func.count())
                .select_from(AsyncJob)
                .where(
                    AsyncJob.status.in_(
                        [JobStatus.PENDING, JobStatus.RETRY_WAIT, JobStatus.RUNNING]
                    )
                )
            )
            or 0
        )

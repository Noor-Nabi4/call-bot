"""Generic async job worker with lease reclaim and handler dispatch."""

from __future__ import annotations

import logging
import os
import socket
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select, text, update
from sqlalchemy.orm import Session

from callbot_platform.async_jobs.types import JobStatus
from callbot_platform.config import Settings, get_settings
from callbot_platform.db.models.async_job import AsyncJob
from callbot_platform.observability.metrics import JobMetrics
from callbot_platform.tenancy import (
    TenantContext,
    TenantSource,
    clear_tenant_context,
    set_tenant_context,
)
from callbot_platform.workers.outbox import compute_backoff_seconds

logger = logging.getLogger(__name__)

JobHandler = Callable[[Session, AsyncJob], dict[str, Any] | None]


class AsyncJobWorker:
    """
    Claim → commit lease → run handler (own sessions for I/O) → succeed/retry/DLQ.

    Handlers must not assume the claim session stays open during provider HTTP.
    They receive a fresh session for DB reads/writes around I/O.
    """

    def __init__(
        self,
        session_factory: Any,
        *,
        settings: Settings | None = None,
        handlers: dict[str, JobHandler] | None = None,
        worker_id: str | None = None,
        metrics: JobMetrics | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings or get_settings()
        self._handlers = handlers or {}
        self._worker_id = (
            worker_id or f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
        )
        self._metrics = metrics or JobMetrics()
        self._stop = False

    def register(self, job_type: str, handler: JobHandler) -> None:
        self._handlers[job_type] = handler

    def request_stop(self) -> None:
        self._stop = True

    def run_forever(self) -> None:
        interval = float(self._settings.job_poll_interval_seconds)
        while not self._stop:
            processed = self.process_batch()
            if processed == 0:
                time.sleep(interval)

    def process_batch(self) -> int:
        self._reclaim_expired_leases()
        claimed = self._claim_batch()
        if not claimed:
            return 0
        for job_id, tenant_id in claimed:
            if self._stop:
                break
            self._process_one(job_id, tenant_id)
        return len(claimed)

    def process_job(self, job_id: UUID) -> None:
        """Process a single job by id (tests / inline post-commit)."""
        session: Session = self._session_factory()
        tenant_id: UUID | None = None
        try:
            row = session.get(AsyncJob, job_id)
            if row is None:
                return
            tenant_id = row.tenant_id
            if row.status == JobStatus.SUCCEEDED:
                return
            now = datetime.now(UTC)
            lease = now + timedelta(seconds=float(self._settings.job_lease_seconds))
            row.status = JobStatus.RUNNING
            row.claimed_at = now
            row.claimed_by = self._worker_id
            row.lease_expires_at = lease
            row.updated_at = now
            session.commit()
        finally:
            session.close()
        if tenant_id is None:
            return
        self._process_one(job_id, tenant_id)

    def _reclaim_expired_leases(self) -> int:
        now = datetime.now(UTC)
        session: Session = self._session_factory()
        try:
            result = session.execute(
                update(AsyncJob)
                .where(
                    AsyncJob.status == JobStatus.RUNNING,
                    AsyncJob.lease_expires_at.is_not(None),
                    AsyncJob.lease_expires_at < now,
                )
                .values(
                    status=JobStatus.PENDING,
                    claimed_at=None,
                    claimed_by=None,
                    lease_expires_at=None,
                    updated_at=now,
                    last_error="lease_expired_reclaimed",
                )
            )
            session.commit()
            count = int(result.rowcount or 0)
            if count:
                self._metrics.inc("jobs_lease_reclaimed_total", count)
                logger.warning(
                    "async_jobs_lease_reclaimed",
                    extra={"count": count, "worker_id": self._worker_id},
                )
            return count
        except Exception:
            session.rollback()
            logger.exception("async_jobs_lease_reclaim_failed")
            return 0
        finally:
            session.close()

    def _claim_batch(self) -> list[tuple[UUID, UUID]]:
        batch_size = int(self._settings.job_batch_size)
        now = datetime.now(UTC)
        lease = now + timedelta(seconds=float(self._settings.job_lease_seconds))
        session: Session = self._session_factory()
        try:
            dialect = session.bind.dialect.name if session.bind is not None else ""
            if dialect == "postgresql":
                result = session.execute(
                    text(
                        """
                        SELECT id, tenant_id
                        FROM async_jobs
                        WHERE status IN ('pending', 'retry_wait')
                          AND (next_attempt_at IS NULL OR next_attempt_at <= :now)
                        ORDER BY created_at ASC
                        FOR UPDATE SKIP LOCKED
                        LIMIT :limit
                        """
                    ),
                    {"now": now, "limit": batch_size},
                )
                rows = [(UUID(str(r[0])), UUID(str(r[1]))) for r in result.fetchall()]
            else:
                q = (
                    select(AsyncJob)
                    .where(
                        AsyncJob.status.in_([JobStatus.PENDING, JobStatus.RETRY_WAIT]),
                        or_(
                            AsyncJob.next_attempt_at.is_(None),
                            AsyncJob.next_attempt_at <= now,
                        ),
                    )
                    .order_by(AsyncJob.created_at.asc())
                    .limit(batch_size)
                    .with_for_update()
                )
                objs = list(session.scalars(q).all())
                rows = [(o.id, o.tenant_id) for o in objs]

            if not rows:
                session.commit()
                return []

            ids = [r[0] for r in rows]
            session.execute(
                update(AsyncJob)
                .where(
                    AsyncJob.id.in_(ids),
                    AsyncJob.status.in_([JobStatus.PENDING, JobStatus.RETRY_WAIT]),
                )
                .values(
                    status=JobStatus.RUNNING,
                    claimed_at=now,
                    claimed_by=self._worker_id,
                    lease_expires_at=lease,
                    updated_at=now,
                )
            )
            session.commit()
            self._metrics.inc("jobs_claimed_total", len(rows))
            return rows
        except Exception:
            session.rollback()
            logger.exception("async_jobs_claim_failed")
            raise
        finally:
            session.close()

    def _process_one(self, job_id: UUID, tenant_id: UUID) -> None:
        started = time.perf_counter()
        token = set_tenant_context(
            TenantContext(tenant_id=tenant_id, source=TenantSource.JOB)
        )
        job_type = "unknown"
        try:
            snap = self._load_running(job_id, tenant_id)
            if snap is None:
                return
            job_type, _payload, resource_id = snap
            handler = self._handlers.get(job_type)
            if handler is None:
                self._mark_failure(
                    job_id, tenant_id, f"no_handler:{job_type}", permanent=True
                )
                return
            try:
                session: Session = self._session_factory()
                try:
                    job = session.get(AsyncJob, job_id)
                    if job is None or job.tenant_id != tenant_id:
                        session.commit()
                        return
                    result = handler(session, job) or {}
                    session.commit()
                except Exception:
                    session.rollback()
                    raise
                finally:
                    session.close()
                self._mark_success(job_id, tenant_id, result)
                self._metrics.inc("jobs_processed_total")
                self._metrics.inc(f"jobs_succeeded_{job_type}")
            except Exception as exc:
                logger.exception(
                    "async_job_failed",
                    extra={
                        "job_id": str(job_id),
                        "tenant_id": str(tenant_id),
                        "job_type": job_type,
                        "resource_id": resource_id,
                    },
                )
                self._mark_failure(job_id, tenant_id, str(exc)[:500])
                self._metrics.inc("jobs_failed_total")
        finally:
            clear_tenant_context(token)
            self._metrics.observe_latency_ms(
                (time.perf_counter() - started) * 1000, job_type=job_type
            )

    def _load_running(
        self, job_id: UUID, tenant_id: UUID
    ) -> tuple[str, dict[str, Any], str | None] | None:
        session: Session = self._session_factory()
        try:
            row = session.get(AsyncJob, job_id)
            if row is None or row.status != JobStatus.RUNNING:
                session.commit()
                return None
            if row.tenant_id != tenant_id:
                row.status = JobStatus.DEAD_LETTER
                row.last_error = "tenant_mismatch"
                row.updated_at = datetime.now(UTC)
                session.commit()
                self._metrics.inc("jobs_dead_lettered_total")
                return None
            data = (row.job_type, dict(row.payload or {}), row.resource_id)
            session.commit()
            return data
        finally:
            session.close()

    def _mark_success(
        self, job_id: UUID, tenant_id: UUID, result: dict[str, Any]
    ) -> None:
        session: Session = self._session_factory()
        try:
            row = session.get(AsyncJob, job_id)
            if row is None or row.tenant_id != tenant_id:
                session.commit()
                return
            now = datetime.now(UTC)
            row.status = JobStatus.SUCCEEDED
            row.result = dict(result)
            row.last_error = None
            row.claimed_at = None
            row.claimed_by = None
            row.lease_expires_at = None
            row.completed_at = now
            row.updated_at = now
            session.commit()
        finally:
            session.close()

    def _mark_failure(
        self,
        job_id: UUID,
        tenant_id: UUID,
        error: str,
        *,
        permanent: bool = False,
    ) -> None:
        settings = self._settings
        base = float(settings.job_base_backoff_seconds)
        cap = float(settings.job_max_backoff_seconds)
        now = datetime.now(UTC)
        session: Session = self._session_factory()
        try:
            row = session.get(AsyncJob, job_id)
            if row is None or row.tenant_id != tenant_id:
                session.commit()
                return
            row.attempt_count = int(row.attempt_count or 0) + 1
            row.last_error = error
            row.last_failed_at = now
            if row.first_failed_at is None:
                row.first_failed_at = now
            row.updated_at = now
            row.claimed_at = None
            row.claimed_by = None
            row.lease_expires_at = None
            max_attempts = int(row.max_attempts or settings.job_max_attempts)
            if permanent or row.attempt_count >= max_attempts:
                row.status = JobStatus.DEAD_LETTER
                row.next_attempt_at = None
                self._metrics.inc("jobs_dead_lettered_total")
            else:
                delay = compute_backoff_seconds(row.attempt_count, base=base, cap=cap)
                row.status = JobStatus.RETRY_WAIT
                row.next_attempt_at = now + timedelta(seconds=delay)
                self._metrics.inc("jobs_retried_total")
            session.commit()
        finally:
            session.close()

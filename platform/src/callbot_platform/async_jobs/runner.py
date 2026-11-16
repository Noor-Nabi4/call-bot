"""Run a queued async job after the request transaction commits."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from callbot_platform.async_jobs.handlers import attach_default_handlers
from callbot_platform.async_jobs.handlers.telephony import TelephonyProvisionHandler
from callbot_platform.async_jobs.worker import AsyncJobWorker
from callbot_platform.config import Settings, get_settings
from callbot_platform.db.models import TenantPhoneNumber
from callbot_platform.db.models.async_job import AsyncJob
from callbot_platform.telephony.services.purchase import PlatformPurchaseService


def run_async_job(
    session_factory: sessionmaker[Session],
    job_id: UUID,
    *,
    settings: Settings | None = None,
    telephony_handler: TelephonyProvisionHandler | None = None,
) -> AsyncJob | None:
    """Process one job using a dedicated worker (provider I/O outside request TX)."""
    cfg = settings or get_settings()
    worker = AsyncJobWorker(session_factory, settings=cfg)
    attach_default_handlers(worker, settings=cfg, telephony=telephony_handler)
    worker.process_job(job_id)
    session = session_factory()
    try:
        return session.get(AsyncJob, job_id)
    finally:
        session.close()


def complete_purchase_after_commit(
    session_factory: sessionmaker[Session],
    *,
    tenant_id: UUID,
    job_id: UUID,
    idempotency_key: str,
    settings: Settings,
    purchase_deps: dict[str, Any],
) -> dict[str, Any]:
    """
    Run purchase provisioning job and refresh idempotency response.

    Used by API routes and tests after enqueue + commit.
    """
    handler = TelephonyProvisionHandler(
        settings=settings,
        cipher=purchase_deps.get("cipher"),
        signer=purchase_deps.get("signer"),
        provisioning=purchase_deps.get("provisioning"),
        twilio_sip=purchase_deps.get("twilio_sip"),
        livekit=purchase_deps.get("livekit"),
    )
    job = run_async_job(
        session_factory, job_id, settings=settings, telephony_handler=handler
    )
    session = session_factory()
    try:
        svc = PlatformPurchaseService(
            session,
            settings,
            cipher=purchase_deps["cipher"],
            signer=purchase_deps["signer"],
            inventory=purchase_deps["inventory"],
            provisioning=purchase_deps["provisioning"],
            twilio_sip=purchase_deps["twilio_sip"],
            livekit=purchase_deps["livekit"],
        )
        if job is None:
            raise RuntimeError("job_missing_after_process")
        phone_id = UUID(str((job.payload or {}).get("phone_number_id")))
        phone = session.get(TenantPhoneNumber, phone_id)
        if phone is None:
            raise RuntimeError("phone_missing_after_process")
        serialized = svc._serialize(phone)
        response = {
            "phone_number": serialized,
            "job_id": str(job_id),
            "provisioning": job.status,
        }
        if job.status == "succeeded":
            svc.mark_idempotency_completed(
                tenant_id=tenant_id,
                idempotency_key=idempotency_key,
                response=response,
            )
        else:
            response = {
                "error": "partial_provisioning",
                "message": job.last_error or "provisioning failed",
                "phone_number": serialized,
                "job_id": str(job_id),
                "job_status": job.status,
            }
            svc.mark_idempotency_failed(
                tenant_id=tenant_id,
                idempotency_key=idempotency_key,
                response=response,
            )
        session.commit()
        return response
    finally:
        session.close()

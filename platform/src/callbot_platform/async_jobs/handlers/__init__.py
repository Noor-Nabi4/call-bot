"""Handler registry for async job worker."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from callbot_platform.async_jobs.handlers.call_intelligence import (
    CallIntelligenceJobHandler,
)
from callbot_platform.async_jobs.handlers.knowledge import KnowledgeIngestHandler
from callbot_platform.async_jobs.handlers.stripe_billing import StripeProvisionHandler
from callbot_platform.async_jobs.handlers.telephony import TelephonyProvisionHandler
from callbot_platform.async_jobs.types import JobType
from callbot_platform.async_jobs.worker import AsyncJobWorker, JobHandler
from callbot_platform.config import Settings
from callbot_platform.db.models.async_job import AsyncJob


def build_default_handlers(
    *,
    settings: Settings,
    telephony: TelephonyProvisionHandler | None = None,
    stripe_handler: StripeProvisionHandler | None = None,
) -> dict[str, JobHandler]:
    tel = telephony or TelephonyProvisionHandler(settings=settings)
    stripe_h = stripe_handler or StripeProvisionHandler(settings=settings)
    knowledge_h = KnowledgeIngestHandler(settings=settings)
    call_intel_h = CallIntelligenceJobHandler(settings=settings)

    def _purchase(session: Session, job: AsyncJob) -> dict:
        try:
            return tel.handle_purchase(session, job)
        except Exception as exc:
            tel.mark_purchase_partial(
                session,
                phone_id=UUID(str(job.payload["phone_number_id"])),
                tenant_id=job.tenant_id,
                error=str(exc)[:500],
            )
            session.flush()
            raise

    def _connect(session: Session, job: AsyncJob) -> dict:
        return tel.handle_connect(session, job)

    def _release(session: Session, job: AsyncJob) -> dict:
        return tel.handle_release(session, job)

    def _refresh(session: Session, job: AsyncJob) -> dict:
        return tel.handle_refresh_dispatch(session, job)

    def _signup(session: Session, job: AsyncJob) -> dict:
        return stripe_h.handle_signup(session, job)

    def _checkout(session: Session, job: AsyncJob) -> dict:
        return stripe_h.handle_checkout(session, job)

    def _knowledge_ingest(session: Session, job: AsyncJob) -> dict:
        return knowledge_h.handle(session, job)

    def _call_transcribe(session: Session, job: AsyncJob) -> dict:
        return call_intel_h.handle_transcribe(session, job)

    def _call_analyze(session: Session, job: AsyncJob) -> dict:
        return call_intel_h.handle_analyze(session, job)

    def _call_retention(session: Session, job: AsyncJob) -> dict:
        return call_intel_h.handle_retention(session, job)

    return {
        JobType.TELEPHONY_PROVISION_PURCHASE: _purchase,
        JobType.TELEPHONY_PROVISION_CONNECT: _connect,
        JobType.TELEPHONY_RELEASE: _release,
        JobType.TELEPHONY_REFRESH_DISPATCH: _refresh,
        JobType.STRIPE_SIGNUP_PROVISION: _signup,
        JobType.STRIPE_CHECKOUT_PROVISION: _checkout,
        JobType.KNOWLEDGE_INGEST: _knowledge_ingest,
        JobType.CALL_TRANSCRIBE: _call_transcribe,
        JobType.CALL_ANALYZE: _call_analyze,
        JobType.CALL_INTELLIGENCE_RETENTION: _call_retention,
    }


def attach_default_handlers(
    worker: AsyncJobWorker,
    *,
    settings: Settings,
    telephony: TelephonyProvisionHandler | None = None,
    stripe_handler: StripeProvisionHandler | None = None,
) -> AsyncJobWorker:
    for job_type, handler in build_default_handlers(
        settings=settings,
        telephony=telephony,
        stripe_handler=stripe_handler,
    ).items():
        worker.register(job_type, handler)
    return worker

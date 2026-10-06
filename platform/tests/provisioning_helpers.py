"""Helpers to drain telephony provisioning jobs in tests."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from callbot_platform.async_jobs.handlers.telephony import TelephonyProvisionHandler
from callbot_platform.async_jobs.runner import (
    complete_purchase_after_commit,
    run_async_job,
)
from callbot_platform.config import Settings
from callbot_platform.db.models import TenantPhoneNumber
from callbot_platform.telephony.services.connect_existing import ConnectExistingService
from callbot_platform.telephony.services.purchase import (
    PlatformPurchaseService,
    PurchaseError,
)


def session_factory_for(session: Session) -> sessionmaker[Session]:
    """Bind a sessionmaker to the same engine/connection as the test session."""
    bind = session.get_bind()
    return sessionmaker(bind=bind, autoflush=False, autocommit=False, future=True)


def purchase_and_provision(
    session: Session,
    service: PlatformPurchaseService,
    settings: Settings,
    *,
    tenant_id: UUID,
    phone_number: str,
    confirm: bool,
    idempotency_key: str,
    deps: dict[str, Any],
) -> dict[str, Any]:
    result = service.purchase(
        tenant_id=tenant_id,
        phone_number=phone_number,
        confirm=confirm,
        idempotency_key=idempotency_key,
    )
    session.commit()
    job_id = result.get("job_id")
    if not job_id:
        return result
    completed = complete_purchase_after_commit(
        session_factory_for(session),
        tenant_id=tenant_id,
        job_id=UUID(str(job_id)),
        idempotency_key=idempotency_key,
        settings=settings,
        purchase_deps=deps,
    )
    if completed.get("error") == "partial_provisioning":
        raise PurchaseError(
            "partial_provisioning",
            str(completed.get("message") or "partial"),
        )
    # Refresh test session view.
    session.expire_all()
    return completed


def connect_and_provision(
    session: Session,
    service: ConnectExistingService,
    settings: Settings,
    *,
    tenant_id: UUID,
    phone_number: str,
    livekit: Any,
    signer: Any,
) -> dict[str, Any]:
    result = service.start(tenant_id=tenant_id, phone_number=phone_number)
    session.commit()
    job_id = result.get("job_id")
    if job_id:
        handler = TelephonyProvisionHandler(
            settings=settings, signer=signer, livekit=livekit
        )
        run_async_job(
            session_factory_for(session),
            UUID(str(job_id)),
            settings=settings,
            telephony_handler=handler,
        )
        session.expire_all()
        phone = session.get(TenantPhoneNumber, UUID(result["phone_number"]["id"]))
        if phone is not None:
            result["phone_number"] = service._serialize(phone)
    return result

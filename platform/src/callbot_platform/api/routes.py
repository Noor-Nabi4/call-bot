"""HTTP API routes for telephony onboarding and internal resolve."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.api.deps import (
    connect_service,
    db_dep,
    purchase_service,
    require_internal_token,
    resolver_service,
    settings_dep,
    signer_dep,
    verification_service,
)
from callbot_platform.config import Settings, get_settings
from callbot_platform.db import get_session_factory
from callbot_platform.db.models import Tenant, TenantPhoneNumber
from callbot_platform.organization import OrganizationError, OrganizationService
from callbot_platform.security.call_scope import CallScopeSigner
from callbot_platform.security.metadata import MetadataSigner
from callbot_platform.telephony.interfaces import ResolveRequest
from callbot_platform.telephony.services.connect_existing import (
    ConnectExistingError,
    ConnectExistingService,
)
from callbot_platform.telephony.services.purchase import (
    PlatformPurchaseService,
    PurchaseError,
)
from callbot_platform.telephony.services.resolver import (
    DbTenantDidResolver,
    TenantResolveError,
)
from callbot_platform.telephony.services.verification import (
    DbNumberVerificationService,
    VerificationError,
)

router = APIRouter()


def _issue_tenant_scope(tenant_id: UUID) -> str | None:
    settings = get_settings()
    if not settings.metadata_hmac_secret:
        return None
    return CallScopeSigner(settings.metadata_hmac_secret).issue(
        tenant_id=tenant_id,
        ttl_seconds=settings.call_scope_ttl_seconds,
    )


class CreateTenantBody(BaseModel):
    model_config = {"extra": "forbid"}

    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=2, max_length=128)
    timezone: str = "UTC"
    industry: str | None = Field(default=None, max_length=64)
    business_type: str | None = Field(default=None, max_length=64)
    currency: str | None = Field(default=None, max_length=3)
    country: str | None = Field(default=None, max_length=2)
    state: str | None = Field(default=None, max_length=128)
    website: str | None = Field(default=None, max_length=2048)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=255)


class ConnectNumberBody(BaseModel):
    phone_number: str
    twilio_account_sid: str | None = None


class ConfirmTrunkBody(BaseModel):
    twilio_trunk_sid: str | None = None


class PurchaseBody(BaseModel):
    phone_number: str
    confirm: bool = False


class ReleaseBody(BaseModel):
    phone_number_sid: str


class ResolveBody(BaseModel):
    job_metadata: str | None = None
    called_number: str | None = None
    livekit_inbound_trunk_id: str | None = None
    is_sip: bool = False


class InboundObservedBody(BaseModel):
    called_number: str
    caller_number: str | None = None
    livekit_inbound_trunk_id: str | None = None
    livekit_room_name: str | None = None
    provider_call_id: str | None = None


class SignMetadataBody(BaseModel):
    tenant_id: str
    did: str | None = None
    source: str = "playground"
    extra: dict[str, Any] = Field(default_factory=dict)


@router.get("/health")
def health() -> dict[str, str]:
    """Legacy alias for liveness."""
    return {"status": "ok"}


@router.get("/liveness")
def liveness() -> dict[str, str]:
    """Process is alive — does not check Postgres."""
    return {"status": "alive"}


@router.get("/readiness")
def readiness(
    session: Session = Depends(db_dep),
    settings: Settings = Depends(settings_dep),
) -> dict[str, Any]:
    """Ready to serve traffic if required dependencies respond quickly."""
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    checks: dict[str, str] = {}
    try:
        session.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "not_ready",
                "message": "postgres unavailable",
                "checks": {"postgres": "fail"},
                "error": str(exc)[:200],
            },
        ) from exc

    backend = (settings.object_storage_backend or "filesystem").strip().lower()
    checks["object_storage"] = backend
    return {"status": "ready", "checks": checks}


@router.post("/tenants", dependencies=[Depends(require_internal_token)])
def create_tenant(body: CreateTenantBody, session: Session = Depends(db_dep)) -> dict:
    try:
        organization = OrganizationService(session).create(
            name=body.name,
            slug=body.slug,
            timezone=body.timezone or "UTC",
            actor="internal",
            industry=body.industry,
            business_type=body.business_type,
            currency=body.currency,
            country=body.country,
            state=body.state,
            website=body.website,
            phone=body.phone,
            email=body.email,
        )
    except OrganizationError as exc:
        status = 409 if exc.code == "slug_taken" else 400
        raise HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        ) from exc
    from callbot_platform.crm.repos import AgentProfileRepository

    tenant_id = UUID(organization["id"])
    AgentProfileRepository(session).create(
        tenant_id,
        name="Main Receptionist",
        agent_type="receptionist",
        is_default=True,
        actor="system",
    )
    return OrganizationService(session).get(tenant_id)


@router.get("/tenants/{tenant_id}", dependencies=[Depends(require_internal_token)])
def get_tenant(tenant_id: UUID, session: Session = Depends(db_dep)) -> dict:
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return {
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "status": tenant.status,
    }


@router.get(
    "/tenants/{tenant_id}/phone-numbers",
    dependencies=[Depends(require_internal_token)],
)
def list_phone_numbers(tenant_id: UUID, session: Session = Depends(db_dep)) -> dict:
    rows = list(
        session.scalars(
            select(TenantPhoneNumber).where(TenantPhoneNumber.tenant_id == tenant_id)
        )
    )
    return {
        "items": [
            {
                "id": str(r.id),
                "e164": r.e164,
                "connection_status": r.connection_status,
                "verification_status": r.verification_status,
                "onboarding_path": r.onboarding_path,
                "provisioning_state": r.provisioning_state,
                "livekit_inbound_trunk_id": r.livekit_inbound_trunk_id,
                "livekit_dispatch_rule_id": r.livekit_dispatch_rule_id,
                "agent_profile_id": str(r.agent_profile_id)
                if r.agent_profile_id
                else None,
            }
            for r in rows
        ]
    }


@router.post(
    "/tenants/{tenant_id}/phone-numbers/connect",
    dependencies=[Depends(require_internal_token)],
)
def connect_existing_number(
    tenant_id: UUID,
    body: ConnectNumberBody,
    session: Session = Depends(db_dep),
    settings: Settings = Depends(settings_dep),
    service: ConnectExistingService = Depends(connect_service),
) -> dict:
    try:
        result = service.start(
            tenant_id=tenant_id,
            phone_number=body.phone_number,
            twilio_account_sid=body.twilio_account_sid,
        )
        job_id = result.get("job_id")
        session.commit()
        if job_id:
            from callbot_platform.async_jobs.handlers.telephony import (
                TelephonyProvisionHandler,
            )
            from callbot_platform.async_jobs.runner import run_async_job

            handler = TelephonyProvisionHandler(
                settings=settings,
                signer=service._signer,
                livekit=service._livekit,
            )
            job = run_async_job(
                get_session_factory(),
                UUID(str(job_id)),
                settings=settings,
                telephony_handler=handler,
            )
            phone = session.scalar(
                select(TenantPhoneNumber).where(
                    TenantPhoneNumber.id == UUID(result["phone_number"]["id"]),
                    TenantPhoneNumber.tenant_id == tenant_id,
                )
            )
            if phone is not None:
                session.refresh(phone)
                result["phone_number"] = service._serialize(phone)
            result["provisioning"] = job.status if job else "unknown"
        return result
    except ConnectExistingError as exc:
        status = 409 if exc.code == "duplicate_number" else 400
        if exc.code == "partial_provisioning":
            status = 502
        raise HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        ) from exc


@router.post(
    "/tenants/{tenant_id}/phone-numbers/{phone_number_id}/confirm-trunk",
    dependencies=[Depends(require_internal_token)],
)
def confirm_trunk(
    tenant_id: UUID,
    phone_number_id: UUID,
    body: ConfirmTrunkBody,
    service: ConnectExistingService = Depends(connect_service),
) -> dict:
    try:
        return service.confirm_trunk(
            tenant_id=tenant_id,
            phone_number_id=phone_number_id,
            twilio_trunk_sid=body.twilio_trunk_sid,
        )
    except ConnectExistingError as exc:
        raise HTTPException(
            status_code=404 if exc.code == "not_found" else 400,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc


@router.post(
    "/tenants/{tenant_id}/phone-numbers/{phone_number_id}/verification/start",
    dependencies=[Depends(require_internal_token)],
)
def start_verification(
    tenant_id: UUID,
    phone_number_id: UUID,
    service: DbNumberVerificationService = Depends(verification_service),
) -> dict:
    try:
        return service.start_verification(
            tenant_id=tenant_id, phone_number_id=phone_number_id
        )
    except VerificationError as exc:
        raise HTTPException(
            status_code=400, detail={"code": exc.code, "message": str(exc)}
        ) from exc


@router.post(
    "/tenants/{tenant_id}/twilio/subaccount",
    dependencies=[Depends(require_internal_token)],
)
def ensure_subaccount(
    tenant_id: UUID,
    service: PlatformPurchaseService = Depends(purchase_service),
) -> dict:
    try:
        return service.ensure_subaccount(tenant_id=tenant_id)
    except PurchaseError as exc:
        raise HTTPException(
            status_code=400, detail={"code": exc.code, "message": str(exc)}
        ) from exc


@router.get(
    "/tenants/{tenant_id}/inventory",
    dependencies=[Depends(require_internal_token)],
)
def search_inventory(
    tenant_id: UUID,
    country: str = "US",
    area_code: str | None = None,
    number_type: str = "local",
    limit: int = 20,
    session: Session = Depends(db_dep),
    service: PlatformPurchaseService = Depends(purchase_service),
) -> dict:
    try:
        service.ensure_subaccount(tenant_id=tenant_id)
        session.commit()
        items = service.search_inventory(
            tenant_id=tenant_id,
            country=country,
            area_code=area_code,
            number_type=number_type,
            limit=limit,
        )
        return {"items": items}
    except PurchaseError as exc:
        raise HTTPException(
            status_code=400, detail={"code": exc.code, "message": str(exc)}
        ) from exc


@router.post(
    "/tenants/{tenant_id}/phone-numbers/purchase",
    dependencies=[Depends(require_internal_token)],
)
def purchase_number(
    tenant_id: UUID,
    body: PurchaseBody,
    session: Session = Depends(db_dep),
    settings: Settings = Depends(settings_dep),
    service: PlatformPurchaseService = Depends(purchase_service),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    try:
        result = service.purchase(
            tenant_id=tenant_id,
            phone_number=body.phone_number,
            confirm=body.confirm,
            idempotency_key=idempotency_key or "",
        )
        job_id = result.get("job_id")
        key = idempotency_key or ""
        session.commit()
        if job_id and result.get("provisioning") == "queued":
            from callbot_platform.async_jobs.runner import (
                complete_purchase_after_commit,
            )

            completed = complete_purchase_after_commit(
                get_session_factory(),
                tenant_id=tenant_id,
                job_id=UUID(str(job_id)),
                idempotency_key=key,
                settings=settings,
                purchase_deps={
                    "cipher": service._cipher,
                    "signer": service._signer,
                    "inventory": service._inventory,
                    "provisioning": service._provisioning,
                    "twilio_sip": service._twilio_sip,
                    "livekit": service._livekit,
                },
            )
            if completed.get("error") == "partial_provisioning":
                raise PurchaseError(
                    "partial_provisioning",
                    str(completed.get("message") or "Purchase partially completed"),
                )
            return completed
        return result
    except PurchaseError as exc:
        status = 400
        if exc.code == "partial_provisioning":
            status = 502
        if exc.code == "duplicate_number":
            status = 409
        raise HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        ) from exc


@router.post(
    "/tenants/{tenant_id}/phone-numbers/{phone_number_id}/release",
    dependencies=[Depends(require_internal_token)],
)
def release_number(
    tenant_id: UUID,
    phone_number_id: UUID,
    body: ReleaseBody,
    session: Session = Depends(db_dep),
    settings: Settings = Depends(settings_dep),
    service: PlatformPurchaseService = Depends(purchase_service),
) -> dict:
    try:
        result = service.release(
            tenant_id=tenant_id,
            phone_number_id=phone_number_id,
            phone_number_sid=body.phone_number_sid,
        )
        job_id = result.get("job_id")
        session.commit()
        if job_id:
            from callbot_platform.async_jobs.handlers.telephony import (
                TelephonyProvisionHandler,
            )
            from callbot_platform.async_jobs.runner import run_async_job

            handler = TelephonyProvisionHandler(
                settings=settings,
                cipher=service._cipher,
                signer=service._signer,
                provisioning=service._provisioning,
                livekit=service._livekit,
            )
            job = run_async_job(
                get_session_factory(),
                UUID(str(job_id)),
                settings=settings,
                telephony_handler=handler,
            )
            phone = session.scalar(
                select(TenantPhoneNumber).where(
                    TenantPhoneNumber.id == phone_number_id,
                    TenantPhoneNumber.tenant_id == tenant_id,
                )
            )
            if phone is not None:
                session.refresh(phone)
                result = {
                    "phone_number": service._serialize(phone),
                    "job_id": str(job_id),
                    "provisioning": job.status if job else "unknown",
                }
        return result
    except PurchaseError as exc:
        raise HTTPException(
            status_code=403 if exc.code == "release_not_allowed" else 400,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc


@router.post(
    "/internal/telephony/resolve",
    dependencies=[Depends(require_internal_token)],
)
def resolve_tenant(
    body: ResolveBody,
    service: DbTenantDidResolver = Depends(resolver_service),
) -> dict:
    try:
        result = service.resolve(
            ResolveRequest(
                job_metadata_raw=body.job_metadata,
                called_number=body.called_number,
                livekit_inbound_trunk_id=body.livekit_inbound_trunk_id,
                is_sip=body.is_sip,
            )
        )
        return {
            "tenant_id": str(result.tenant_id),
            "phone_number_id": str(result.phone_number_id)
            if result.phone_number_id
            else None,
            "e164": result.e164,
            "source": result.source,
            "livekit_inbound_trunk_id": result.livekit_inbound_trunk_id,
            "livekit_dispatch_rule_id": result.livekit_dispatch_rule_id,
            "agent_profile_id": str(result.agent_profile_id)
            if result.agent_profile_id
            else None,
            "call_scope": _issue_tenant_scope(result.tenant_id),
        }
    except TenantResolveError as exc:
        raise HTTPException(
            status_code=403, detail={"code": exc.code, "message": str(exc)}
        ) from exc


@router.post(
    "/internal/telephony/inbound-observed",
    dependencies=[Depends(require_internal_token)],
)
def inbound_observed(
    body: InboundObservedBody,
    service: DbNumberVerificationService = Depends(verification_service),
) -> dict:
    try:
        return service.observe_inbound(
            called_number=body.called_number,
            caller_number=body.caller_number,
            livekit_inbound_trunk_id=body.livekit_inbound_trunk_id,
            livekit_room_name=body.livekit_room_name,
            provider_call_id=body.provider_call_id,
        )
    except VerificationError as exc:
        raise HTTPException(
            status_code=400, detail={"code": exc.code, "message": str(exc)}
        ) from exc


@router.post(
    "/internal/telephony/sign-metadata",
    dependencies=[Depends(require_internal_token)],
)
def sign_metadata(
    body: SignMetadataBody,
    signer: MetadataSigner = Depends(signer_dep),
) -> dict:
    payload = {"tenant_id": body.tenant_id, "source": body.source, **body.extra}
    if body.did:
        payload["did"] = body.did
    return {"metadata": signer.sign_payload(payload)}

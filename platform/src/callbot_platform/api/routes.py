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
    signer_dep,
    verification_service,
)
from callbot_platform.security.metadata import MetadataSigner
from callbot_platform.db.models import Tenant, TenantPhoneNumber
from callbot_platform.telephony.interfaces import ResolveRequest
from callbot_platform.telephony.services.connect_existing import (
    ConnectExistingError,
    ConnectExistingService,
)
from callbot_platform.telephony.services.purchase import PlatformPurchaseService, PurchaseError
from callbot_platform.telephony.services.resolver import DbTenantDidResolver, TenantResolveError
from callbot_platform.telephony.services.verification import (
    DbNumberVerificationService,
    VerificationError,
)

router = APIRouter()


class CreateTenantBody(BaseModel):
    name: str
    slug: str


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
    return {"status": "ok"}


@router.post("/tenants")
def create_tenant(body: CreateTenantBody, session: Session = Depends(db_dep)) -> dict:
    existing = session.scalar(select(Tenant).where(Tenant.slug == body.slug))
    if existing:
        raise HTTPException(status_code=409, detail="Tenant slug already exists")
    tenant = Tenant(name=body.name, slug=body.slug)
    session.add(tenant)
    session.flush()
    return {
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "status": tenant.status,
    }


@router.get("/tenants/{tenant_id}")
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


@router.get("/tenants/{tenant_id}/phone-numbers")
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
            }
            for r in rows
        ]
    }


@router.post("/tenants/{tenant_id}/phone-numbers/connect")
def connect_existing_number(
    tenant_id: UUID,
    body: ConnectNumberBody,
    service: ConnectExistingService = Depends(connect_service),
) -> dict:
    try:
        return service.start(
            tenant_id=tenant_id,
            phone_number=body.phone_number,
            twilio_account_sid=body.twilio_account_sid,
        )
    except ConnectExistingError as exc:
        status = 409 if exc.code == "duplicate_number" else 400
        if exc.code == "partial_provisioning":
            status = 502
        raise HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc)}) from exc


@router.post("/tenants/{tenant_id}/phone-numbers/{phone_number_id}/confirm-trunk")
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


@router.post("/tenants/{tenant_id}/phone-numbers/{phone_number_id}/verification/start")
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


@router.post("/tenants/{tenant_id}/twilio/subaccount")
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


@router.get("/tenants/{tenant_id}/inventory")
def search_inventory(
    tenant_id: UUID,
    country: str = "US",
    area_code: str | None = None,
    number_type: str = "local",
    limit: int = 20,
    service: PlatformPurchaseService = Depends(purchase_service),
) -> dict:
    try:
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


@router.post("/tenants/{tenant_id}/phone-numbers/purchase")
def purchase_number(
    tenant_id: UUID,
    body: PurchaseBody,
    service: PlatformPurchaseService = Depends(purchase_service),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    try:
        return service.purchase(
            tenant_id=tenant_id,
            phone_number=body.phone_number,
            confirm=body.confirm,
            idempotency_key=idempotency_key or "",
        )
    except PurchaseError as exc:
        status = 400
        if exc.code == "partial_provisioning":
            status = 502
        if exc.code == "duplicate_number":
            status = 409
        raise HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        ) from exc


@router.post("/tenants/{tenant_id}/phone-numbers/{phone_number_id}/release")
def release_number(
    tenant_id: UUID,
    phone_number_id: UUID,
    body: ReleaseBody,
    service: PlatformPurchaseService = Depends(purchase_service),
) -> dict:
    try:
        return service.release(
            tenant_id=tenant_id,
            phone_number_id=phone_number_id,
            phone_number_sid=body.phone_number_sid,
        )
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

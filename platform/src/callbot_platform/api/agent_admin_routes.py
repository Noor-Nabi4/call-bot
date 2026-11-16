"""Admin APIs for multi-profile agents and phone management."""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from livekit import api
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.agent_templates import (
    get_template,
    list_marketplace_catalog,
    list_templates,
)
from callbot_platform.api.deps import (
    CurrentUser,
    connect_service,
    db_dep,
    purchase_service,
    require_entitled_permission,
    require_permission,
    settings_dep,
    signer_dep,
    verification_service,
)
from callbot_platform.config import Settings
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.repos import AgentProfileRepository
from callbot_platform.security.metadata import MetadataSigner
from callbot_platform.security.rate_limit import (
    AGENT_SETTINGS_RATE_LIMITER,
    RateLimitExceeded,
)
from callbot_platform.telephony.adapters.livekit_sip import LiveKitSipService
from callbot_platform.telephony.services.connect_existing import (
    ConnectExistingError,
    ConnectExistingService,
)
from callbot_platform.telephony.services.phone_assign import (
    PhoneAssignError,
    PhoneAssignmentService,
)
from callbot_platform.telephony.services.purchase import (
    PlatformPurchaseService,
    PurchaseError,
)
from callbot_platform.telephony.services.verification import (
    DbNumberVerificationService,
    VerificationError,
)

router = APIRouter(prefix="/api/admin", tags=["admin-agents-phones"])

_require_agents_read = require_entitled_permission("ai.read")
_require_agents_manage = require_entitled_permission("agents.manage")
# Phone setup is a prerequisite for onboarding completion (and thus entitlement).
# Do not require wallet/subscription here — that creates a chicken-and-egg 402.
_require_phones = require_permission(
    "phones.manage", allow_incomplete_onboarding=True
)
_require_ai_configure = require_entitled_permission("ai.configure")


class CreateProfileBody(BaseModel):
    model_config = {"extra": "forbid"}

    name: str
    agent_type: str = "receptionist"
    industry_key: str | None = None
    is_default: bool = False
    voice: str | None = None
    language: str | None = None
    greeting: str | None = None
    assistant_name: str | None = None
    business_description: str | None = None
    tone: str | None = None
    supported_languages: list[str] | None = None
    response_style: str | None = None
    service_areas: list[str] | None = None
    business_hours_summary: str | None = None
    business_hours: dict[str, Any] | None = None
    booking_rules: str | None = None
    pricing_disclosure_policy: str | None = None
    handoff_rules_text: str | None = None
    restricted_topics: list[str] | None = None
    custom_instructions: str | None = None
    enabled_tools: dict[str, bool] | None = None


class UpdateProfileBody(BaseModel):
    model_config = {"extra": "forbid"}

    name: str | None = None
    agent_type: str | None = None
    status: str | None = None
    industry_key: str | None = None
    voice: str | None = None
    language: str | None = None
    greeting: str | None = None
    assistant_name: str | None = None
    business_description: str | None = None
    tone: str | None = None
    supported_languages: list[str] | None = None
    response_style: str | None = None
    service_areas: list[str] | None = None
    business_hours_summary: str | None = None
    business_hours: dict[str, Any] | None = None
    booking_rules: str | None = None
    pricing_disclosure_policy: str | None = None
    handoff_rules_text: str | None = None
    restricted_topics: list[str] | None = None
    custom_instructions: str | None = None
    enabled_tools: dict[str, bool] | None = None
    call_flow: dict[str, Any] | None = None


class ApplyTemplateBody(BaseModel):
    industry_key: str
    seed_knowledge: bool = True


class MarketplaceInstallBody(BaseModel):
    model_config = {"extra": "forbid"}

    industry_key: str = Field(min_length=1, max_length=64)
    name: str | None = Field(default=None, max_length=128)
    set_as_default: bool = False
    seed_knowledge: bool = True


class AssignPhoneProfileBody(BaseModel):
    agent_profile_id: UUID | None = None


class ConnectPhoneBody(BaseModel):
    phone_number: str
    twilio_account_sid: str | None = None


class PurchasePhoneBody(BaseModel):
    phone_number: str
    confirm: bool = False


class ReleasePhoneBody(BaseModel):
    """Twilio SID is optional; when omitted the platform uses stored provisioning details."""

    phone_number_sid: str | None = None


class TestCallBody(BaseModel):
    agent_profile_id: UUID | None = None


def _crm_http(exc: Exception) -> HTTPException:
    if isinstance(exc, CrmError):
        status = 404 if "not_found" in exc.code else 400
        return HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        )
    if isinstance(exc, PhoneAssignError):
        status = 404 if exc.code == "not_found" else 400
        if exc.code == "dispatch_update_failed":
            status = 502
        return HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        )
    return HTTPException(
        status_code=500, detail={"code": "internal", "message": str(exc)}
    )


def _rate_limit(user: CurrentUser) -> None:
    try:
        AGENT_SETTINGS_RATE_LIMITER.check(f"admin:{user.user_id}")
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "rate_limited",
                "message": "Too many updates. Try again shortly.",
            },
            headers={"Retry-After": str(int(exc.retry_after_sec) + 1)},
        ) from exc


@router.get("/industry-templates")
def industry_templates(
    user: CurrentUser = Depends(_require_agents_read),  # noqa: B008
) -> dict[str, Any]:
    _ = user
    return {"templates": list_templates()}


@router.get("/marketplace")
def marketplace_catalog(
    user: CurrentUser = Depends(_require_agents_read),  # noqa: B008
) -> dict[str, Any]:
    _ = user
    return list_marketplace_catalog()


@router.post("/marketplace/install")
def marketplace_install(
    body: MarketplaceInstallBody,
    user: CurrentUser = Depends(_require_agents_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    _rate_limit(user)
    try:
        profile = AgentProfileRepository(session).install_from_marketplace(
            user.tenant_id,
            industry_key=body.industry_key,
            name=body.name,
            set_as_default=body.set_as_default,
            seed_knowledge=body.seed_knowledge,
            actor=user.email,
        )
        return {"profile": profile, "business_name": user.tenant_name}
    except Exception as exc:
        raise _crm_http(exc) from exc


@router.get("/agent-profiles")
def list_agent_profiles(
    include_archived: bool = False,
    user: CurrentUser = Depends(_require_agents_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    profiles = AgentProfileRepository(session).list(
        user.tenant_id, include_archived=include_archived
    )
    return {"profiles": profiles, "business_name": user.tenant_name}


@router.post("/agent-profiles")
def create_agent_profile(
    body: CreateProfileBody,
    user: CurrentUser = Depends(_require_agents_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    _rate_limit(user)
    try:
        fields = body.model_dump(exclude_unset=True)
        name = fields.pop("name")
        agent_type = fields.pop("agent_type", "receptionist")
        industry_key = fields.pop("industry_key", None)
        is_default = bool(fields.pop("is_default", False))
        profile = AgentProfileRepository(session).create(
            user.tenant_id,
            name=name,
            agent_type=agent_type,
            industry_key=industry_key,
            is_default=is_default,
            actor=user.email,
            **fields,
        )
        if industry_key and get_template(industry_key) is not None:
            profile = AgentProfileRepository(session).apply_template(
                user.tenant_id,
                UUID(profile["id"]),
                industry_key=industry_key,
                actor=user.email,
            )
        return {"profile": profile, "business_name": user.tenant_name}
    except Exception as exc:
        raise _crm_http(exc) from exc


@router.get("/agent-profiles/{profile_id}")
def get_agent_profile(
    profile_id: UUID,
    user: CurrentUser = Depends(_require_agents_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    profile = AgentProfileRepository(session).get(user.tenant_id, profile_id)
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Agent profile not found"},
        )
    return {"profile": profile, "business_name": user.tenant_name}


@router.put("/agent-profiles/{profile_id}")
def update_agent_profile(
    profile_id: UUID,
    body: UpdateProfileBody,
    user: CurrentUser = Depends(_require_agents_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    _rate_limit(user)
    try:
        profile = AgentProfileRepository(session).update(
            user.tenant_id,
            profile_id,
            actor=user.email,
            **body.model_dump(exclude_unset=True),
        )
        return {"profile": profile, "business_name": user.tenant_name}
    except Exception as exc:
        raise _crm_http(exc) from exc


@router.delete("/agent-profiles/{profile_id}")
def archive_agent_profile(
    profile_id: UUID,
    user: CurrentUser = Depends(_require_agents_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    _rate_limit(user)
    try:
        profile = AgentProfileRepository(session).archive(
            user.tenant_id, profile_id, actor=user.email
        )
        return {"profile": profile}
    except Exception as exc:
        raise _crm_http(exc) from exc


@router.post("/agent-profiles/{profile_id}/set-default")
def set_default_profile(
    profile_id: UUID,
    user: CurrentUser = Depends(_require_agents_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        profile = AgentProfileRepository(session).set_default(
            user.tenant_id, profile_id, actor=user.email
        )
        return {"profile": profile}
    except Exception as exc:
        raise _crm_http(exc) from exc


@router.post("/agent-profiles/{profile_id}/apply-template")
def apply_template(
    profile_id: UUID,
    body: ApplyTemplateBody,
    user: CurrentUser = Depends(_require_agents_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    _rate_limit(user)
    try:
        profile = AgentProfileRepository(session).apply_template(
            user.tenant_id,
            profile_id,
            industry_key=body.industry_key,
            actor=user.email,
            seed_knowledge=body.seed_knowledge,
        )
        return {"profile": profile, "business_name": user.tenant_name}
    except Exception as exc:
        raise _crm_http(exc) from exc


def _phone_service(
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
    signer: MetadataSigner = Depends(signer_dep),  # noqa: B008
) -> PhoneAssignmentService:
    livekit = LiveKitSipService(
        url=settings.livekit_url,
        api_key=settings.livekit_api_key,
        api_secret=settings.livekit_api_secret,
    )
    return PhoneAssignmentService(
        session, signer=signer, livekit=livekit, settings=settings
    )


@router.get("/phone-numbers")
def list_phone_numbers(
    user: CurrentUser = Depends(_require_phones),  # noqa: B008
    service: PhoneAssignmentService = Depends(_phone_service),  # noqa: B008
) -> dict[str, Any]:
    return {"items": service.list_phones(user.tenant_id)}


@router.patch("/phone-numbers/{phone_number_id}")
def assign_phone_profile(
    phone_number_id: UUID,
    body: AssignPhoneProfileBody,
    user: CurrentUser = Depends(_require_phones),  # noqa: B008
    service: PhoneAssignmentService = Depends(_phone_service),  # noqa: B008
) -> dict[str, Any]:
    try:
        item = service.assign_profile(
            user.tenant_id,
            phone_number_id,
            agent_profile_id=body.agent_profile_id,
            actor=user.email,
        )
        return {"phone_number": item}
    except Exception as exc:
        raise _crm_http(exc) from exc


@router.post("/phone-numbers/connect")
def connect_phone(
    body: ConnectPhoneBody,
    user: CurrentUser = Depends(_require_phones),  # noqa: B008
    service: ConnectExistingService = Depends(connect_service),  # noqa: B008
) -> dict[str, Any]:
    try:
        return service.start(
            tenant_id=user.tenant_id,
            phone_number=body.phone_number,
            twilio_account_sid=body.twilio_account_sid,
            actor=user.email,
        )
    except ConnectExistingError as exc:
        status = 409 if exc.code == "duplicate_number" else 400
        if exc.code == "partial_provisioning":
            status = 502
        raise HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        ) from exc


class ConfirmTrunkBody(BaseModel):
    twilio_trunk_sid: str | None = None


@router.post("/phone-numbers/{phone_number_id}/confirm-trunk")
def confirm_trunk(
    phone_number_id: UUID,
    body: ConfirmTrunkBody,
    user: CurrentUser = Depends(_require_phones),  # noqa: B008
    service: ConnectExistingService = Depends(connect_service),  # noqa: B008
) -> dict[str, Any]:
    try:
        return service.confirm_trunk(
            tenant_id=user.tenant_id,
            phone_number_id=phone_number_id,
            twilio_trunk_sid=body.twilio_trunk_sid,
            actor=user.email,
        )
    except ConnectExistingError as exc:
        raise HTTPException(
            status_code=404 if exc.code == "not_found" else 400,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc


@router.post("/phone-numbers/{phone_number_id}/verification/start")
def start_verification(
    phone_number_id: UUID,
    user: CurrentUser = Depends(_require_phones),  # noqa: B008
    service: DbNumberVerificationService = Depends(verification_service),  # noqa: B008
) -> dict[str, Any]:
    try:
        return service.start_verification(
            tenant_id=user.tenant_id, phone_number_id=phone_number_id
        )
    except VerificationError as exc:
        raise HTTPException(
            status_code=400, detail={"code": exc.code, "message": str(exc)}
        ) from exc


@router.post("/twilio/subaccount")
def ensure_subaccount(
    user: CurrentUser = Depends(_require_phones),  # noqa: B008
    service: PlatformPurchaseService = Depends(purchase_service),  # noqa: B008
) -> dict[str, Any]:
    try:
        return service.ensure_subaccount(tenant_id=user.tenant_id, actor=user.email)
    except PurchaseError as exc:
        raise HTTPException(
            status_code=400, detail={"code": exc.code, "message": str(exc)}
        ) from exc


@router.get("/inventory")
def search_inventory(
    country: str = "US",
    area_code: str | None = None,
    number_type: str = "local",
    limit: int = 20,
    user: CurrentUser = Depends(_require_phones),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    service: PlatformPurchaseService = Depends(purchase_service),  # noqa: B008
) -> dict[str, Any]:
    from callbot_platform.domain.phone import PhoneNumberError, normalize_area_code
    from callbot_platform.telephony.adapters.twilio_adapter import TwilioApiError

    try:
        normalized_area = normalize_area_code(area_code, country=country)
        service.ensure_subaccount(tenant_id=user.tenant_id, actor=user.email)
        session.commit()
        items = service.search_inventory(
            tenant_id=user.tenant_id,
            country=country,
            area_code=normalized_area,
            number_type=number_type,
            limit=limit,
        )
        return {"items": items, "area_code": normalized_area}
    except PhoneNumberError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_area_code", "message": str(exc)},
        ) from exc
    except TwilioApiError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "inventory_search_failed", "message": str(exc)},
        ) from exc
    except PurchaseError as exc:
        raise HTTPException(
            status_code=400, detail={"code": exc.code, "message": str(exc)}
        ) from exc


@router.post("/phone-numbers/purchase")
def purchase_phone(
    body: PurchasePhoneBody,
    user: CurrentUser = Depends(_require_phones),  # noqa: B008
    service: PlatformPurchaseService = Depends(purchase_service),  # noqa: B008
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    try:
        return service.purchase(
            tenant_id=user.tenant_id,
            phone_number=body.phone_number,
            confirm=body.confirm,
            idempotency_key=idempotency_key or str(uuid4()),
            actor=user.email,
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


@router.post("/phone-numbers/{phone_number_id}/release")
def release_phone(
    phone_number_id: UUID,
    body: ReleasePhoneBody,
    user: CurrentUser = Depends(_require_phones),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
    service: PlatformPurchaseService = Depends(purchase_service),  # noqa: B008
) -> dict[str, Any]:
    try:
        from callbot_platform.async_jobs.handlers.telephony import (
            TelephonyProvisionHandler,
        )
        from callbot_platform.async_jobs.runner import run_async_job
        from callbot_platform.db import get_session_factory
        from callbot_platform.db.models import TenantPhoneNumber

        result = service.release(
            tenant_id=user.tenant_id,
            phone_number_id=phone_number_id,
            phone_number_sid=body.phone_number_sid,
            actor=user.email,
        )
        job_id = result.get("job_id")
        session.commit()
        if job_id:
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
                    TenantPhoneNumber.tenant_id == user.tenant_id,
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


@router.post("/test-call")
def create_test_call(
    body: TestCallBody,
    user: CurrentUser = Depends(_require_ai_configure),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
    signer: MetadataSigner = Depends(signer_dep),  # noqa: B008
) -> dict[str, Any]:
    """Issue a LiveKit browser token with signed tenant + agent_profile metadata."""
    profiles = AgentProfileRepository(session)
    profile_id = body.agent_profile_id
    if profile_id is None:
        default = profiles.get_default(user.tenant_id)
        if default is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "agent_profile_missing",
                    "message": "Create an agent profile before testing",
                },
            )
        profile_id = UUID(default["id"])
    else:
        profile = profiles.get(user.tenant_id, profile_id)
        if profile is None or profile.get("status") != "active":
            raise HTTPException(
                status_code=404,
                detail={"code": "not_found", "message": "Agent profile not found"},
            )

    if (
        not settings.livekit_url
        or not settings.livekit_api_key
        or not settings.livekit_api_secret
    ):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "livekit_not_configured",
                "message": "LiveKit credentials are not configured on the platform",
            },
        )

    metadata = signer.sign_payload(
        {
            "tenant_id": str(user.tenant_id),
            "agent_profile_id": str(profile_id),
            "source": "ops_test_call",
        }
    )
    room_name = f"ops-test-{user.tenant_id.hex[:8]}-{uuid4().hex[:8]}"
    identity = f"ops-{user.user_id.hex[:8]}"
    token = (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_name(user.name or user.email)
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
            )
        )
        .with_room_config(
            api.RoomConfiguration(
                agents=[
                    api.RoomAgentDispatch(
                        agent_name=settings.agent_name,
                        metadata=metadata,
                    )
                ]
            )
        )
        .to_jwt()
    )
    return {
        "server_url": settings.livekit_url,
        "participant_token": token,
        "room_name": room_name,
        "agent_profile_id": str(profile_id),
        "metadata": metadata,
        "expires_at": int(time.time()) + 60 * 30,
    }

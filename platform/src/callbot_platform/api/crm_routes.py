"""Internal CRM HTTP API (service-token authenticated)."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from callbot_platform.api.deps import db_dep, require_internal_token
from callbot_platform.config import get_settings
from callbot_platform.crm.repos import (
    AgentProfileRepository,
    AgentSettingsRepository,
    CallRepository,
    CrmError,
    CustomerRepository,
    LeadRepository,
)
from callbot_platform.db.models import Tenant
from callbot_platform.domain.phone import PhoneNumberError
from callbot_platform.security.call_scope import (
    CallScope,
    CallScopeSigner,
    enforce_body_call,
    enforce_body_tenant,
    optional_or_required_call_scope,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/internal/crm",
    dependencies=[Depends(require_internal_token)],
)


class LookupBody(BaseModel):
    tenant_id: UUID
    phone: str


class UpsertCustomerBody(BaseModel):
    tenant_id: UUID
    name: str
    phone: str
    email: str | None = None
    address: str | None = None


class CreateLeadBody(BaseModel):
    tenant_id: UUID
    customer_id: UUID
    service_type: str
    urgency: str = "normal"
    notes: str | None = None
    preferred_time_window: str | None = None
    call_id: UUID | None = None
    idempotency_key: str | None = None


class CallStartBody(BaseModel):
    tenant_id: UUID
    room_name: str
    job_id: str | None = None
    customer_id: UUID | None = None
    caller_number: str | None = None
    called_number: str | None = None
    telephony_provider: str | None = None
    provider_call_id: str | None = None


class CallEndBody(BaseModel):
    tenant_id: UUID
    call_id: UUID
    status: str = "closed"
    disconnect_reason: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    customer_id: UUID | None = None


class AgentSettingsBody(BaseModel):
    model_config = {"extra": "forbid"}

    business_prompt_facts: dict[str, Any] | None = None
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
    booking_rules: str | None = None
    pricing_disclosure_policy: str | None = None
    handoff_rules_text: str | None = None
    restricted_topics: list[str] | None = None
    custom_instructions: str | None = None


def apply_agent_settings_upsert(
    session: Session,
    *,
    tenant_id: UUID,
    body: AgentSettingsBody,
    actor: str,
) -> dict[str, Any]:
    return AgentSettingsRepository(session).upsert(
        tenant_id,
        business_prompt_facts=body.business_prompt_facts,
        voice=body.voice,
        language=body.language,
        greeting=body.greeting,
        assistant_name=body.assistant_name,
        business_description=body.business_description,
        tone=body.tone,
        supported_languages=body.supported_languages,
        response_style=body.response_style,
        service_areas=body.service_areas,
        business_hours_summary=body.business_hours_summary,
        booking_rules=body.booking_rules,
        pricing_disclosure_policy=body.pricing_disclosure_policy,
        handoff_rules_text=body.handoff_rules_text,
        restricted_topics=body.restricted_topics,
        custom_instructions=body.custom_instructions,
        actor=actor,
    )


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, CrmError):
        status = 404 if "not_found" in exc.code else 400
        return HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        )
    if isinstance(exc, PhoneNumberError):
        return HTTPException(
            status_code=400, detail={"code": "invalid_phone", "message": str(exc)}
        )
    return HTTPException(
        status_code=500, detail={"code": "internal", "message": str(exc)}
    )


@router.post("/customers/lookup")
def lookup_customer(body: LookupBody, session: Session = Depends(db_dep)) -> dict:
    try:
        result = CustomerRepository(session).lookup_by_phone(body.tenant_id, body.phone)
        if result is None:
            return {"found": False, "customer": None}
        return {"found": True, "customer": result}
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/customers/upsert")
def upsert_customer(
    body: UpsertCustomerBody, session: Session = Depends(db_dep)
) -> dict:
    try:
        customer = CustomerRepository(session).upsert(
            body.tenant_id,
            name=body.name,
            phone=body.phone,
            email=body.email,
            address=body.address,
        )
        return {"customer": customer}
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/leads")
def create_lead(body: CreateLeadBody, session: Session = Depends(db_dep)) -> dict:
    try:
        lead = LeadRepository(session).create(
            body.tenant_id,
            customer_id=body.customer_id,
            service_type=body.service_type,
            urgency=body.urgency,
            notes=body.notes,
            preferred_time_window=body.preferred_time_window,
            call_id=body.call_id,
            idempotency_key=body.idempotency_key,
        )
        return {"lead": lead}
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/leads/{lead_id}")
def get_lead(
    lead_id: UUID,
    tenant_id: UUID,
    session: Session = Depends(db_dep),
) -> dict:
    lead = LeadRepository(session).get(tenant_id, lead_id)
    if lead is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "lead_not_found", "message": "Lead not found for tenant"},
        )
    return {"lead": lead}


@router.post("/calls/start")
def call_start(
    body: CallStartBody,
    session: Session = Depends(db_dep),
    scope: CallScope | None = Depends(optional_or_required_call_scope),
) -> dict:
    if scope is not None:
        enforce_body_tenant(scope, body.tenant_id)
    try:
        call = CallRepository(session).start(
            body.tenant_id,
            room_name=body.room_name,
            job_id=body.job_id,
            customer_id=body.customer_id,
            caller_number=body.caller_number,
            called_number=body.called_number,
            telephony_provider=body.telephony_provider,
            provider_call_id=body.provider_call_id,
        )
        settings = get_settings()
        call_scope_token = None
        if settings.metadata_hmac_secret:
            call_scope_token = CallScopeSigner(settings.metadata_hmac_secret).issue(
                tenant_id=body.tenant_id,
                call_id=UUID(call["id"]),
                room_name=body.room_name,
                ttl_seconds=settings.call_scope_ttl_seconds,
            )
        return {"call": call, "call_scope": call_scope_token}
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/calls/end")
def call_end(
    body: CallEndBody,
    session: Session = Depends(db_dep),
    scope: CallScope | None = Depends(optional_or_required_call_scope),
) -> dict:
    if scope is not None:
        enforce_body_tenant(scope, body.tenant_id)
        enforce_body_call(scope, body.call_id)
    try:
        call = CallRepository(session).end(
            body.tenant_id,
            call_id=body.call_id,
            status=body.status,
            disconnect_reason=body.disconnect_reason,
            metrics=body.metrics,
            customer_id=body.customer_id,
        )
        from callbot_platform.automation.service import AutomationService

        automation = AutomationService(session)
        payload = {
            "call_id": call["id"],
            "customer_id": call.get("customer_id"),
            "status": call.get("status"),
            "disconnect_reason": call.get("disconnect_reason"),
        }
        fired = automation.dispatch(body.tenant_id, "call.ended", payload=payload)
        metrics = body.metrics if isinstance(body.metrics, dict) else {}
        if metrics.get("handoff_requested"):
            fired.extend(
                automation.dispatch(
                    body.tenant_id, "call.handoff_requested", payload=payload
                )
            )
            from callbot_platform.queue import CallQueueRepository, QueueError

            try:
                queued = CallQueueRepository(session).enqueue_for_call(
                    body.tenant_id,
                    body.call_id,
                    reason="handoff",
                    priority=10,
                    actor="voice-agent",
                )
                if queued is not None:
                    call["queue_item"] = queued
            except QueueError as exc:
                logger.warning(
                    "call_queue_enqueue_failed",
                    extra={
                        "tenant_id": str(body.tenant_id),
                        "call_id": str(body.call_id),
                        "code": exc.code,
                    },
                )
        call["automations"] = fired
        return {"call": call}
    except Exception as exc:
        raise _http_error(exc) from exc


tenant_settings_router = APIRouter(prefix="/tenants")

internal_tenant_router = APIRouter(
    prefix="/internal/tenants",
    dependencies=[Depends(require_internal_token)],
)


@internal_tenant_router.get("/{tenant_id}/agent-profile")
def get_agent_profile(
    tenant_id: UUID,
    session: Session = Depends(db_dep),
    agent_profile_id: UUID | None = None,
) -> dict:
    """Voice-agent startup: fail closed when no active profile exists.

    Optional agent_profile_id query param selects a specific profile; otherwise
    the tenant default is used (back-compat).
    """
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "tenant_not_found", "message": "Tenant not found"},
        )
    if tenant.status != "active":
        raise HTTPException(
            status_code=404,
            detail={"code": "tenant_inactive", "message": "Tenant is not active"},
        )
    repo = AgentProfileRepository(session)
    profile = repo.get_voice_profile(
        tenant_id, business_name=tenant.name, profile_id=agent_profile_id
    )
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "agent_profile_missing",
                "message": "No agent profile configured for tenant",
            },
        )
    if not str(profile.get("business_name") or "").strip():
        raise HTTPException(
            status_code=422,
            detail={
                "code": "agent_profile_invalid",
                "message": "Agent profile is missing business_name",
            },
        )
    return {"profile": profile}


@internal_tenant_router.get("/{tenant_id}/agent-profiles/{profile_id}")
def get_agent_profile_by_id(
    tenant_id: UUID, profile_id: UUID, session: Session = Depends(db_dep)
) -> dict:
    return get_agent_profile(tenant_id, session, agent_profile_id=profile_id)


@internal_tenant_router.get("/{tenant_id}/agent-profile/meta")
def get_agent_profile_meta(
    tenant_id: UUID,
    session: Session = Depends(db_dep),
    agent_profile_id: UUID | None = None,
) -> dict:
    """Lightweight version check for voice-agent cache invalidation."""
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "tenant_not_found", "message": "Tenant not found"},
        )
    meta = AgentProfileRepository(session).get_voice_profile_meta(
        tenant_id, profile_id=agent_profile_id
    )
    if meta is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "agent_profile_missing",
                "message": "No agent profile configured for tenant",
            },
        )
    return {"meta": meta}


@internal_tenant_router.get("/{tenant_id}/agent-profiles/{profile_id}/meta")
def get_agent_profile_meta_by_id(
    tenant_id: UUID, profile_id: UUID, session: Session = Depends(db_dep)
) -> dict:
    return get_agent_profile_meta(tenant_id, session, agent_profile_id=profile_id)


@internal_tenant_router.put("/{tenant_id}/agent-settings")
def put_agent_settings_internal(
    tenant_id: UUID,
    body: AgentSettingsBody,
    session: Session = Depends(db_dep),
) -> dict:
    """Platform super-admin override via X-Internal-Token (never from body)."""
    from callbot_platform.security.rate_limit import (
        AGENT_SETTINGS_RATE_LIMITER,
        RateLimitExceeded,
    )

    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    try:
        AGENT_SETTINGS_RATE_LIMITER.check(f"internal:{tenant_id}")
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "rate_limited",
                "message": "Too many agent settings updates",
            },
            headers={"Retry-After": str(int(exc.retry_after_sec) + 1)},
        ) from exc
    settings = apply_agent_settings_upsert(
        session,
        tenant_id=tenant_id,
        body=body,
        actor="platform_internal",
    )
    return {"settings": settings}


@tenant_settings_router.get("/{tenant_id}/agent-settings")
def get_agent_settings_legacy(tenant_id: UUID) -> dict:
    """Removed: unauthenticated access is no longer allowed."""
    raise HTTPException(
        status_code=401,
        detail={
            "code": "auth_required",
            "message": "Use GET /api/admin/agent-settings with a tenant admin session",
        },
    )


@tenant_settings_router.put("/{tenant_id}/agent-settings")
def put_agent_settings_legacy(tenant_id: UUID, body: AgentSettingsBody) -> dict:
    """Removed: unauthenticated writes are no longer allowed."""
    raise HTTPException(
        status_code=401,
        detail={
            "code": "auth_required",
            "message": (
                "Use PUT /api/admin/agent-settings (tenant admin) or "
                "PUT /internal/tenants/{id}/agent-settings (platform token)"
            ),
        },
    )

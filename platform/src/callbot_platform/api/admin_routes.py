"""Tenant admin APIs: CRM lists, metrics, users, retention, audit."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from callbot_platform.admin.repos import AdminError, AdminRepository
from callbot_platform.api.deps import CurrentUser, db_dep, require_entitled_ops_roles
from callbot_platform.auth.repos import AuthError, AuthRepository
from callbot_platform.security.session import (
    ROLE_ADMIN,
    ROLE_DISPATCHER,
    VALID_ROLES,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


class InviteUserBody(BaseModel):
    email: str
    password: str = Field(min_length=8)
    name: str
    role: str
    phone: str | None = None


class UpdateUserBody(BaseModel):
    model_config = {"extra": "forbid"}

    name: str | None = Field(default=None, max_length=255)
    role: str | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8)


class RetentionBody(BaseModel):
    recording_retention_days: int | None = None
    transcript_retention_days: int | None = None
    audit_retention_days: int | None = None


@router.get("/customers")
def customers(
    user: CurrentUser = Depends(
        require_entitled_ops_roles(ROLE_ADMIN, ROLE_DISPATCHER)
    ),
    session: Session = Depends(db_dep),
) -> dict[str, Any]:
    return {"customers": AdminRepository(session).list_customers(user.tenant_id)}


@router.get("/calls")
def calls(
    user: CurrentUser = Depends(
        require_entitled_ops_roles(ROLE_ADMIN, ROLE_DISPATCHER)
    ),
    session: Session = Depends(db_dep),
    status: str | None = Query(
        default=None,
        max_length=32,
        description="Optional status filter (e.g. active for live monitoring)",
    ),
    limit: int = Query(default=100, ge=1, le=200),
) -> dict[str, Any]:
    try:
        return {
            "calls": AdminRepository(session).list_calls(
                user.tenant_id, status=status, limit=limit
            )
        }
    except AdminError as exc:
        raise HTTPException(
            status_code=400, detail={"code": exc.code, "message": str(exc)}
        ) from exc


@router.get("/appointments")
def appointments(
    user: CurrentUser = Depends(
        require_entitled_ops_roles(ROLE_ADMIN, ROLE_DISPATCHER)
    ),
    session: Session = Depends(db_dep),
) -> dict[str, Any]:
    return {"appointments": AdminRepository(session).list_appointments(user.tenant_id)}


@router.get("/metrics")
def metrics(
    days: int = 30,
    user: CurrentUser = Depends(
        require_entitled_ops_roles(ROLE_ADMIN, ROLE_DISPATCHER)
    ),
    session: Session = Depends(db_dep),
) -> dict[str, Any]:
    return {
        "metrics": AdminRepository(session).metrics_summary(user.tenant_id, days=days)
    }


@router.get("/audit")
def audit(
    user: CurrentUser = Depends(require_entitled_ops_roles(ROLE_ADMIN)),
    session: Session = Depends(db_dep),
) -> dict[str, Any]:
    return {"events": AdminRepository(session).list_audit(user.tenant_id)}


@router.get("/users")
def users(
    user: CurrentUser = Depends(require_entitled_ops_roles(ROLE_ADMIN)),
    session: Session = Depends(db_dep),
) -> dict[str, Any]:
    return {"users": AdminRepository(session).list_users(user.tenant_id)}


@router.post("/users")
def invite_user(
    body: InviteUserBody,
    user: CurrentUser = Depends(require_entitled_ops_roles(ROLE_ADMIN)),
    session: Session = Depends(db_dep),
) -> dict[str, Any]:
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    try:
        created = AuthRepository(session).create_user(
            user.tenant_id,
            email=body.email,
            password=body.password,
            name=body.name,
            role=body.role,
            phone=body.phone,
            actor=user.email,
        )
        return {"user": created}
    except AuthError as exc:
        raise HTTPException(
            status_code=400, detail={"code": exc.code, "message": str(exc)}
        ) from exc


@router.patch("/users/{user_id}")
def update_user(
    user_id: str,
    body: UpdateUserBody,
    user: CurrentUser = Depends(require_entitled_ops_roles(ROLE_ADMIN)),
    session: Session = Depends(db_dep),
) -> dict[str, Any]:
    if body.role is not None and body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    try:
        updated = AuthRepository(session).update_user_admin(
            user.tenant_id,
            UUID(user_id),
            actor_user_id=user.user_id,
            actor_email=user.email,
            role=body.role,
            is_active=body.is_active,
            name=body.name,
            password=body.password,
        )
        return {"user": updated}
    except AuthError as exc:
        status = 404 if exc.code == "user_not_found" else 400
        raise HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail={"code": "invalid_user_id", "message": str(exc)}
        ) from exc


@router.get("/retention")
def get_retention(
    user: CurrentUser = Depends(require_entitled_ops_roles(ROLE_ADMIN)),
    session: Session = Depends(db_dep),
) -> dict[str, Any]:
    return {"settings": AdminRepository(session).get_retention(user.tenant_id)}


@router.put("/retention")
def put_retention(
    body: RetentionBody,
    user: CurrentUser = Depends(require_entitled_ops_roles(ROLE_ADMIN)),
    session: Session = Depends(db_dep),
) -> dict[str, Any]:
    settings = AdminRepository(session).upsert_retention(
        user.tenant_id,
        recording_retention_days=body.recording_retention_days,
        transcript_retention_days=body.transcript_retention_days,
        audit_retention_days=body.audit_retention_days,
        actor=user.email,
    )
    return {"settings": settings}


class AgentSettingsUpdateBody(BaseModel):
    """Tenant-editable agent profile fields. tenant_id is never accepted."""

    model_config = {"extra": "forbid"}

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


@router.get("/agent-settings")
def get_agent_settings(
    user: CurrentUser = Depends(require_entitled_ops_roles(ROLE_ADMIN)),
    session: Session = Depends(db_dep),
) -> dict[str, Any]:
    from callbot_platform.crm.repos import AgentSettingsRepository

    settings = AgentSettingsRepository(session).get(user.tenant_id)
    return {
        "settings": settings,
        "business_name": user.tenant_name,
    }


@router.put("/agent-settings")
def put_agent_settings(
    body: AgentSettingsUpdateBody,
    user: CurrentUser = Depends(require_entitled_ops_roles(ROLE_ADMIN)),
    session: Session = Depends(db_dep),
) -> dict[str, Any]:
    """Admin-only. Always scoped to the session tenant — never path/body tenant_id."""
    from callbot_platform.api.crm_routes import (
        AgentSettingsBody,
        apply_agent_settings_upsert,
    )
    from callbot_platform.security.rate_limit import (
        AGENT_SETTINGS_RATE_LIMITER,
        RateLimitExceeded,
    )

    try:
        AGENT_SETTINGS_RATE_LIMITER.check(f"admin:{user.user_id}")
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "rate_limited",
                "message": "Too many agent settings updates. Try again shortly.",
            },
            headers={"Retry-After": str(int(exc.retry_after_sec) + 1)},
        ) from exc

    payload = AgentSettingsBody(**body.model_dump(exclude_unset=True))
    settings = apply_agent_settings_upsert(
        session,
        tenant_id=user.tenant_id,
        body=payload,
        actor=user.email,
    )
    return {"settings": settings, "business_name": user.tenant_name}

"""Ops session authentication routes."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from callbot_platform.api.deps import (
    CurrentUser,
    db_dep,
    require_internal_token,
    require_tenant_user,
    settings_dep,
)
from callbot_platform.auth.repos import AuthError, AuthRepository
from callbot_platform.billing.errors import BillingError
from callbot_platform.billing.service import BillingService
from callbot_platform.config import Settings
from callbot_platform.origins import session_cookie_params
from callbot_platform.rbac.service import AuthorizationService
from callbot_platform.security.rate_limit import (
    AUTH_LOGIN_RATE_LIMITER,
    AUTH_SIGNUP_RATE_LIMITER,
    RateLimitExceeded,
    SlidingWindowRateLimiter,
)
from callbot_platform.security.session import create_session_token

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_rate_key(request: Request, *parts: str) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    host = forwarded or (request.client.host if request.client else "unknown")
    return "|".join((host, *parts))


def _enforce_auth_rate_limit(limiter: SlidingWindowRateLimiter, key: str) -> None:
    try:
        limiter.check(key)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "rate_limited",
                "message": "Too many authentication attempts",
            },
            headers={"Retry-After": str(int(exc.retry_after_sec) + 1)},
        ) from exc


def _enrich_user_session(session: Session, user: dict[str, Any]) -> dict[str, Any]:
    """Attach effective RBAC roles/permissions for frontend UX (not authority)."""
    authz = AuthorizationService(session)
    access = authz.serialize_effective_access(
        UUID(str(user["tenant_id"])),
        UUID(str(user["id"])),
    )
    return {**user, **access}


class LoginBody(BaseModel):
    model_config = {"extra": "forbid"}

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)
    tenant_slug: str = Field(min_length=1, max_length=64)


class BootstrapBody(BaseModel):
    model_config = {"extra": "forbid"}

    tenant_id: UUID
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=255)


class SignupBody(BaseModel):
    model_config = {"extra": "forbid"}

    business_name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=2, max_length=64)
    timezone: str = Field(default="UTC", max_length=64)
    name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    plan_key: str = Field(min_length=1, max_length=32)


class UpdateProfileBody(BaseModel):
    model_config = {"extra": "forbid"}

    name: str | None = Field(default=None, min_length=1, max_length=255)
    current_password: str | None = None
    new_password: str | None = Field(default=None, min_length=8)


def _auth_http(exc: Exception, *, login: bool = False) -> HTTPException:
    if isinstance(exc, AuthError):
        # Login: avoid account/tenant enumeration via distinct codes/status.
        if login and exc.code in {"invalid_credentials", "tenant_not_found"}:
            return HTTPException(
                status_code=401,
                detail={
                    "code": "invalid_credentials",
                    "message": "Invalid email, password, or organization",
                },
            )
        status = 401 if exc.code == "invalid_credentials" else 400
        if exc.code == "tenant_not_found":
            status = 404
        if exc.code == "already_bootstrapped":
            status = 409
        return HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        )
    if isinstance(exc, BillingError):
        status = 400
        if exc.code == "slug_taken":
            status = 409
        if exc.code == "stripe_not_configured":
            status = 503
        return HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        )
    return HTTPException(
        status_code=500, detail={"code": "internal", "message": str(exc)}
    )


def _set_session_cookie(
    response: Response, settings: Settings, user: dict[str, Any]
) -> None:
    token = create_session_token(
        settings=settings,
        user_id=UUID(user["id"]),
        tenant_id=UUID(user["tenant_id"]),
        role=user["role"],
        email=user["email"],
    )
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        **session_cookie_params(settings),
    )


@router.post("/signup")
def signup(
    body: SignupBody,
    request: Request,
    response: Response,
    session: Session = Depends(db_dep),
    settings: Settings = Depends(settings_dep),
) -> dict[str, Any]:
    _enforce_auth_rate_limit(
        AUTH_SIGNUP_RATE_LIMITER,
        _client_rate_key(request, "signup", body.slug.lower(), body.email.lower()),
    )
    try:
        result = BillingService(session, settings).signup(
            business_name=body.business_name,
            slug=body.slug,
            timezone=body.timezone,
            name=body.name,
            email=body.email,
            password=body.password,
            plan_key=body.plan_key,
        )
        job_id = result.get("job_id")
        tenant_id = result.get("tenant_id")
        session.commit()
        if job_id:
            from callbot_platform.async_jobs.runner import run_async_job
            from callbot_platform.db import get_session_factory

            run_async_job(get_session_factory(), UUID(str(job_id)), settings=settings)
            if tenant_id:
                checkout = BillingService(session, settings).get_signup_checkout(
                    UUID(str(tenant_id))
                )
                result["checkout_url"] = checkout.get("checkout_url")
                result["provisioning"] = checkout.get("provisioning_status")
    except Exception as exc:
        session.rollback()
        raise _auth_http(exc) from exc

    _set_session_cookie(response, settings, result["user"])
    result["user"] = _enrich_user_session(session, result["user"])
    return result


@router.post("/login")
def login(
    body: LoginBody,
    request: Request,
    response: Response,
    session: Session = Depends(db_dep),
    settings: Settings = Depends(settings_dep),
) -> dict[str, Any]:
    _enforce_auth_rate_limit(
        AUTH_LOGIN_RATE_LIMITER,
        _client_rate_key(
            request, "login", body.tenant_slug.lower(), body.email.lower()
        ),
    )
    try:
        user = AuthRepository(session).authenticate(
            tenant_slug=body.tenant_slug,
            email=body.email,
            password=body.password,
        )
    except Exception as exc:
        raise _auth_http(exc, login=True) from exc

    _set_session_cookie(response, settings, user)
    return {"user": _enrich_user_session(session, user)}


@router.post("/logout")
def logout(
    response: Response,
    settings: Settings = Depends(settings_dep),
) -> dict[str, bool]:
    params = session_cookie_params(settings)
    response.delete_cookie(
        settings.session_cookie_name,
        path=params["path"],
        secure=params["secure"],
        httponly=params["httponly"],
        samesite=params["samesite"],
    )
    return {"ok": True}


@router.get("/me")
def me(
    user: CurrentUser = Depends(require_tenant_user),
    session: Session = Depends(db_dep),
) -> dict[str, Any]:
    return {"user": _enrich_user_session(session, user.as_dict())}


@router.get("/me/permissions")
def me_permissions(
    user: CurrentUser = Depends(require_tenant_user),
    session: Session = Depends(db_dep),
) -> dict[str, Any]:
    """Effective permissions for the authenticated session user only."""
    return AuthorizationService(session).serialize_effective_access(
        user.tenant_id, user.user_id
    )


@router.put("/me")
def update_me(
    body: UpdateProfileBody,
    user: CurrentUser = Depends(require_tenant_user),
    session: Session = Depends(db_dep),
) -> dict[str, Any]:
    if body.name is None and body.new_password is None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "nothing_to_update",
                "message": "Provide a name and/or a new password",
            },
        )
    try:
        updated = AuthRepository(session).update_profile(
            tenant_id=user.tenant_id,
            user_id=user.user_id,
            name=body.name,
            current_password=body.current_password,
            new_password=body.new_password,
            actor=user.email,
        )
    except Exception as exc:
        raise _auth_http(exc) from exc
    return {"user": _enrich_user_session(session, updated)}


@router.post("/bootstrap", dependencies=[Depends(require_internal_token)])
def bootstrap(
    body: BootstrapBody,
    session: Session = Depends(db_dep),
) -> dict[str, Any]:
    try:
        user = AuthRepository(session).bootstrap_admin(
            tenant_id=body.tenant_id,
            email=body.email,
            password=body.password,
            name=body.name,
        )
        return {"user": user}
    except Exception as exc:
        raise _auth_http(exc) from exc

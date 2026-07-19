"""Ops session authentication routes."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
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
from callbot_platform.config import Settings
from callbot_platform.security.session import create_session_token

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginBody(BaseModel):
    email: str
    password: str
    tenant_slug: str


class BootstrapBody(BaseModel):
    tenant_id: UUID
    email: str
    password: str = Field(min_length=8)
    name: str


class UpdateProfileBody(BaseModel):
    model_config = {"extra": "forbid"}

    name: str | None = Field(default=None, min_length=1, max_length=255)
    current_password: str | None = None
    new_password: str | None = Field(default=None, min_length=8)


def _auth_http(exc: Exception) -> HTTPException:
    if isinstance(exc, AuthError):
        status = 401 if exc.code == "invalid_credentials" else 400
        if exc.code == "tenant_not_found":
            status = 404
        if exc.code == "already_bootstrapped":
            status = 409
        return HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        )
    return HTTPException(
        status_code=500, detail={"code": "internal", "message": str(exc)}
    )


@router.post("/login")
def login(
    body: LoginBody,
    response: Response,
    session: Session = Depends(db_dep),
    settings: Settings = Depends(settings_dep),
) -> dict[str, Any]:
    try:
        user = AuthRepository(session).authenticate(
            tenant_slug=body.tenant_slug,
            email=body.email,
            password=body.password,
        )
        token = create_session_token(
            settings=settings,
            user_id=UUID(user["id"]),
            tenant_id=UUID(user["tenant_id"]),
            role=user["role"],
            email=user["email"],
        )
    except Exception as exc:
        raise _auth_http(exc) from exc

    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=settings.session_ttl_hours * 3600,
        path="/",
    )
    return {"user": user}


@router.post("/logout")
def logout(
    response: Response,
    settings: Settings = Depends(settings_dep),
) -> dict[str, bool]:
    response.delete_cookie(settings.session_cookie_name, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: CurrentUser = Depends(require_tenant_user)) -> dict[str, Any]:
    return {"user": user.as_dict()}


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
    return {"user": updated}


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

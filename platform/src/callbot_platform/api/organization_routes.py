"""Ops organization (tenant business) profile and membership."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from callbot_platform.api.deps import (
    CurrentUser,
    db_dep,
    require_entitled_ops_roles,
    require_ops_roles,
)
from callbot_platform.organization import OrganizationError, OrganizationService
from callbot_platform.organization.membership import VALID_MEMBERSHIP_STATUSES
from callbot_platform.security.session import ROLE_ADMIN, VALID_ROLES

router = APIRouter(prefix="/api/admin/organization", tags=["organization"])

_require_admin = require_ops_roles(ROLE_ADMIN)
_require_entitled_admin = require_entitled_ops_roles(ROLE_ADMIN)


class OrganizationBody(BaseModel):
    model_config = {"extra": "forbid"}

    name: str | None = Field(default=None, max_length=255)
    industry: str | None = Field(default=None, max_length=64)
    business_type: str | None = Field(default=None, max_length=64)
    timezone: str | None = Field(default=None, max_length=64)
    currency: str | None = Field(default=None, max_length=3)
    country: str | None = Field(default=None, max_length=2)
    state: str | None = Field(default=None, max_length=128)
    website: str | None = Field(default=None, max_length=2048)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=255)


class CreateMemberBody(BaseModel):
    model_config = {"extra": "forbid"}

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    role: str = Field(min_length=1, max_length=32)
    status: str | None = Field(default=None, max_length=32)
    phone: str | None = Field(default=None, max_length=32)


class UpdateMemberBody(BaseModel):
    model_config = {"extra": "forbid"}

    name: str | None = Field(default=None, min_length=1, max_length=255)
    role: str | None = Field(default=None, max_length=32)
    status: str | None = Field(default=None, max_length=32)
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


def _http(exc: OrganizationError) -> HTTPException:
    status = 400
    if exc.code in {"not_found", "member_not_found"}:
        status = 404
    elif exc.code in {"slug_taken", "email_taken"}:
        status = 409
    elif exc.code == "plan_limit_exceeded":
        status = 402
    return HTTPException(
        status_code=status,
        detail={"code": exc.code, "message": str(exc)},
    )


@router.get("")
def get_organization(
    user: CurrentUser = Depends(_require_admin),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {"organization": OrganizationService(session).get(user.tenant_id)}
    except OrganizationError as exc:
        raise _http(exc) from exc


@router.patch("")
def patch_organization(
    body: OrganizationBody,
    user: CurrentUser = Depends(_require_admin),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "nothing_to_update",
                "message": "No organization fields provided",
            },
        )
    try:
        organization = OrganizationService(session).update(
            user.tenant_id,
            actor=user.email,
            **fields,
        )
        return {"organization": organization}
    except OrganizationError as exc:
        raise _http(exc) from exc


@router.get("/members")
def list_members(
    user: CurrentUser = Depends(_require_entitled_admin),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    members = OrganizationService(session).memberships.list(user.tenant_id)
    return {"members": members}


@router.post("/members")
def create_member(
    body: CreateMemberBody,
    user: CurrentUser = Depends(_require_entitled_admin),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    if body.role not in VALID_ROLES:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_role", "message": "Invalid role"},
        )
    if body.status is not None and body.status not in VALID_MEMBERSHIP_STATUSES:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_membership_status",
                "message": "Invalid membership status",
            },
        )
    try:
        member = OrganizationService(session).memberships.create(
            user.tenant_id,
            email=body.email,
            password=body.password,
            name=body.name,
            role=body.role,
            status=body.status,
            phone=body.phone,
            actor=user.email,
        )
        return {"member": member}
    except OrganizationError as exc:
        raise _http(exc) from exc


@router.get("/members/{member_id}")
def get_member(
    member_id: UUID,
    user: CurrentUser = Depends(_require_entitled_admin),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        member = OrganizationService(session).memberships.get(user.tenant_id, member_id)
        return {"member": member}
    except OrganizationError as exc:
        raise _http(exc) from exc


@router.patch("/members/{member_id}")
def patch_member(
    member_id: UUID,
    body: UpdateMemberBody,
    user: CurrentUser = Depends(_require_entitled_admin),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    if body.role is not None and body.role not in VALID_ROLES:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_role", "message": "Invalid role"},
        )
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "nothing_to_update",
                "message": "No membership fields provided",
            },
        )
    try:
        member = OrganizationService(session).memberships.update(
            user.tenant_id,
            member_id,
            actor_user_id=user.user_id,
            actor_email=user.email,
            **fields,
        )
        return {"member": member}
    except OrganizationError as exc:
        raise _http(exc) from exc

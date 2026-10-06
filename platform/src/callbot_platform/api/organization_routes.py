"""Ops organization (tenant business) profile."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from callbot_platform.api.deps import CurrentUser, db_dep, require_ops_roles
from callbot_platform.organization import OrganizationError, OrganizationService
from callbot_platform.security.session import ROLE_ADMIN

router = APIRouter(prefix="/api/admin/organization", tags=["organization"])


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


def _http(exc: OrganizationError) -> HTTPException:
    status = 404 if exc.code == "not_found" else 400
    if exc.code == "slug_taken":
        status = 409
    return HTTPException(
        status_code=status,
        detail={"code": exc.code, "message": str(exc)},
    )


@router.get("")
def get_organization(
    user: CurrentUser = Depends(require_ops_roles(ROLE_ADMIN)),
    session: Session = Depends(db_dep),
) -> dict[str, Any]:
    try:
        return {"organization": OrganizationService(session).get(user.tenant_id)}
    except OrganizationError as exc:
        raise _http(exc) from exc


@router.patch("")
def patch_organization(
    body: OrganizationBody,
    user: CurrentUser = Depends(require_ops_roles(ROLE_ADMIN)),
    session: Session = Depends(db_dep),
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

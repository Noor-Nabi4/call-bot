"""Ops white-label branding settings."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from callbot_platform.api.deps import CurrentUser, db_dep, require_entitled_ops_roles
from callbot_platform.branding import BrandingError, BrandingRepository
from callbot_platform.security.session import ROLE_ADMIN

router = APIRouter(prefix="/api/admin/branding", tags=["branding"])


class BrandingBody(BaseModel):
    model_config = {"extra": "forbid"}

    product_name: str | None = Field(default=None, max_length=128)
    logo_url: str | None = Field(default=None, max_length=2048)
    primary_color: str | None = Field(default=None, max_length=7)
    accent_color: str | None = Field(default=None, max_length=7)
    support_email: str | None = Field(default=None, max_length=255)


@router.get("")
def get_branding(
    user: CurrentUser = Depends(require_entitled_ops_roles(ROLE_ADMIN)),
    session: Session = Depends(db_dep),
) -> dict[str, Any]:
    return {"branding": BrandingRepository(session).get(user.tenant_id)}


@router.put("")
def put_branding(
    body: BrandingBody,
    user: CurrentUser = Depends(require_entitled_ops_roles(ROLE_ADMIN)),
    session: Session = Depends(db_dep),
) -> dict[str, Any]:
    try:
        branding = BrandingRepository(session).upsert(
            user.tenant_id,
            actor=user.email,
            **body.model_dump(exclude_unset=True),
        )
        return {"branding": branding}
    except BrandingError as exc:
        raise HTTPException(
            status_code=400, detail={"code": exc.code, "message": str(exc)}
        ) from exc

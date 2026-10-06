"""Admin CRUD for tenant API keys."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from callbot_platform.api.deps import CurrentUser, db_dep, require_entitled_permission
from callbot_platform.api_keys import ApiKeyError, ApiKeyRepository
from callbot_platform.security.api_keys import VALID_SCOPES

_require_api_keys = require_entitled_permission("api_keys.manage")

router = APIRouter(prefix="/api/admin/api-keys", tags=["api-keys"])


class CreateApiKeyBody(BaseModel):
    model_config = {"extra": "forbid"}

    name: str = Field(min_length=1, max_length=128)
    scopes: list[str] | None = None
    notes: str | None = Field(default=None, max_length=2000)


@router.get("")
def list_api_keys(
    user: CurrentUser = Depends(_require_api_keys),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    return {
        "keys": ApiKeyRepository(session).list_keys(user.tenant_id),
        "available_scopes": sorted(VALID_SCOPES),
    }


@router.post("")
def create_api_key(
    body: CreateApiKeyBody,
    user: CurrentUser = Depends(_require_api_keys),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        key = ApiKeyRepository(session).create_key(
            user.tenant_id,
            name=body.name,
            scopes=body.scopes,
            notes=body.notes,
            actor=user.email,
        )
        return {"key": key}
    except ApiKeyError as exc:
        raise HTTPException(
            status_code=400, detail={"code": exc.code, "message": str(exc)}
        ) from exc


@router.delete("/{key_id}")
def revoke_api_key(
    key_id: UUID,
    user: CurrentUser = Depends(_require_api_keys),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        key = ApiKeyRepository(session).revoke_key(
            user.tenant_id, key_id, actor=user.email
        )
        return {"key": key}
    except ApiKeyError as exc:
        status = 404 if exc.code == "not_found" else 400
        raise HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        ) from exc

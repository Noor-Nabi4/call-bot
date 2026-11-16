"""Public tenant API (/v1) authenticated with API keys."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from callbot_platform.admin.repos import AdminRepository
from callbot_platform.api.deps import ApiKeyPrincipal, db_dep, require_api_key

router = APIRouter(prefix="/v1", tags=["public-v1"])


@router.get("/customers")
def list_customers(
    principal: ApiKeyPrincipal = Depends(require_api_key),
    session: Session = Depends(db_dep),
    limit: int = Query(default=100, ge=1, le=200),
) -> dict[str, Any]:
    principal.require_scope("customers:read")
    customers = AdminRepository(session).list_customers(
        principal.tenant_id, limit=limit
    )
    return {"customers": customers}


@router.get("/calls")
def list_calls(
    principal: ApiKeyPrincipal = Depends(require_api_key),
    session: Session = Depends(db_dep),
    status: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=100, ge=1, le=200),
    cursor: str | None = Query(default=None, max_length=512),
) -> dict[str, Any]:
    principal.require_scope("calls:read")
    return AdminRepository(session).list_calls(
        principal.tenant_id, status=status, limit=limit, cursor=cursor
    )

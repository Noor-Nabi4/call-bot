"""Internal AI tool HTTP API for the voice agent.

Trusted tenant/call identity comes from call-scope (or explicit tenant when
REQUIRE_CALL_SCOPE is false in local/dev). Model arguments never include
tenantId, permissions, or actor identity.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from callbot_platform.ai_tools import AIToolExecutor
from callbot_platform.api.deps import db_dep, require_internal_token, settings_dep
from callbot_platform.config import Settings
from callbot_platform.security.call_scope import (
    CallScope,
    enforce_body_tenant,
    optional_or_required_call_scope,
)

router = APIRouter(
    prefix="/internal/ai/tools",
    dependencies=[Depends(require_internal_token)],
)


class ToolInvokeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Present only when call-scope is optional (dev). Prefer call-scope tenant.
    tenant_id: UUID | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    confirmed: bool = False
    confirmation_token: str | None = None
    operation_id: UUID | None = None
    # Optional session-identified customer (verified tenant-side on use).
    customer_id: UUID | None = None
    caller_phone: str | None = None


@router.get("")
def list_tools(
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    return {"tools": AIToolExecutor(session).list_tools()}


@router.post("/{tool_name}")
def invoke_tool(
    tool_name: str,
    body: ToolInvokeBody,
    session: Session = Depends(db_dep),  # noqa: B008
    scope: CallScope | None = Depends(optional_or_required_call_scope),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
) -> dict[str, Any]:
    if scope is not None:
        tenant_id = scope.tenant_id
        if body.tenant_id is not None:
            enforce_body_tenant(scope, body.tenant_id)
        call_id = scope.call_id
    else:
        if body.tenant_id is None:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "tenant_required",
                    "message": "tenant_id or call-scope is required",
                },
            )
        tenant_id = body.tenant_id
        call_id = None

    result = AIToolExecutor(
        session, hmac_secret=settings.metadata_hmac_secret or ""
    ).execute(
        tool_name,
        tenant_id=tenant_id,
        call_id=call_id,
        args=body.args,
        operation_id=body.operation_id,
        customer_id=body.customer_id,
        caller_phone=body.caller_phone,
        confirmed=body.confirmed,
        confirmation_token=body.confirmation_token,
    )
    return result

"""Phase 30 AI Agent Configuration APIs — profile, capabilities, activation."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from callbot_platform.agent_config.errors import AgentConfigError
from callbot_platform.agent_config.service import AgentConfigService
from callbot_platform.api.deps import (
    CurrentUser,
    db_dep,
    require_entitled_permission,
)

router = APIRouter(prefix="/api/admin/agent-config", tags=["agent-config"])

# Routes reuse agents.manage (profile ownership). Catalog also defines
# agent_config.* / agent_capabilities.* for finer role templates.
_require_manage = require_entitled_permission("agents.manage")


class AgentConfigUpdateBody(BaseModel):
    model_config = {"extra": "forbid"}

    operation_id: str | None = Field(default=None, max_length=128)
    name: str | None = None
    assistant_name: str | None = None
    voice: str | None = None
    language: str | None = None
    tone: str | None = None
    greeting: str | None = None
    custom_instructions: str | None = None
    business_description: str | None = None
    business_hours_summary: str | None = None
    business_hours: dict[str, Any] | None = None
    handoff_rules_text: str | None = None
    supported_languages: list[str] | None = None
    response_style: str | None = None
    status: str | None = None
    capabilities: dict[str, bool] | None = None
    transfer_rules: dict[str, bool] | None = None
    escalation_rules: dict[str, bool] | None = None
    after_hours_behavior: str | None = None


class ActivateBody(BaseModel):
    model_config = {"extra": "forbid"}

    operation_id: str | None = Field(default=None, max_length=128)


def _http(exc: AgentConfigError) -> HTTPException:
    status = 400
    if exc.code == "not_found":
        status = 404
    elif exc.code in {"AGENT_CONFIGURATION_UNAVAILABLE", "CAPABILITY_UNAVAILABLE"}:
        status = 409
    return HTTPException(
        status_code=status, detail={"code": exc.code, "message": exc.message}
    )


@router.get("/catalog")
def get_catalog(
    user: CurrentUser = Depends(_require_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    _ = user
    return {"catalog": AgentConfigService(session).catalog()}


@router.get("/profiles/{profile_id}")
def get_agent_config(
    profile_id: UUID,
    user: CurrentUser = Depends(_require_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "config": AgentConfigService(session).get_config(user.tenant_id, profile_id)
        }
    except AgentConfigError as exc:
        raise _http(exc) from exc


@router.put("/profiles/{profile_id}")
def update_agent_config(
    profile_id: UUID,
    body: AgentConfigUpdateBody,
    user: CurrentUser = Depends(_require_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    payload = body.model_dump(exclude_unset=True)
    operation_id = payload.pop("operation_id", None)
    try:
        config = AgentConfigService(session).update_config(
            user.tenant_id,
            profile_id,
            actor=user.email,
            operation_id=operation_id,
            **payload,
        )
        return {"config": config}
    except AgentConfigError as exc:
        raise _http(exc) from exc


@router.post("/profiles/{profile_id}/activate")
def activate_agent_config(
    profile_id: UUID,
    body: ActivateBody,
    user: CurrentUser = Depends(_require_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        config = AgentConfigService(session).activate(
            user.tenant_id,
            profile_id,
            actor=user.email,
            operation_id=body.operation_id,
        )
        return {"config": config}
    except AgentConfigError as exc:
        raise _http(exc) from exc

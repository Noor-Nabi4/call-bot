"""Ops CRUD for tenant automation rules."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from callbot_platform.api.deps import CurrentUser, db_dep, require_entitled_permission
from callbot_platform.automation.service import AutomationError, AutomationService

_require_automations_read = require_entitled_permission("automations.read")
_require_automations_manage = require_entitled_permission("automations.manage")

router = APIRouter(prefix="/api/admin/automations", tags=["automations"])


class RuleBody(BaseModel):
    model_config = {"extra": "forbid"}

    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    trigger_key: str = Field(min_length=1, max_length=64)
    action_key: str = Field(min_length=1, max_length=64)
    config: dict[str, Any] = Field(default_factory=dict)
    is_enabled: bool = True


class RuleUpdateBody(BaseModel):
    model_config = {"extra": "forbid"}

    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    trigger_key: str | None = Field(default=None, min_length=1, max_length=64)
    action_key: str | None = Field(default=None, min_length=1, max_length=64)
    config: dict[str, Any] | None = None
    is_enabled: bool | None = None


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, AutomationError):
        status = 404 if exc.code == "not_found" else 400
        return HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        )
    return HTTPException(
        status_code=500, detail={"code": "internal", "message": str(exc)}
    )


@router.get("/catalog")
def catalog(
    user: CurrentUser = Depends(_require_automations_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    _ = user
    return AutomationService(session).catalog()


@router.get("")
def list_rules(
    user: CurrentUser = Depends(_require_automations_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    service = AutomationService(session)
    return {"rules": service.list_rules(user.tenant_id), "catalog": service.catalog()}


@router.post("")
def create_rule(
    body: RuleBody,
    user: CurrentUser = Depends(_require_automations_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        rule = AutomationService(session).create_rule(
            user.tenant_id,
            name=body.name,
            description=body.description,
            trigger_key=body.trigger_key,
            action_key=body.action_key,
            config=body.config,
            is_enabled=body.is_enabled,
            actor=user.email,
        )
        return {"rule": rule}
    except Exception as exc:
        raise _http(exc) from exc


@router.patch("/{rule_id}")
def update_rule(
    rule_id: UUID,
    body: RuleUpdateBody,
    user: CurrentUser = Depends(_require_automations_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        rule = AutomationService(session).update_rule(
            user.tenant_id,
            rule_id,
            name=body.name,
            description=body.description,
            trigger_key=body.trigger_key,
            action_key=body.action_key,
            config=body.config,
            is_enabled=body.is_enabled,
            actor=user.email,
        )
        return {"rule": rule}
    except Exception as exc:
        raise _http(exc) from exc


@router.delete("/{rule_id}")
def delete_rule(
    rule_id: UUID,
    user: CurrentUser = Depends(_require_automations_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, bool]:
    try:
        AutomationService(session).delete_rule(
            user.tenant_id, rule_id, actor=user.email
        )
        return {"ok": True}
    except Exception as exc:
        raise _http(exc) from exc

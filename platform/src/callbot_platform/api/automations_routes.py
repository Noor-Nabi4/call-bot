"""Phase 22 Automation workflow APIs."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from callbot_platform.api.deps import CurrentUser, db_dep, require_entitled_permission
from callbot_platform.automations.service import AutomationWorkflowService
from callbot_platform.crm.errors import CrmError
from callbot_platform.rbac.errors import RbacError

router = APIRouter(prefix="/api/admin/crm", tags=["automations"])

_require_read = require_entitled_permission("automations.read")
_require_create = require_entitled_permission("automations.create")
_require_update = require_entitled_permission("automations.update")
_require_activate = require_entitled_permission("automations.activate")
_require_delete = require_entitled_permission("automations.delete")
_require_history = require_entitled_permission("automations.history")


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, RbacError):
        return HTTPException(
            status_code=403, detail={"code": exc.code, "message": str(exc)}
        )
    if isinstance(exc, CrmError):
        status = 404 if exc.code == "not_found" else 400
        return HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        )
    return HTTPException(
        status_code=500, detail={"code": "internal", "message": "Internal error"}
    )


def _actor(user: CurrentUser) -> str:
    return user.email or str(user.user_id)


class WorkflowCreateBody(BaseModel):
    model_config = {"extra": "forbid"}
    name: str = Field(min_length=1, max_length=128)
    trigger_event: str = Field(min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=4000)
    definition: dict[str, Any] | None = None


class WorkflowUpdateBody(BaseModel):
    model_config = {"extra": "forbid"}
    name: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=4000)
    trigger_event: str | None = Field(default=None, max_length=64)
    definition: dict[str, Any] | None = None


@router.get("/automations")
def list_workflows(
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    include_archived: bool = False,
) -> dict[str, Any]:
    try:
        return AutomationWorkflowService(session).list(
            user.tenant_id, include_archived=include_archived
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/automations", status_code=201)
def create_workflow(
    body: WorkflowCreateBody,
    user: CurrentUser = Depends(_require_create),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        row = AutomationWorkflowService(session).create(
            user.tenant_id,
            name=body.name,
            trigger_event=body.trigger_event,
            actor=_actor(user),
            description=body.description,
            definition=body.definition,
        )
        session.commit()
        return {"workflow": row}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.get("/automations/{workflow_id}")
def get_workflow(
    workflow_id: UUID,
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "workflow": AutomationWorkflowService(session).get(
                user.tenant_id, workflow_id
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.patch("/automations/{workflow_id}")
def update_workflow(
    workflow_id: UUID,
    body: WorkflowUpdateBody,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        fields = body.model_dump(exclude_unset=True)
        row = AutomationWorkflowService(session).update(
            user.tenant_id, workflow_id, actor=_actor(user), **fields
        )
        session.commit()
        return {"workflow": row}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.post("/automations/{workflow_id}/publish")
def publish_workflow(
    workflow_id: UUID,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        row = AutomationWorkflowService(session).publish(
            user.tenant_id, workflow_id, actor=_actor(user)
        )
        session.commit()
        return {"workflow": row}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.post("/automations/{workflow_id}/activate")
def activate_workflow(
    workflow_id: UUID,
    user: CurrentUser = Depends(_require_activate),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        row = AutomationWorkflowService(session).activate(
            user.tenant_id, workflow_id, actor=_actor(user)
        )
        session.commit()
        return {"workflow": row}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.post("/automations/{workflow_id}/disable")
def disable_workflow(
    workflow_id: UUID,
    user: CurrentUser = Depends(_require_activate),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        row = AutomationWorkflowService(session).disable(
            user.tenant_id, workflow_id, actor=_actor(user)
        )
        session.commit()
        return {"workflow": row}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.post("/automations/{workflow_id}/archive")
def archive_workflow(
    workflow_id: UUID,
    user: CurrentUser = Depends(_require_delete),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        row = AutomationWorkflowService(session).archive(
            user.tenant_id, workflow_id, actor=_actor(user)
        )
        session.commit()
        return {"workflow": row}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.get("/automations/{workflow_id}/executions")
def list_executions(
    workflow_id: UUID,
    user: CurrentUser = Depends(_require_history),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    try:
        return AutomationWorkflowService(session).list_executions(
            user.tenant_id,
            workflow_id,
            status=status,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/automation-executions/{execution_id}")
def get_execution(
    execution_id: UUID,
    user: CurrentUser = Depends(_require_history),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "execution": AutomationWorkflowService(session).get_execution(
                user.tenant_id, execution_id
            )
        }
    except Exception as exc:
        raise _http(exc) from exc

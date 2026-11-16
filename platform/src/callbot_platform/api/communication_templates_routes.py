"""Communication Templates admin APIs (Phase 25)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from callbot_platform.api.deps import CurrentUser, db_dep, require_entitled_permission
from callbot_platform.communication_templates import (
    CommunicationTemplateError,
    CommunicationTemplateService,
)
from callbot_platform.rbac.errors import RbacError

router = APIRouter(prefix="/api/admin/crm", tags=["communication-templates"])

_require_read = require_entitled_permission("communication_templates.read")
_require_update = require_entitled_permission("communication_templates.update")
_require_publish = require_entitled_permission("communication_templates.publish")
_require_delete = require_entitled_permission("communication_templates.delete")


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, RbacError):
        return HTTPException(
            status_code=403, detail={"code": exc.code, "message": str(exc)}
        )
    if isinstance(exc, CommunicationTemplateError):
        status = 404 if exc.code.endswith("_not_found") else 400
        return HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        )
    return HTTPException(
        status_code=500, detail={"code": "internal", "message": "Internal error"}
    )


def _actor(user: CurrentUser) -> str:
    return user.email or str(user.user_id)


class TemplateUpdateBody(BaseModel):
    model_config = {"extra": "forbid"}
    name: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    subject_template: str | None = Field(default=None, max_length=200)
    body_template: str | None = Field(default=None, max_length=4000)
    publish: bool = False


class TemplateValidateBody(BaseModel):
    model_config = {"extra": "forbid"}
    subject_template: str | None = Field(default=None, max_length=200)
    body_template: str | None = Field(default=None, max_length=4000)


@router.get("/communication-templates")
def list_templates(
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    channel: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    try:
        items = CommunicationTemplateService(session).list(
            user.tenant_id, channel=channel, status=status
        )
        return {"items": items}
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/communication-templates/variables")
def variable_catalog(
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    template_key: str | None = None,
) -> dict[str, Any]:
    try:
        return CommunicationTemplateService(session).variable_catalog(template_key)
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/communication-templates/{template_id}")
def get_template(
    template_id: UUID,
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "template": CommunicationTemplateService(session).get(
                user.tenant_id, template_id
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.patch("/communication-templates/{template_id}")
def update_template(
    template_id: UUID,
    body: TemplateUpdateBody,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        data = CommunicationTemplateService(session).update(
            user.tenant_id,
            template_id,
            actor=_actor(user),
            name=body.name,
            description=body.description,
            subject_template=body.subject_template,
            body_template=body.body_template,
            publish=body.publish,
        )
        return {"template": data}
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/communication-templates/{template_id}/validate")
def validate_template(
    template_id: UUID,
    body: TemplateValidateBody,
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return CommunicationTemplateService(session).validate(
            user.tenant_id,
            template_id,
            body=body.body_template,
            subject=body.subject_template,
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/communication-templates/{template_id}/preview")
def preview_template(
    template_id: UUID,
    body: TemplateValidateBody,
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return CommunicationTemplateService(session).preview(
            user.tenant_id,
            template_id,
            body=body.body_template,
            subject=body.subject_template,
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/communication-templates/{template_id}/publish")
def publish_template(
    template_id: UUID,
    user: CurrentUser = Depends(_require_publish),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        data = CommunicationTemplateService(session).publish(
            user.tenant_id, template_id, actor=_actor(user)
        )
        return {"template": data}
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/communication-templates/{template_id}/archive")
def archive_template(
    template_id: UUID,
    user: CurrentUser = Depends(_require_delete),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        data = CommunicationTemplateService(session).archive(
            user.tenant_id, template_id, actor=_actor(user)
        )
        return {"template": data}
    except Exception as exc:
        raise _http(exc) from exc

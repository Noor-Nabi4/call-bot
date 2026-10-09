"""Business profile, model, industry templates, and CRM configuration APIs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from callbot_platform.api.deps import CurrentUser, db_dep, require_permission
from callbot_platform.business_config import (
    list_business_models,
    list_business_sizes,
    list_industries,
)
from callbot_platform.crm_config import CrmSetupError, CrmSetupService
from callbot_platform.crm_templates import (
    get_template,
    list_templates,
    resolve_template,
    serialize_template,
)
from callbot_platform.onboarding import OnboardingService
from callbot_platform.organization import OrganizationError, OrganizationService

router = APIRouter(prefix="/api/admin/organization", tags=["business-configuration"])

_require_org_read = require_permission(
    "organization.read", allow_incomplete_onboarding=True
)
_require_org_update = require_permission(
    "organization.update", allow_incomplete_onboarding=True
)


class BusinessProfileBody(BaseModel):
    model_config = {"extra": "forbid"}

    business_name: str | None = Field(default=None, max_length=255)
    industry: str | None = Field(default=None, max_length=64)
    country: str | None = Field(default=None, max_length=2)
    state: str | None = Field(default=None, max_length=128)
    timezone: str | None = Field(default=None, max_length=64)
    currency: str | None = Field(default=None, max_length=3)
    website: str | None = Field(default=None, max_length=2048)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=255)
    business_size: str | None = Field(default=None, max_length=32)
    business_type: str | None = Field(default=None, max_length=64)
    complete_steps: list[str] | None = None


class BusinessModelBody(BaseModel):
    model_config = {"extra": "forbid"}

    business_model: str = Field(min_length=1, max_length=64)


def _org_http(exc: OrganizationError) -> HTTPException:
    status = 400
    if exc.code == "not_found":
        status = 404
    return HTTPException(
        status_code=status, detail={"code": exc.code, "message": str(exc)}
    )


def _crm_http(exc: CrmSetupError) -> HTTPException:
    return HTTPException(
        status_code=400, detail={"code": exc.code, "message": str(exc)}
    )


def _as_profile(org: dict[str, Any]) -> dict[str, Any]:
    return {
        "business_name": org.get("name"),
        "industry": org.get("industry_key") or org.get("industry"),
        "country": org.get("country"),
        "state": org.get("state"),
        "timezone": org.get("timezone"),
        "currency": org.get("currency"),
        "website": org.get("website"),
        "phone": org.get("phone"),
        "email": org.get("email"),
        "business_size": org.get("business_size"),
        "business_type": org.get("business_type"),
        "business_model": org.get("business_type"),
    }


@router.get("/business-profile")
def get_business_profile(
    user: CurrentUser = Depends(_require_org_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        org = OrganizationService(session).get(user.tenant_id)
        return {
            "profile": _as_profile(org),
            "catalogs": {
                "industries": list_industries(),
                "business_models": list_business_models(),
                "business_sizes": list_business_sizes(),
            },
        }
    except OrganizationError as exc:
        raise _org_http(exc) from exc


@router.patch("/business-profile")
def patch_business_profile(
    body: BusinessProfileBody,
    user: CurrentUser = Depends(_require_org_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    fields = body.model_dump(exclude_unset=True)
    complete_steps = fields.pop("complete_steps", None)
    mapped: dict[str, Any] = {}
    if "business_name" in fields:
        mapped["name"] = fields["business_name"]
    if "industry" in fields:
        mapped["industry"] = fields["industry"]
    for key in (
        "country",
        "state",
        "timezone",
        "currency",
        "website",
        "phone",
        "email",
        "business_size",
        "business_type",
    ):
        if key in fields:
            mapped[key] = fields[key]
    try:
        if mapped:
            org = OrganizationService(session).update(
                user.tenant_id, actor=user.email, **mapped
            )
        else:
            org = OrganizationService(session).get(user.tenant_id)
        onboarding = None
        if complete_steps:
            svc = OnboardingService(session)
            for step in complete_steps:
                onboarding = svc.complete_step(user.tenant_id, step, actor=user.email)
        return {
            "profile": _as_profile(org),
            "onboarding": onboarding,
        }
    except OrganizationError as exc:
        raise _org_http(exc) from exc


@router.get("/business-model")
def get_business_model(
    user: CurrentUser = Depends(_require_org_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        org = OrganizationService(session).get(user.tenant_id)
        return {
            "business_model": org.get("business_type"),
            "options": list_business_models(),
        }
    except OrganizationError as exc:
        raise _org_http(exc) from exc


@router.put("/business-model")
def put_business_model(
    body: BusinessModelBody,
    user: CurrentUser = Depends(_require_org_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        org = OrganizationService(session).update(
            user.tenant_id,
            actor=user.email,
            business_type=body.business_model,
        )
        onboarding = OnboardingService(session).complete_step(
            user.tenant_id, "business_model", actor=user.email
        )
        return {
            "business_model": org.get("business_type"),
            "onboarding": onboarding,
        }
    except OrganizationError as exc:
        raise _org_http(exc) from exc


@router.get("/industry-templates")
def get_industry_templates(
    user: CurrentUser = Depends(_require_org_read),  # noqa: B008
) -> dict[str, Any]:
    _ = user
    return {"templates": list_templates(), "industries": list_industries()}


@router.get("/industry-templates/{template_key}")
def get_industry_template(
    template_key: str,
    user: CurrentUser = Depends(_require_org_read),  # noqa: B008
) -> dict[str, Any]:
    _ = user
    tmpl = get_template(template_key)
    if tmpl is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Template not found"},
        )
    return {"template": serialize_template(tmpl)}


@router.get("/crm-configuration")
def get_crm_configuration(
    user: CurrentUser = Depends(_require_org_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    cfg = CrmSetupService(session).get(user.tenant_id)
    org = OrganizationService(session).get(user.tenant_id)
    preview = serialize_template(
        resolve_template(
            industry_key=org.get("industry_key"),
            business_model=org.get("business_type"),
        )
    )
    return {"configuration": cfg, "preview_template": preview}


@router.post("/crm-configuration/setup")
def setup_crm_configuration(
    user: CurrentUser = Depends(_require_org_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        cfg = CrmSetupService(session).setup(user.tenant_id, actor=user.email)
        return {"configuration": cfg}
    except CrmSetupError as exc:
        raise _crm_http(exc) from exc

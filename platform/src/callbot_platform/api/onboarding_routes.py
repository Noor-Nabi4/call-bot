"""Organization onboarding APIs — session-derived tenant only."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from callbot_platform.api.deps import CurrentUser, db_dep, require_permission
from callbot_platform.onboarding import OnboardingError, OnboardingService

router = APIRouter(prefix="/api/admin/organization/onboarding", tags=["onboarding"])

_require_org_read = require_permission(
    "organization.read", allow_incomplete_onboarding=True
)
_require_org_update = require_permission(
    "organization.update", allow_incomplete_onboarding=True
)


class OnboardingPatchBody(BaseModel):
    model_config = {"extra": "forbid"}

    current_step: str | None = Field(default=None, max_length=64)
    state_data: dict[str, Any] | None = None


def _http(exc: OnboardingError) -> HTTPException:
    status = 400
    if exc.code in {"not_found"}:
        status = 404
    elif exc.code in {
        "onboarding_closed",
        "invalid_transition",
        "mandatory_onboarding",
    }:
        status = 409
    elif exc.code in {
        "step_required",
        "invalid_setup_path",
        "phone_required",
        "phone_pending",
        "phone_ineligible",
        "incomplete",
        "profile_incomplete",
    }:
        status = 400
    return HTTPException(
        status_code=status,
        detail={"code": exc.code, "message": str(exc)},
    )


@router.get("")
def get_onboarding(
    user: CurrentUser = Depends(_require_org_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    return {"onboarding": OnboardingService(session).get(user.tenant_id)}


@router.patch("")
def patch_onboarding(
    body: OnboardingPatchBody,
    user: CurrentUser = Depends(_require_org_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(
            status_code=400,
            detail={"code": "empty_patch", "message": "No onboarding fields to update"},
        )
    try:
        state = OnboardingService(session).patch(
            user.tenant_id,
            actor=user.email,
            current_step=fields.get("current_step"),
            state_data=fields.get("state_data"),
        )
        return {"onboarding": state}
    except OnboardingError as exc:
        raise _http(exc) from exc


@router.post("/steps/{step}/complete")
def complete_step(
    step: str,
    user: CurrentUser = Depends(_require_org_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "onboarding": OnboardingService(session).complete_step(
                user.tenant_id, step, actor=user.email
            )
        }
    except OnboardingError as exc:
        raise _http(exc) from exc


@router.post("/steps/{step}/skip")
def skip_step(
    step: str,
    user: CurrentUser = Depends(_require_org_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "onboarding": OnboardingService(session).skip_step(
                user.tenant_id, step, actor=user.email
            )
        }
    except OnboardingError as exc:
        raise _http(exc) from exc


@router.post("/complete")
def complete_onboarding(
    user: CurrentUser = Depends(_require_org_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "onboarding": OnboardingService(session).mark_completed(
                user.tenant_id, actor=user.email
            )
        }
    except OnboardingError as exc:
        raise _http(exc) from exc


@router.post("/skip")
def skip_onboarding(
    user: CurrentUser = Depends(_require_org_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "onboarding": OnboardingService(session).mark_skipped(
                user.tenant_id, actor=user.email
            )
        }
    except OnboardingError as exc:
        raise _http(exc) from exc

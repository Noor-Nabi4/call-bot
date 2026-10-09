"""Phase 29 AI Business Setup APIs — analyze / draft / confirm."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from callbot_platform.ai_business_setup.errors import AiBusinessSetupError
from callbot_platform.ai_business_setup.schemas import (
    ConfirmRequest,
    SetupRecommendation,
)
from callbot_platform.ai_business_setup.service import AiBusinessSetupService
from callbot_platform.api.deps import (
    CurrentUser,
    db_dep,
    require_permission,
    settings_dep,
)
from callbot_platform.config import Settings

router = APIRouter(prefix="/api/admin/business-setup", tags=["business-setup"])

_require_read = require_permission(
    "business_setup.read", allow_incomplete_onboarding=True
)
_require_generate = require_permission(
    "business_setup.generate", allow_incomplete_onboarding=True
)
_require_update = require_permission(
    "business_setup.update", allow_incomplete_onboarding=True
)
_require_confirm = require_permission(
    "business_setup.confirm", allow_incomplete_onboarding=True
)


class AnalyzeBody(BaseModel):
    model_config = {"extra": "forbid"}

    description: str = Field(min_length=8, max_length=4000)
    clarification_answers: dict[str, str] = Field(default_factory=dict)


class DraftBody(BaseModel):
    model_config = {"extra": "forbid"}

    recommendation: SetupRecommendation


def _http(exc: AiBusinessSetupError) -> HTTPException:
    status = 400
    if exc.code in {"AI_PROVIDER_ERROR"}:
        status = 503
    return HTTPException(
        status_code=status, detail={"code": exc.code, "message": exc.message}
    )


@router.get("")
def get_business_setup(
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
) -> dict[str, Any]:
    return {
        "setup": AiBusinessSetupService(session, settings=settings).get_state(
            user.tenant_id
        )
    }


@router.post("/analyze")
def analyze_business(
    body: AnalyzeBody,
    user: CurrentUser = Depends(_require_generate),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        setup = AiBusinessSetupService(session, settings=settings).analyze(
            user.tenant_id,
            description=body.description,
            actor=user.email,
            clarification_answers=body.clarification_answers,
        )
        return {"setup": setup}
    except AiBusinessSetupError as exc:
        raise _http(exc) from exc


@router.put("/recommendation")
def put_recommendation(
    body: DraftBody,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        setup = AiBusinessSetupService(session, settings=settings).save_draft(
            user.tenant_id,
            recommendation=body.recommendation,
            actor=user.email,
        )
        return {"setup": setup}
    except AiBusinessSetupError as exc:
        raise _http(exc) from exc


@router.post("/confirm")
def confirm_setup(
    body: ConfirmRequest,
    user: CurrentUser = Depends(_require_confirm),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return AiBusinessSetupService(session, settings=settings).confirm(
            user.tenant_id, body=body, actor=user.email
        )
    except AiBusinessSetupError as exc:
        raise _http(exc) from exc

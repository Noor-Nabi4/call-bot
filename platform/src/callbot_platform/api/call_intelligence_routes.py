"""Call Intelligence APIs (Phase 23)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from callbot_platform.api.deps import CurrentUser, db_dep, require_entitled_permission
from callbot_platform.call_intelligence import (
    CallIntelligenceError,
    CallIntelligenceService,
)
from callbot_platform.rbac.errors import RbacError

router = APIRouter(prefix="/api/admin/crm", tags=["call-intelligence"])

_require_calls_read = require_entitled_permission("calls.read")
_require_rec_read = require_entitled_permission("calls.recordings.read")
_require_tx_read = require_entitled_permission("calls.transcripts.read")
_require_intel_read = require_entitled_permission("calls.intelligence.read")
_require_intel_manage = require_entitled_permission("calls.intelligence.manage")


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, RbacError):
        return HTTPException(
            status_code=403, detail={"code": exc.code, "message": str(exc)}
        )
    if isinstance(exc, CallIntelligenceError):
        status = (
            404 if exc.code.endswith("_not_found") or exc.code == "not_found" else 400
        )
        if exc.code in {"recording_conflict"}:
            status = 409
        return HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        )
    return HTTPException(
        status_code=500, detail={"code": "internal", "message": "Internal error"}
    )


def _actor(user: CurrentUser) -> str:
    return user.email or str(user.user_id)


@router.get("/calls/{call_id}/recording")
def get_call_recording(
    call_id: UUID,
    user: CurrentUser = Depends(_require_rec_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        svc = CallIntelligenceService(session)
        data = svc.recordings.presign_download(
            tenant_id=user.tenant_id,
            call_id=call_id,
            actor=_actor(user),
        )
        return {"recording": data}
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/calls/{call_id}/transcript")
def get_call_transcript(
    call_id: UUID,
    user: CurrentUser = Depends(_require_tx_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        data = CallIntelligenceService(session).transcripts.get_for_call(
            user.tenant_id, call_id, include_segments=True
        )
        if data is None:
            raise CallIntelligenceError("transcript_not_found", "Transcript not found")
        return {"transcript": data}
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/calls/{call_id}/intelligence")
def get_call_intelligence(
    call_id: UUID,
    user: CurrentUser = Depends(_require_intel_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        data = CallIntelligenceService(session).analysis.get_latest(
            user.tenant_id, call_id
        )
        if data is None:
            raise CallIntelligenceError(
                "intelligence_not_found", "Call intelligence not found"
            )
        return {"intelligence": data}
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/calls/{call_id}/classification")
def get_call_classification(
    call_id: UUID,
    user: CurrentUser = Depends(_require_intel_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        data = CallIntelligenceService(session).analysis.get_classification(
            user.tenant_id, call_id
        )
        if data is None:
            raise CallIntelligenceError(
                "classification_not_found", "Classification not found"
            )
        return {"classification": data}
    except Exception as exc:
        raise _http(exc) from exc


class ReanalyzeBody(BaseModel):
    model_config = {"extra": "forbid"}
    reason: str | None = Field(default=None, max_length=500)


@router.post("/calls/{call_id}/reanalyze")
def reanalyze_call(
    call_id: UUID,
    body: ReanalyzeBody | None = None,
    user: CurrentUser = Depends(_require_intel_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        result = CallIntelligenceService(session).reanalyze(
            tenant_id=user.tenant_id,
            call_id=call_id,
            actor=_actor(user),
        )
        return {"reanalyze": result}
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/call-intelligence")
def list_call_intelligence(
    user: CurrentUser = Depends(_require_intel_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    classification: str | None = Query(default=None),
    sentiment: str | None = Query(default=None),
    intent: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    try:
        return CallIntelligenceService(session).search.search(
            user.tenant_id,
            classification=classification,
            sentiment=sentiment,
            intent=intent,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/call-intelligence/search")
def search_call_intelligence(
    user: CurrentUser = Depends(_require_tx_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    q: str | None = Query(default=None, max_length=500),
    call_id: UUID | None = Query(default=None),  # noqa: B008
    customer_id: UUID | None = Query(default=None),  # noqa: B008
    speaker: str | None = Query(default=None),
    classification: str | None = Query(default=None),
    sentiment: str | None = Query(default=None),
    intent: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),  # noqa: B008
    date_to: datetime | None = Query(default=None),  # noqa: B008
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    try:
        return CallIntelligenceService(session).search.search(
            user.tenant_id,
            q=q,
            call_id=call_id,
            customer_id=customer_id,
            speaker=speaker,
            classification=classification,
            sentiment=sentiment,
            intent=intent,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        raise _http(exc) from exc

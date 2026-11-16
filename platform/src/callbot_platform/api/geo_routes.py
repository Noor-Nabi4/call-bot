"""Public read-only geo catalog routes (signup + onboarding shared source)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from callbot_platform.api.deps import db_dep
from callbot_platform.geo.service import GeoCatalogError, GeoCatalogService
from callbot_platform.security.rate_limit import (
    RateLimitExceeded,
    SlidingWindowRateLimiter,
)

router = APIRouter(prefix="/geo", tags=["geo"])

_GEO_RATE_LIMITER = SlidingWindowRateLimiter(max_requests=60, window_sec=60.0)


def _client_key(request: Request, *parts: str) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    host = forwarded or (request.client.host if request.client else "unknown")
    return "|".join((host, *parts))


def _enforce(request: Request, action: str) -> None:
    try:
        _GEO_RATE_LIMITER.check(_client_key(request, action))
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "rate_limited",
                "message": "Too many geo catalog requests",
            },
            headers={"Retry-After": str(int(exc.retry_after_sec) + 1)},
        ) from exc


def _geo_http(exc: GeoCatalogError) -> HTTPException:
    status = 404 if exc.code.startswith("unknown_") else 400
    return HTTPException(
        status_code=status, detail={"code": exc.code, "message": str(exc)}
    )


@router.get("/catalog")
def geo_catalog(
    request: Request,
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    _enforce(request, "catalog")
    return GeoCatalogService(session).catalog_payload()


@router.get("/regions")
def geo_regions(
    request: Request,
    country: str = "",
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    _enforce(request, "regions")
    try:
        return GeoCatalogService(session).regions_payload(country)
    except GeoCatalogError as exc:
        raise _geo_http(exc) from exc

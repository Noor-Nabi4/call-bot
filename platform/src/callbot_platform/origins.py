"""Canonical public origins for Call & Flow production."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, TypedDict
from urllib.parse import urlparse

if TYPE_CHECKING:
    from callbot_platform.config import Settings

PROD_WEB_ORIGIN = "https://callandflow.com"
PROD_WEB_WWW_ORIGIN = "https://www.callandflow.com"
PROD_API_ORIGIN = "https://api.callandflow.com"
PROD_API_HOST = "api.callandflow.com"

_PROD_WEB_ORIGINS = (PROD_WEB_ORIGIN, PROD_WEB_WWW_ORIGIN)

_LOCAL_WEB_ORIGINS = (
    "http://localhost:3002",
    "http://127.0.0.1:3002",
)

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


class SessionCookieParams(TypedDict):
    httponly: bool
    samesite: Literal["lax"]
    secure: bool
    path: str
    max_age: int


def _normalize_origin(origin: str) -> str:
    return origin.strip().rstrip("/")


def _is_loopback_origin(origin: str) -> bool:
    host = urlparse(origin).hostname or ""
    return host.lower() in _LOOPBACK_HOSTS


def cors_allow_origins(settings: Settings) -> list[str]:
    """Browser origins allowed to call the platform API with credentials."""
    origins: list[str] = []
    seen: set[str] = set()

    def add(origin: str) -> None:
        normalized = _normalize_origin(origin)
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        origins.append(normalized)

    for origin in settings.ops_cors_origin_list:
        add(origin)
    for origin in _PROD_WEB_ORIGINS:
        add(origin)
    if not settings.is_production:
        for origin in _LOCAL_WEB_ORIGINS:
            add(origin)
        return origins

    https_only = [
        origin
        for origin in origins
        if origin.startswith("https://") and not _is_loopback_origin(origin)
    ]
    for origin in reversed(_PROD_WEB_ORIGINS):
        if origin not in https_only:
            https_only.insert(0, origin)
    return https_only


def session_cookie_params(settings: Settings) -> SessionCookieParams:
    return {
        "httponly": True,
        "samesite": "lax",
        "secure": settings.cookie_secure,
        "path": "/",
        "max_age": settings.session_ttl_hours * 3600,
    }

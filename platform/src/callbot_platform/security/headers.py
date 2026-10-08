"""HTTP security headers for the platform API (JSON responses)."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

# API returns JSON/binary — keep CSP tight. Browser UI CSP lives in Next.js.
_API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
_PERMISSIONS = "camera=(), microphone=(), geolocation=(), payment=()"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach baseline security headers without breaking CORS or LiveKit clients."""

    def __init__(self, app: ASGIApp, *, is_production: bool = False) -> None:
        super().__init__(app)
        self._is_production = is_production

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        headers.setdefault("Permissions-Policy", _PERMISSIONS)
        headers.setdefault("Content-Security-Policy", _API_CSP)
        if self._is_production:
            headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response

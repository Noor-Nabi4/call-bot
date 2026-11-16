"""Shared HTTP helpers — rate-limit and retry classification for providers."""

from __future__ import annotations

import logging
import random
import time
from typing import Any

import httpx

from callbot_platform.integrations.constants import MAX_SYNC_RETRIES
from callbot_platform.integrations.errors import (
    AuthExpiredError,
    AuthRevokedError,
    IntegrationError,
    PermissionDeniedError,
    ProviderUnavailableError,
    RateLimitedError,
)

logger = logging.getLogger(__name__)

_TRANSIENT_STATUS = frozenset({429, 500, 502, 503, 504})
_SENSITIVE_HEADERS = frozenset(
    {"authorization", "proxy-authorization", "x-api-key", "cookie"}
)


def redact_headers(headers: dict[str, str] | httpx.Headers) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in dict(headers).items():
        if key.lower() in _SENSITIVE_HEADERS:
            out[key] = "[REDACTED]"
        else:
            out[key] = value
    return out


def parse_retry_after(response: httpx.Response) -> float | None:
    raw = response.headers.get("Retry-After") or response.headers.get("retry-after")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def classify_http_error(response: httpx.Response) -> IntegrationError:
    status = response.status_code
    if status in {401}:
        return AuthExpiredError("Provider rejected credentials")
    if status in {403}:
        return PermissionDeniedError("Provider permission denied")
    if status == 429:
        return RateLimitedError(
            "Provider rate limited", retry_after=parse_retry_after(response)
        )
    if status in _TRANSIENT_STATUS:
        return ProviderUnavailableError(f"Provider returned HTTP {status}")
    return IntegrationError(
        "INVALID_REQUEST",
        f"Provider returned HTTP {status}",
        retryable=False,
    )


def backoff_seconds(attempt: int, *, retry_after: float | None = None) -> float:
    if retry_after is not None and retry_after > 0:
        return min(retry_after, 60.0)
    base = min(2**attempt, 30)
    return base + random.uniform(0, 0.5)


def request_with_retry(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    data: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout: float = 30.0,
    max_retries: int = MAX_SYNC_RETRIES,
) -> httpx.Response:
    """Execute HTTP with exponential backoff on transient failures."""
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.request(
                    method,
                    url,
                    headers=headers,
                    data=data,
                    json=json_body,
                    params=params,
                )
            if response.status_code < 400:
                return response
            err = classify_http_error(response)
            if not err.retryable or attempt >= max_retries:
                logger.warning(
                    "integration_http_error status=%s url=%s headers=%s",
                    response.status_code,
                    url.split("?")[0],
                    redact_headers(response.request.headers),
                )
                if response.status_code == 401:
                    raise AuthExpiredError from None
                if response.status_code == 403:
                    body = (response.text or "").lower()
                    if "revok" in body:
                        raise AuthRevokedError from None
                    raise PermissionDeniedError from None
                raise err
            delay = backoff_seconds(attempt, retry_after=err.retry_after)
            time.sleep(delay)
            last_exc = err
        except httpx.TimeoutException as exc:
            last_exc = ProviderUnavailableError("Provider request timed out")
            if attempt >= max_retries:
                raise last_exc from exc
            time.sleep(backoff_seconds(attempt))
        except httpx.TransportError as exc:
            last_exc = ProviderUnavailableError("Provider network error")
            if attempt >= max_retries:
                raise last_exc from exc
            time.sleep(backoff_seconds(attempt))
    if isinstance(last_exc, IntegrationError):
        raise last_exc
    raise ProviderUnavailableError("Provider request failed")

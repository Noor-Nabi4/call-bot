"""Outbound HTTPS webhooks for automation integrations.

SSRF-hardened: HTTPS only, no private/link-local/loopback destinations.
Optional HMAC-SHA256 signature header when a shared secret is configured.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import socket
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

_MAX_URL = 2048
_MAX_SECRET = 256
_DEFAULT_TIMEOUT_SEC = 5.0
_MAX_TIMEOUT_SEC = 15.0


class WebhookError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def normalize_webhook_config(config: dict[str, Any] | None) -> dict[str, Any]:
    """Validate and normalize post_webhook action config."""
    raw = dict(config or {})
    url = str(raw.get("url") or "").strip()
    if not url:
        raise WebhookError("invalid_webhook_url", "Webhook URL is required")
    if len(url) > _MAX_URL:
        raise WebhookError("invalid_webhook_url", "Webhook URL is too long")
    validate_webhook_url(url)

    secret_raw = raw.get("secret")
    secret: str | None = None
    if secret_raw is not None:
        secret = str(secret_raw).strip() or None
        if secret and len(secret) > _MAX_SECRET:
            raise WebhookError("invalid_webhook_secret", "Webhook secret is too long")

    timeout = raw.get("timeout_sec", _DEFAULT_TIMEOUT_SEC)
    try:
        timeout_sec = float(timeout)
    except (TypeError, ValueError) as exc:
        raise WebhookError(
            "invalid_webhook_timeout", "timeout_sec must be a number"
        ) from exc
    if timeout_sec < 1 or timeout_sec > _MAX_TIMEOUT_SEC:
        raise WebhookError(
            "invalid_webhook_timeout",
            f"timeout_sec must be between 1 and {_MAX_TIMEOUT_SEC}",
        )

    return {
        "url": url,
        "secret": secret,
        "timeout_sec": timeout_sec,
    }


def validate_webhook_url(url: str) -> None:
    """Reject non-HTTPS and destinations that resolve to private networks."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise WebhookError("invalid_webhook_url", "Webhook URL must use HTTPS")
    host = (parsed.hostname or "").strip().lower()
    if not host:
        raise WebhookError("invalid_webhook_url", "Webhook URL host is required")
    if host in {"localhost", "metadata.google.internal"}:
        raise WebhookError("invalid_webhook_url", "Webhook URL host is not allowed")
    if host.endswith(".localhost") or host.endswith(".local"):
        raise WebhookError("invalid_webhook_url", "Webhook URL host is not allowed")

    try:
        infos = socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise WebhookError(
            "invalid_webhook_url", f"Webhook host could not be resolved: {host}"
        ) from exc
    if not infos:
        raise WebhookError(
            "invalid_webhook_url", f"Webhook host could not be resolved: {host}"
        )
    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise WebhookError(
                "invalid_webhook_url",
                "Webhook URL must not target private or reserved networks",
            )


def deliver_webhook(
    *,
    url: str,
    payload: dict[str, Any],
    secret: str | None = None,
    timeout_sec: float = _DEFAULT_TIMEOUT_SEC,
    event: str,
    tenant_id: str,
    rule_id: str,
) -> dict[str, Any]:
    """POST JSON payload to the tenant webhook URL. Raises WebhookError on failure."""
    validate_webhook_url(url)
    body_obj = {
        "event": event,
        "tenant_id": tenant_id,
        "rule_id": rule_id,
        "payload": payload,
    }
    body = json.dumps(body_obj, separators=(",", ":"), default=str).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "CallAndFlow-Webhook/1.0",
        "X-CallAndFlow-Event": event,
        "X-CallAndFlow-Tenant-Id": tenant_id,
        # Legacy aliases for existing webhook receivers
        "X-VoxPilot-Event": event,
        "X-VoxPilot-Tenant-Id": tenant_id,
        "X-Callbot-Event": event,
        "X-Callbot-Tenant-Id": tenant_id,
    }
    if secret:
        digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        signature = f"sha256={digest}"
        headers["X-CallAndFlow-Signature"] = signature
        headers["X-VoxPilot-Signature"] = signature
        headers["X-Callbot-Signature"] = signature

    try:
        with httpx.Client(timeout=timeout_sec, follow_redirects=False) as client:
            response = client.post(url, content=body, headers=headers)
    except httpx.HTTPError as exc:
        logger.warning(
            "webhook_delivery_failed",
            extra={"url_host": urlparse(url).hostname, "error": type(exc).__name__},
        )
        raise WebhookError(
            "webhook_delivery_failed", "Webhook delivery failed"
        ) from exc

    if response.status_code >= 400:
        raise WebhookError(
            "webhook_rejected",
            f"Webhook endpoint returned HTTP {response.status_code}",
        )
    return {"status_code": response.status_code}

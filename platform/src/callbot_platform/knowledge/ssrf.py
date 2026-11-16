"""SSRF-safe URL validation for website knowledge ingestion."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from callbot_platform.knowledge.repos import KnowledgeError

_BLOCKED_HOSTS = frozenset(
    {
        "localhost",
        "metadata.google.internal",
        "metadata.google.com",
        "metadata",
    }
)


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def validate_public_http_url(url: str, *, max_length: int = 2048) -> str:
    raw = (url or "").strip()
    if not raw or len(raw) > max_length:
        raise KnowledgeError("invalid_url", "URL missing or too long")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        raise KnowledgeError("invalid_url", "Only http/https URLs are allowed")
    if not parsed.hostname:
        raise KnowledgeError("invalid_url", "URL host is required")
    host = parsed.hostname.lower().rstrip(".")
    if host in _BLOCKED_HOSTS or host.endswith(".local") or host.endswith(".internal"):
        raise KnowledgeError("ssrf_blocked", "URL host is not allowed")
    # Block literal IPs in private ranges.
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None and _is_blocked_ip(ip):
        raise KnowledgeError("ssrf_blocked", "URL resolves to a blocked address")
    return raw


def assert_resolved_public(hostname: str) -> None:
    host = (hostname or "").lower().rstrip(".")
    if host in _BLOCKED_HOSTS:
        raise KnowledgeError("ssrf_blocked", "URL host is not allowed")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise KnowledgeError("invalid_url", "Unable to resolve URL host") from exc
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if _is_blocked_ip(ip):
            raise KnowledgeError("ssrf_blocked", "URL resolves to a blocked address")

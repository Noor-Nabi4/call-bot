"""API key generation and hashing (SHA-256; plaintext returned once)."""

from __future__ import annotations

import hashlib
import secrets
from typing import Final

KEY_PREFIX: Final[str] = "cbk_"
VALID_SCOPES: Final[frozenset[str]] = frozenset(
    {
        "customers:read",
        "calls:read",
    }
)


def generate_api_key() -> tuple[str, str, str]:
    """Return (plaintext, prefix, sha256_hex)."""
    secret = secrets.token_urlsafe(32)
    plaintext = f"{KEY_PREFIX}{secret}"
    prefix = plaintext[:12]
    return plaintext, prefix, hash_api_key(plaintext)


def hash_api_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def normalize_scopes(scopes: list[str] | None) -> list[str]:
    if not scopes:
        return sorted(VALID_SCOPES)
    cleaned = sorted({s.strip() for s in scopes if s and s.strip()})
    unknown = [s for s in cleaned if s not in VALID_SCOPES]
    if unknown:
        raise ValueError(f"Unsupported scopes: {unknown}")
    if not cleaned:
        raise ValueError("At least one scope is required")
    return cleaned

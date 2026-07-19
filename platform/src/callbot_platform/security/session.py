"""Password hashing and session JWT helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import bcrypt
import jwt

from callbot_platform.config import Settings

ROLE_ADMIN = "admin"
ROLE_DISPATCHER = "dispatcher"
ROLE_TECHNICIAN = "technician"
VALID_ROLES = frozenset({ROLE_ADMIN, ROLE_DISPATCHER, ROLE_TECHNICIAN})
OPS_ROLES = frozenset({ROLE_ADMIN, ROLE_DISPATCHER})


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False


def create_session_token(
    *,
    settings: Settings,
    user_id: UUID,
    tenant_id: UUID,
    role: str,
    email: str,
) -> str:
    secret = settings.session_secret
    if not secret:
        raise ValueError("SESSION_SECRET is required")
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": role,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=settings.session_ttl_hours)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_session_token(token: str, *, settings: Settings) -> dict[str, Any]:
    secret = settings.session_secret
    if not secret:
        raise ValueError("SESSION_SECRET is required")
    return jwt.decode(token, secret, algorithms=["HS256"])

"""Scheduling domain errors and shared helpers."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime


class SchedulingError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def confirmation_code() -> str:
    return f"APT-{secrets.token_hex(3).upper()}"


def ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)

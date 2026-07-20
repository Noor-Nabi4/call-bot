"""CRM domain errors and shared helpers."""

from __future__ import annotations

import secrets
from typing import Any


class CrmError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def ref_code() -> str:
    return f"JB-{secrets.token_hex(3).upper()}"


def as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        item = value.strip()
        return [item] if item else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []

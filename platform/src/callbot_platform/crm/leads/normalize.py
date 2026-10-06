"""Lead field normalization and catalog validation."""

from __future__ import annotations

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.leads.constants import (
    DEFAULT_LEAD_PRIORITY,
    DEFAULT_LEAD_SOURCE,
    DEFAULT_LEAD_STATUS,
    LEAD_PRIORITIES,
    LEAD_SOURCES,
    LEAD_STATUSES,
    URGENCY_TO_PRIORITY,
)


def _trim(value: str | None, *, max_len: int, field: str) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > max_len:
        raise CrmError(f"invalid_{field}", f"{field} is too long")
    return cleaned


def require_title(title: str | None) -> str:
    cleaned = _trim(title, max_len=255, field="title")
    if not cleaned:
        raise CrmError("invalid_title", "title is required")
    return cleaned


def normalize_status(value: str | None, *, default: str = DEFAULT_LEAD_STATUS) -> str:
    if value is None or not str(value).strip():
        return default
    normalized = str(value).strip().upper()
    if normalized not in LEAD_STATUSES:
        raise CrmError("invalid_status", f"Invalid lead status: {value}")
    return normalized


def normalize_priority(
    value: str | None, *, default: str = DEFAULT_LEAD_PRIORITY
) -> str:
    if value is None or not str(value).strip():
        return default
    normalized = str(value).strip().upper()
    if normalized not in LEAD_PRIORITIES:
        raise CrmError("invalid_priority", f"Invalid lead priority: {value}")
    return normalized


def normalize_source(value: str | None, *, default: str = DEFAULT_LEAD_SOURCE) -> str:
    if value is None or not str(value).strip():
        return default
    normalized = str(value).strip().upper()
    if normalized not in LEAD_SOURCES:
        raise CrmError("invalid_source", f"Invalid lead source: {value}")
    return normalized


def priority_from_urgency(urgency: str | None) -> str:
    key = (urgency or "normal").strip().lower()
    return URGENCY_TO_PRIORITY.get(key, DEFAULT_LEAD_PRIORITY)


def normalize_prospect_email(value: str | None) -> str | None:
    return _trim(value, max_len=255, field="prospect_email")


def normalize_prospect_name(value: str | None) -> str | None:
    return _trim(value, max_len=255, field="prospect_name")


def normalize_prospect_phone(value: str | None) -> str | None:
    return _trim(value, max_len=32, field="prospect_phone")


def normalize_description(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None

"""Shared helpers for services/pricebook money, codes, and effective dates."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.products.normalize import (
    escape_like,
    money_to_str,
    parse_money,
    parse_tax_rate,
    slugify,
)
from callbot_platform.crm.services.constants import (
    CATALOG_STATUSES,
    COMPONENT_TYPES,
    DEFAULT_PRICING_TYPE,
    DEFAULT_STATUS,
    PRICING_TYPES,
)

_CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

__all__ = [
    "escape_like",
    "money_to_str",
    "normalize_code",
    "normalize_component_type",
    "normalize_pricing_type",
    "normalize_status",
    "parse_effective_range",
    "parse_money",
    "parse_positive_decimal",
    "parse_tax_rate",
    "ranges_overlap",
    "slugify",
    "trim",
]


def trim(value: str | None, *, max_len: int, field: str) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > max_len:
        raise CrmError(f"invalid_{field}", f"{field} is too long")
    return cleaned


def normalize_status(value: str | None, *, default: str = DEFAULT_STATUS) -> str:
    if value is None or not str(value).strip():
        return default
    status = str(value).strip().upper()
    if status not in CATALOG_STATUSES:
        raise CrmError("invalid_status", "Status must be ACTIVE or INACTIVE")
    return status


def normalize_pricing_type(
    value: str | None, *, default: str = DEFAULT_PRICING_TYPE
) -> str:
    if value is None or not str(value).strip():
        return default
    pricing = str(value).strip().upper()
    if pricing not in PRICING_TYPES:
        raise CrmError(
            "invalid_pricing_type",
            "pricing_type must be FIXED, STARTING_AT, HOURLY, or CUSTOM_QUOTE",
        )
    return pricing


def normalize_component_type(value: str) -> str:
    cleaned = value.strip().upper()
    if cleaned not in COMPONENT_TYPES:
        raise CrmError(
            "invalid_component_type",
            "component_type must be LABOR or MATERIAL",
        )
    return cleaned


def normalize_code(
    value: str | None, *, required: bool = False
) -> tuple[str | None, str | None]:
    """Return (display_code, code_normalized). Matching is case-insensitive."""
    if value is None:
        if required:
            raise CrmError("invalid_code", "Service code is required")
        return None, None
    cleaned = value.strip()
    if not cleaned:
        if required:
            raise CrmError("invalid_code", "Service code is required")
        return None, None
    if len(cleaned) > 64:
        raise CrmError("invalid_code", "Service code is too long")
    if not _CODE_RE.match(cleaned):
        raise CrmError(
            "invalid_code",
            "Code may contain letters, digits, '.', '_', '-' "
            "and must start alphanumerically",
        )
    return cleaned, cleaned.upper()


def parse_positive_decimal(value: object | None, *, field: str) -> Decimal | None:
    num = parse_money(value, field=field)
    if num is None:
        return None
    if num <= 0:
        raise CrmError(f"invalid_{field}", f"{field} must be positive")
    return num


def parse_effective_range(
    effective_from: datetime | str | None,
    effective_until: datetime | str | None,
) -> tuple[datetime | None, datetime | None]:
    start = _parse_dt(effective_from, field="effective_from")
    end = _parse_dt(effective_until, field="effective_until")
    if start is not None and end is not None and end < start:
        raise CrmError(
            "invalid_effective_range",
            "effective_until must not precede effective_from",
        )
    return start, end


def _parse_dt(value: datetime | str | None, *, field: str) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise CrmError(f"invalid_{field}", f"Invalid {field}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def ranges_overlap(
    a_from: datetime | None,
    a_until: datetime | None,
    b_from: datetime | None,
    b_until: datetime | None,
) -> bool:
    """Inclusive [from, until] overlap; None start/end = unbounded.

    Adjacent non-touching ranges do not overlap, e.g.:
      [2027-01-01, 2027-06-30] and [2027-07-01, 2027-12-31]
    Touching at the same instant does overlap (inclusive endpoints), e.g.:
      [..., 2027-06-30T00:00:00Z] and [2027-06-30T00:00:00Z, ...]
    """
    a_start = (
        _as_utc(a_from) if a_from is not None else datetime.min.replace(tzinfo=UTC)
    )
    a_end = (
        _as_utc(a_until) if a_until is not None else datetime.max.replace(tzinfo=UTC)
    )
    b_start = (
        _as_utc(b_from) if b_from is not None else datetime.min.replace(tzinfo=UTC)
    )
    b_end = (
        _as_utc(b_until) if b_until is not None else datetime.max.replace(tzinfo=UTC)
    )
    return a_start <= b_end and b_start <= a_end


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def is_effective_at(
    *,
    at: datetime,
    effective_from: datetime | None,
    effective_until: datetime | None,
) -> bool:
    at_utc = _as_utc(at)
    if effective_from is not None and at_utc < _as_utc(effective_from):
        return False
    return not (effective_until is not None and at_utc > _as_utc(effective_until))

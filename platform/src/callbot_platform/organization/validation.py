"""Validation for tenant organization profile fields."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from callbot_platform.db.models.tenant import Tenant
from callbot_platform.domain.phone import PhoneNumberError, normalize_e164
from callbot_platform.organization.errors import OrganizationError

BUSINESS_TYPES = frozenset(
    {
        "products",
        "services",
        "products_and_services",
        "subscriptions",
        "appointments",
        "rentals",
        "custom",
    }
)

# Active ISO 4217 alphabetic codes commonly used for SaaS settlement.
CURRENCIES = frozenset(
    {
        "AED",
        "ARS",
        "AUD",
        "BDT",
        "BGN",
        "BHD",
        "BRL",
        "CAD",
        "CHF",
        "CLP",
        "CNY",
        "COP",
        "CZK",
        "DKK",
        "EGP",
        "EUR",
        "GBP",
        "HKD",
        "HUF",
        "IDR",
        "ILS",
        "INR",
        "JPY",
        "KES",
        "KRW",
        "KWD",
        "MXN",
        "MYR",
        "NGN",
        "NOK",
        "NZD",
        "OMR",
        "PEN",
        "PHP",
        "PKR",
        "PLN",
        "QAR",
        "RON",
        "SAR",
        "SEK",
        "SGD",
        "THB",
        "TRY",
        "TWD",
        "UAH",
        "USD",
        "VND",
        "ZAR",
    }
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_COUNTRY_RE = re.compile(r"^[A-Z]{2}$")
_INDUSTRY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def _optional_str(value: str | None, *, max_length: int) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > max_length:
        raise OrganizationError(
            "invalid_value", f"Value exceeds {max_length} characters"
        )
    return cleaned


def validate_name(value: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise OrganizationError("invalid_name", "Business name is required")
    if len(cleaned) > 255:
        raise OrganizationError("invalid_name", "Business name is too long")
    return cleaned


def validate_timezone(value: str) -> str:
    cleaned = (value or "").strip() or "UTC"
    if len(cleaned) > 64:
        raise OrganizationError("invalid_timezone", "Timezone is too long")
    try:
        ZoneInfo(cleaned)
    except (ZoneInfoNotFoundError, KeyError, ValueError) as exc:
        raise OrganizationError(
            "invalid_timezone", f"Unknown timezone: {cleaned}"
        ) from exc
    return cleaned


def validate_industry(value: str | None) -> str | None:
    cleaned = _optional_str(value, max_length=64)
    if cleaned is None:
        return None
    from callbot_platform.business_config.industries import (
        INDUSTRY_KEYS,
        normalize_industry_key,
    )

    key = normalize_industry_key(cleaned)
    if key not in INDUSTRY_KEYS:
        raise OrganizationError(
            "invalid_industry",
            "Industry must be a supported industry key",
        )
    return key


def validate_business_size(value: str | None) -> str | None:
    cleaned = _optional_str(value, max_length=32)
    if cleaned is None:
        return None
    from callbot_platform.business_config.sizes import BUSINESS_SIZE_KEYS

    key = cleaned.lower().replace(" ", "_").replace("-", "_")
    if key not in BUSINESS_SIZE_KEYS:
        raise OrganizationError(
            "invalid_business_size",
            "Business size must be one of: " + ", ".join(sorted(BUSINESS_SIZE_KEYS)),
        )
    return key


def validate_business_type(value: str | None) -> str | None:
    cleaned = _optional_str(value, max_length=64)
    if cleaned is None:
        return None
    key = cleaned.strip().lower().replace(" ", "_").replace("-", "_")
    if key == "products_services":
        key = "products_and_services"
    if key not in BUSINESS_TYPES:
        raise OrganizationError(
            "invalid_business_type",
            "Business type must be one of: " + ", ".join(sorted(BUSINESS_TYPES)),
        )
    return key


def _geo_currency_codes() -> frozenset[str]:
    """Prefer seeded geo catalog codes; fall back to the legacy allowlist."""
    try:
        from callbot_platform.geo.seed_data import currency_codes_from_seed

        return currency_codes_from_seed()
    except Exception:
        return CURRENCIES


def _geo_country_codes() -> frozenset[str] | None:
    try:
        from callbot_platform.geo.seed_data import country_codes_from_seed

        return country_codes_from_seed()
    except Exception:
        return None


def validate_currency(value: str | None) -> str:
    cleaned = (value or "USD").strip().upper()
    allowed = _geo_currency_codes()
    if cleaned not in allowed:
        raise OrganizationError(
            "invalid_currency",
            "Currency must be a supported ISO 4217 code (for example USD)",
        )
    return cleaned


def validate_country(value: str | None) -> str | None:
    cleaned = _optional_str(value, max_length=2)
    if cleaned is None:
        return None
    code = cleaned.upper()
    if not _COUNTRY_RE.match(code):
        raise OrganizationError(
            "invalid_country", "Country must be an ISO 3166-1 alpha-2 code"
        )
    known = _geo_country_codes()
    if known is not None and code not in known:
        raise OrganizationError(
            "invalid_country",
            "Country must be a supported ISO 3166-1 alpha-2 code",
        )
    return code


def validate_state(value: str | None) -> str | None:
    return _optional_str(value, max_length=128)


def validate_website(value: str | None) -> str | None:
    cleaned = _optional_str(value, max_length=2048)
    if cleaned is None:
        return None
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"https", "http"}:
        raise OrganizationError("invalid_website", "Website must be an http(s) URL")
    if not parsed.netloc:
        raise OrganizationError("invalid_website", "Website host is required")
    return cleaned


def validate_phone(value: str | None) -> str | None:
    cleaned = _optional_str(value, max_length=32)
    if cleaned is None:
        return None
    try:
        return normalize_e164(cleaned)
    except PhoneNumberError as exc:
        raise OrganizationError("invalid_phone", str(exc)) from exc


def validate_email(value: str | None) -> str | None:
    cleaned = _optional_str(value, max_length=255)
    if cleaned is None:
        return None
    if not _EMAIL_RE.match(cleaned):
        raise OrganizationError("invalid_email", "Email is invalid")
    return cleaned.lower()


def serialize_organization(tenant: Tenant) -> dict[str, Any]:
    return {
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "industry": tenant.industry_key,
        "industry_key": tenant.industry_key,
        "business_type": tenant.business_type,
        "timezone": tenant.timezone,
        "currency": tenant.currency,
        "country": tenant.country,
        "state": tenant.state,
        "website": tenant.website,
        "phone": tenant.phone,
        "email": tenant.email,
        "business_size": tenant.business_size,
        "status": tenant.status,
        "default_agent_profile_id": str(tenant.default_agent_profile_id)
        if tenant.default_agent_profile_id
        else None,
        "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
        "updated_at": tenant.updated_at.isoformat() if tenant.updated_at else None,
    }

"""Field value validation and typed storage helpers."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from callbot_platform.domain.phone import PhoneNumberError, normalize_e164
from callbot_platform.dynamic_crm.errors import DynamicCrmError
from callbot_platform.dynamic_crm.types import FIELD_TYPES, normalize_field_type

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_FIELD_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_OBJECT_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_REL_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


def validate_field_key(value: str) -> str:
    key = str(value or "").strip().lower()
    if not _FIELD_KEY_RE.match(key):
        raise DynamicCrmError(
            "invalid_field_key",
            "field_key must be lowercase snake_case starting with a letter",
        )
    return key


def validate_object_key(value: str) -> str:
    key = str(value or "").strip().lower()
    if not _OBJECT_KEY_RE.match(key):
        raise DynamicCrmError(
            "invalid_object_key",
            "object_key must be lowercase snake_case starting with a letter",
        )
    return key


def validate_relationship_key(value: str) -> str:
    key = str(value or "").strip().lower()
    if not _REL_KEY_RE.match(key):
        raise DynamicCrmError(
            "invalid_relationship_key",
            "relationship_key must be lowercase snake_case starting with a letter",
        )
    return key


def _options(config: dict[str, Any]) -> list[str]:
    raw = config.get("options") or []
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw]


def validate_and_pack_value(
    field_type: str,
    value: Any,
    *,
    configuration: dict[str, Any] | None = None,
    validation_rules: dict[str, Any] | None = None,
    required: bool = False,
) -> dict[str, Any]:
    """Validate a value and return typed column payload (all other columns None)."""
    ftype = normalize_field_type(field_type)
    if ftype not in FIELD_TYPES:
        raise DynamicCrmError("invalid_field_type", f"Unknown field type: {field_type}")
    config = configuration or {}
    rules = validation_rules or {}

    empty = value is None or value == "" or value == []
    if empty:
        if required:
            raise DynamicCrmError("required", "Value is required")
        return {
            "value_text": None,
            "value_number": None,
            "value_boolean": None,
            "value_date": None,
            "value_datetime": None,
            "value_json": None,
        }

    packed: dict[str, Any] = {
        "value_text": None,
        "value_number": None,
        "value_boolean": None,
        "value_date": None,
        "value_datetime": None,
        "value_json": None,
    }

    if ftype == "TEXT":
        text = str(value).strip()
        min_len = rules.get("min_length")
        max_len = rules.get("max_length", 10_000)
        if min_len is not None and len(text) < int(min_len):
            raise DynamicCrmError("invalid_text", "Value is too short")
        if max_len is not None and len(text) > int(max_len):
            raise DynamicCrmError("invalid_text", "Value is too long")
        pattern = rules.get("pattern")
        if pattern and not re.search(str(pattern), text):
            raise DynamicCrmError("invalid_text", "Value does not match pattern")
        packed["value_text"] = text
    elif ftype == "NUMBER":
        try:
            num = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise DynamicCrmError("invalid_number", "Invalid number") from exc
        if rules.get("integer_only") and num != num.to_integral_value():
            raise DynamicCrmError("invalid_number", "Value must be an integer")
        if rules.get("min") is not None and num < Decimal(str(rules["min"])):
            raise DynamicCrmError("invalid_number", "Value is below minimum")
        if rules.get("max") is not None and num > Decimal(str(rules["max"])):
            raise DynamicCrmError("invalid_number", "Value is above maximum")
        packed["value_number"] = num
    elif ftype == "CURRENCY":
        try:
            num = Decimal(str(value)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError) as exc:
            raise DynamicCrmError(
                "invalid_currency", "Invalid currency amount"
            ) from exc
        packed["value_number"] = num
    elif ftype == "BOOLEAN":
        if isinstance(value, bool):
            packed["value_boolean"] = value
        elif str(value).strip().lower() in {"true", "1", "yes"}:
            packed["value_boolean"] = True
        elif str(value).strip().lower() in {"false", "0", "no"}:
            packed["value_boolean"] = False
        else:
            raise DynamicCrmError("invalid_boolean", "Value must be true or false")
    elif ftype == "DATE":
        if isinstance(value, date) and not isinstance(value, datetime):
            packed["value_date"] = value
        else:
            try:
                packed["value_date"] = date.fromisoformat(str(value)[:10])
            except ValueError as exc:
                raise DynamicCrmError("invalid_date", "Invalid date") from exc
    elif ftype == "DATETIME":
        if isinstance(value, datetime):
            packed["value_datetime"] = value
        else:
            try:
                packed["value_datetime"] = datetime.fromisoformat(
                    str(value).replace("Z", "+00:00")
                )
            except ValueError as exc:
                raise DynamicCrmError("invalid_datetime", "Invalid datetime") from exc
    elif ftype == "EMAIL":
        email = str(value).strip().lower()
        if not _EMAIL_RE.match(email):
            raise DynamicCrmError("invalid_email", "Invalid email address")
        packed["value_text"] = email
    elif ftype == "PHONE":
        try:
            packed["value_text"] = normalize_e164(str(value))
        except PhoneNumberError as exc:
            raise DynamicCrmError("invalid_phone", str(exc)) from exc
    elif ftype == "URL":
        url = str(value).strip()
        parsed = urlparse(url if "://" in url else f"https://{url}")
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise DynamicCrmError("invalid_url", "Invalid URL")
        packed["value_text"] = url if "://" in url else f"https://{url.lstrip('/')}"
    elif ftype == "DROPDOWN":
        choice = str(value)
        opts = _options(config)
        if opts and choice not in opts:
            raise DynamicCrmError("invalid_dropdown", "Value is not an allowed option")
        packed["value_text"] = choice
    elif ftype == "MULTI_SELECT":
        if not isinstance(value, list):
            raise DynamicCrmError("invalid_multi_select", "Value must be a list")
        opts = set(_options(config))
        selected = [str(v) for v in value]
        if opts and any(v not in opts for v in selected):
            raise DynamicCrmError(
                "invalid_multi_select", "One or more options are not allowed"
            )
        packed["value_json"] = selected
    elif ftype == "ADDRESS":
        if isinstance(value, str):
            packed["value_json"] = {"line1": value.strip()}
        elif isinstance(value, dict):
            packed["value_json"] = {
                k: value.get(k)
                for k in ("line1", "line2", "city", "state", "postal", "country")
            }
        else:
            raise DynamicCrmError("invalid_address", "Address must be an object")
    elif ftype == "FILE":
        if isinstance(value, str):
            packed["value_json"] = {"object_key": value}
        elif isinstance(value, dict) and value.get("object_key"):
            packed["value_json"] = {
                "object_key": str(value["object_key"]),
                "filename": value.get("filename"),
                "content_type": value.get("content_type"),
            }
        else:
            raise DynamicCrmError(
                "invalid_file", "File must reference an object-storage key"
            )
    elif ftype == "RELATIONSHIP":
        try:
            packed["value_text"] = str(UUID(str(value)))
        except (ValueError, TypeError) as exc:
            raise DynamicCrmError(
                "invalid_relationship", "Relationship value must be a UUID"
            ) from exc
    else:
        raise DynamicCrmError("invalid_field_type", f"Unsupported type: {ftype}")

    return packed


def unpack_value(field_type: str, row: Any) -> Any:
    ftype = normalize_field_type(field_type)
    if ftype in {"TEXT", "EMAIL", "PHONE", "URL", "DROPDOWN", "RELATIONSHIP"}:
        return row.value_text
    if ftype in {"NUMBER", "CURRENCY"}:
        return float(row.value_number) if row.value_number is not None else None
    if ftype == "BOOLEAN":
        return row.value_boolean
    if ftype == "DATE":
        return row.value_date.isoformat() if row.value_date else None
    if ftype == "DATETIME":
        return row.value_datetime.isoformat() if row.value_datetime else None
    if ftype in {"MULTI_SELECT", "ADDRESS", "FILE"}:
        return row.value_json
    return row.value_json

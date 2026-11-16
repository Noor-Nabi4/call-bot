"""E.164 phone number normalization."""

from __future__ import annotations

import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberFormat


class PhoneNumberError(ValueError):
    pass


def normalize_e164(raw: str, default_region: str | None = None) -> str:
    """Normalize to E.164.

    Uses possibility (not full carrier validity) so existing Twilio DIDs —
    including reserved test ranges — can be registered when the carrier
    already owns the number.
    """
    value = (raw or "").strip()
    if not value:
        raise PhoneNumberError("Phone number is required")
    try:
        parsed = phonenumbers.parse(value, default_region)
    except NumberParseException as exc:
        raise PhoneNumberError(f"Invalid phone number: {value}") from exc
    if not phonenumbers.is_possible_number(parsed):
        raise PhoneNumberError(f"Impossible phone number: {value}")
    return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)

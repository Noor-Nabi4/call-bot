"""E.164 phone number normalization."""

from __future__ import annotations

import re

import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberFormat


class PhoneNumberError(ValueError):
    pass


def normalize_area_code(raw: str | None, *, country: str = "US") -> str | None:
    """
    Normalize inventory area-code input for Twilio (US/CA = 3 digits).

    Accepts bare codes (\"415\") or a full number from which the NPA is extracted.
    Returns None when input is empty. Raises PhoneNumberError when invalid.
    """
    value = (raw or "").strip()
    if not value:
        return None
    digits = re.sub(r"\D+", "", value)
    country_code = (country or "US").upper()
    if country_code in {"US", "CA"}:
        if len(digits) == 3:
            return digits
        # NANP: country code 1 + 10-digit national number → NPA is first 3.
        if digits.startswith("1") and len(digits) >= 4:
            digits = digits[1:]
        if len(digits) >= 3:
            npa = digits[:3]
            if npa.isdigit() and npa[0] in "23456789":
                return npa
        raise PhoneNumberError(
            "Area code must be 3 digits (e.g. 415), not a full phone number"
        )
    if not digits.isdigit() or len(digits) < 2 or len(digits) > 5:
        raise PhoneNumberError("Area code must be 2-5 digits for this country")
    return digits


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

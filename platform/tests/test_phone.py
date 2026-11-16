"""E.164 normalization tests."""

from __future__ import annotations

import pytest

from callbot_platform.domain.phone import PhoneNumberError, normalize_e164


def test_normalize_e164_plus_format() -> None:
    assert normalize_e164("+1 (555) 123-4567") == "+15551234567"


def test_normalize_e164_with_default_region() -> None:
    assert normalize_e164("5551234567", default_region="US") == "+15551234567"


def test_normalize_rejects_invalid() -> None:
    with pytest.raises(PhoneNumberError):
        normalize_e164("not-a-number")

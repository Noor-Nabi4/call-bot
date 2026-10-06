"""Customer email normalization for search/matching."""

from __future__ import annotations

import re

from callbot_platform.crm.errors import CrmError

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(value: str | None) -> str | None:
    """Trim and lowercase for comparison. Does not rewrite provider aliases."""
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > 255:
        raise CrmError("invalid_email", "Email is too long")
    if not _EMAIL_RE.match(cleaned):
        raise CrmError("invalid_email", "Email is invalid")
    return cleaned.lower()

"""Emergency detection for handoff priority/routing."""

from __future__ import annotations

from typing import Any

from callbot_platform.human_handoff.constants import (
    EMERGENCY_CONFIDENCE_THRESHOLD,
    EMERGENCY_KEYWORDS,
)


def detect_emergency(
    *,
    text: str | None = None,
    classification: str | None = None,
    classification_confidence: float | None = None,
    explicit_emergency: bool = False,
) -> dict[str, Any]:
    """Return emergency signal. Never trusts client for tenant/permissions."""
    if explicit_emergency:
        return {"emergency": True, "source": "explicit"}
    if (classification or "").upper() == "EMERGENCY":
        conf = classification_confidence
        if conf is None or float(conf) >= EMERGENCY_CONFIDENCE_THRESHOLD:
            return {"emergency": True, "source": "classification"}
    lower = (text or "").lower()
    for kw in EMERGENCY_KEYWORDS:
        if kw in lower:
            return {"emergency": True, "source": "keyword", "keyword": kw}
    return {"emergency": False, "source": None}

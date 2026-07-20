"""Call quality review validation (post-call QA)."""

from __future__ import annotations

from typing import Any

VALID_DISPOSITIONS = frozenset(
    {
        "resolved",
        "callback",
        "transferred",
        "spam",
        "no_answer",
        "abandoned",
        "other",
    }
)

_MAX_NOTES = 2000


class CallQualityError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def validate_quality_review(
    *,
    quality_score: int | None = None,
    disposition_code: str | None = None,
    quality_notes: str | None = None,
) -> dict[str, Any]:
    """Normalize QA fields. At least one of score or disposition is required."""
    if (
        quality_score is None
        and not (disposition_code or "").strip()
        and not (quality_notes or "").strip()
    ):
        raise CallQualityError(
            "invalid_quality_review",
            "Provide a quality_score and/or disposition_code",
        )

    score: int | None = None
    if quality_score is not None:
        try:
            score = int(quality_score)
        except (TypeError, ValueError) as exc:
            raise CallQualityError(
                "invalid_quality_score", "quality_score must be an integer 1–5"
            ) from exc
        if score < 1 or score > 5:
            raise CallQualityError(
                "invalid_quality_score", "quality_score must be between 1 and 5"
            )

    disposition: str | None = None
    if disposition_code is not None:
        disposition = disposition_code.strip().lower()
        if not disposition:
            disposition = None
        elif disposition not in VALID_DISPOSITIONS:
            raise CallQualityError(
                "invalid_disposition",
                f"Unsupported disposition. Allowed: {sorted(VALID_DISPOSITIONS)}",
            )

    notes: str | None = None
    if quality_notes is not None:
        notes = quality_notes.strip()[:_MAX_NOTES] or None

    return {
        "quality_score": score,
        "disposition_code": disposition,
        "quality_notes": notes,
    }

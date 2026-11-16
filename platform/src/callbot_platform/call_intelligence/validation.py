"""Validate and sanitize AI / provider output for Call Intelligence."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from callbot_platform.call_intelligence.constants import (
    MAX_IMPORTANT_NOTES,
    MAX_NOTE_CHARS,
    MAX_OUTCOME_CHARS,
    MAX_PROBLEM_CHARS,
    SPEAKER_MAP,
    AppointmentIntelStatus,
    CallClassification,
    CallIntent,
    ClassificationSource,
    FollowUp,
    Sentiment,
    Speaker,
)
from callbot_platform.call_intelligence.errors import CallIntelligenceError

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def clamp_confidence(value: object | None) -> float | None:
    if value is None:
        return None
    try:
        conf = float(value)
    except (TypeError, ValueError) as exc:
        raise CallIntelligenceError(
            "invalid_confidence", "confidence must be numeric"
        ) from exc
    if conf < 0 or conf > 1:
        raise CallIntelligenceError(
            "invalid_confidence", "confidence must be between 0 and 1"
        )
    return conf


def map_speaker(raw: str | None) -> str:
    if not raw:
        return Speaker.UNKNOWN.value
    key = raw.strip().lower()
    if key.upper() in {s.value for s in Speaker}:
        return key.upper()
    return SPEAKER_MAP.get(key, Speaker.UNKNOWN.value)


def sanitize_text(value: object | None, *, max_len: int) -> str | None:
    if value is None:
        return None
    text = _CONTROL_CHARS.sub("", str(value)).strip()
    if not text:
        return None
    return text[:max_len]


def validate_segment(
    *,
    speaker: str | None,
    start_ms: int,
    end_ms: int,
    text: str,
    confidence: float | None,
    sequence: int,
) -> dict[str, Any]:
    if start_ms < 0 or end_ms < start_ms or sequence < 0:
        raise CallIntelligenceError(
            "invalid_segment",
            "segment timing/sequence invalid",
        )
    cleaned = sanitize_text(text, max_len=8000) or ""
    if not cleaned:
        raise CallIntelligenceError("invalid_segment", "segment text required")
    return {
        "speaker": map_speaker(speaker),
        "start_ms": int(start_ms),
        "end_ms": int(end_ms),
        "text": cleaned,
        "confidence": clamp_confidence(confidence),
        "sequence": int(sequence),
    }


def normalize_segments(raw_segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize provider segments; drop empty; preserve provider timestamps."""
    out: list[dict[str, Any]] = []
    for i, raw in enumerate(raw_segments):
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text") or "").strip()
        if not text:
            continue
        start = int(
            raw.get("start_ms")
            if raw.get("start_ms") is not None
            else raw.get("start", 0)
        )
        end = int(
            raw.get("end_ms")
            if raw.get("end_ms") is not None
            else raw.get("end", start)
        )
        seq = int(raw.get("sequence") if raw.get("sequence") is not None else i)
        conf = raw.get("confidence")
        try:
            out.append(
                validate_segment(
                    speaker=raw.get("speaker"),
                    start_ms=start,
                    end_ms=end,
                    text=text,
                    confidence=float(conf) if conf is not None else None,
                    sequence=seq,
                )
            )
        except CallIntelligenceError:
            continue
    out.sort(key=lambda s: (s["sequence"], s["start_ms"]))
    # Re-sequence densely after sort for uniqueness
    for i, seg in enumerate(out):
        seg["sequence"] = i
    return out


def _enum_or(
    value: object | None,
    allowed: type,
    *,
    default: str,
) -> str:
    if value is None:
        return default
    raw = str(value).strip().upper()
    names = {e.value for e in allowed}  # type: ignore[attr-defined]
    if raw in names:
        return raw
    return default


def sanitize_important_notes(raw: object | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        items = [raw]
    elif isinstance(raw, list):
        items = raw
    else:
        return []
    notes: list[str] = []
    for item in items:
        note = sanitize_text(item, max_len=MAX_NOTE_CHARS)
        if note:
            notes.append(note)
        if len(notes) >= MAX_IMPORTANT_NOTES:
            break
    return notes


def validate_analysis_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate structured AI analysis. Never trusts unbounded categories."""
    intent = _enum_or(raw.get("intent"), CallIntent, default=CallIntent.OTHER.value)
    classification = _enum_or(
        raw.get("classification") or raw.get("intent"),
        CallClassification,
        default=CallClassification.OTHER.value,
    )
    sentiment = _enum_or(
        raw.get("customer_sentiment") or raw.get("sentiment"),
        Sentiment,
        default=Sentiment.UNKNOWN.value,
    )
    follow_up = _enum_or(raw.get("follow_up"), FollowUp, default=FollowUp.NONE.value)
    appointment_status = _enum_or(
        raw.get("appointment_status"),
        AppointmentIntelStatus,
        default=AppointmentIntelStatus.UNKNOWN.value,
    )
    problem = sanitize_text(raw.get("problem"), max_len=MAX_PROBLEM_CHARS) or "UNKNOWN"
    outcome = sanitize_text(raw.get("outcome"), max_len=MAX_OUTCOME_CHARS) or "UNKNOWN"
    confidence = clamp_confidence(
        raw.get("classification_confidence") or raw.get("confidence")
    )
    if confidence is None:
        confidence = 0.5
    source = _enum_or(
        raw.get("classification_source") or raw.get("source"),
        ClassificationSource,
        default=ClassificationSource.AI.value,
    )
    return {
        "intent": intent,
        "problem": problem,
        "outcome": outcome,
        "sentiment": sentiment,
        "appointment_status": appointment_status,
        "follow_up": follow_up,
        "classification": classification,
        "classification_confidence": confidence,
        "classification_source": source,
        "important_notes": sanitize_important_notes(raw.get("important_notes")),
    }


def content_hash(*parts: str) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(part.encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()

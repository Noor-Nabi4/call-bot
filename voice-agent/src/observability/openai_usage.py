"""Serialize OpenAI Realtime usage for COGS estimation.

Prefer cumulative ``session.usage.model_usage`` (LiveKit session usage docs).
Fall back to accumulated per-turn RealtimeModelMetrics when session usage is empty.
"""

from __future__ import annotations

from contextlib import suppress
from typing import Any

_USAGE_INT_FIELDS: tuple[str, ...] = (
    "input_tokens",
    "input_cached_tokens",
    "input_cached_audio_tokens",
    "input_cached_text_tokens",
    "input_cached_image_tokens",
    "input_audio_tokens",
    "input_text_tokens",
    "input_image_tokens",
    "output_tokens",
    "output_audio_tokens",
    "output_text_tokens",
)


def _int_attr(obj: Any, name: str) -> int:
    value = getattr(obj, name, None)
    if value is None:
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def serialize_llm_model_usage(entry: Any) -> dict[str, Any] | None:
    """Extract token fields from an LLMModelUsage-like object."""
    provider = str(getattr(entry, "provider", "") or "").lower()
    model = str(getattr(entry, "model", "") or "")
    # Realtime / LLM entries only — skip TTS/STT summaries.
    type_name = type(entry).__name__.lower()
    if "tts" in type_name or "stt" in type_name or "interruption" in type_name:
        return None
    has_tokens = any(_int_attr(entry, f) > 0 for f in _USAGE_INT_FIELDS)
    if (
        not has_tokens
        and "llm" not in type_name
        and "realtime" not in type_name
        and provider not in {"openai", ""}
        and "realtime" not in model.lower()
    ):
        return None
    if not has_tokens and provider and provider != "openai":
        return None

    payload: dict[str, Any] = {
        "provider": provider or "openai",
        "model": model or None,
    }
    for field in _USAGE_INT_FIELDS:
        payload[field] = _int_attr(entry, field)
    session_duration = getattr(entry, "session_duration", None)
    if session_duration is not None:
        with suppress(TypeError, ValueError):
            payload["session_duration"] = float(session_duration)
    return payload


def snapshot_from_session_usage(session: Any) -> dict[str, Any] | None:
    """Read cumulative OpenAI usage from ``session.usage.model_usage``."""
    usage = getattr(session, "usage", None)
    if usage is None:
        return None
    model_usage = getattr(usage, "model_usage", None)
    if not model_usage:
        return None

    openai_entries: list[dict[str, Any]] = []
    for entry in model_usage:
        serialized = serialize_llm_model_usage(entry)
        if serialized is None:
            continue
        provider = str(serialized.get("provider") or "").lower()
        model = str(serialized.get("model") or "").lower()
        if provider == "openai" or "realtime" in model or "gpt" in model:
            openai_entries.append(serialized)

    if not openai_entries:
        return None
    if len(openai_entries) == 1:
        return openai_entries[0]
    # Merge multiple OpenAI model entries (rare) by summing token fields.
    merged: dict[str, Any] = {
        "provider": "openai",
        "model": openai_entries[0].get("model"),
    }
    for field in _USAGE_INT_FIELDS:
        merged[field] = sum(int(e.get(field) or 0) for e in openai_entries)
    return merged


def accumulate_realtime_turn(accumulator: dict[str, int], metrics: Any) -> None:
    """Add one RealtimeModelMetrics turn into an accumulator (backup path)."""
    input_tokens = _int_attr(metrics, "input_tokens")
    output_tokens = _int_attr(metrics, "output_tokens")
    total_tokens = _int_attr(metrics, "total_tokens")
    details = getattr(metrics, "input_token_details", None)
    cached = _int_attr(details, "cached_tokens") if details is not None else 0
    audio_in = _int_attr(details, "audio_tokens") if details is not None else 0
    text_in = _int_attr(details, "text_tokens") if details is not None else 0
    out_details = getattr(metrics, "output_token_details", None)
    audio_out = _int_attr(out_details, "audio_tokens") if out_details is not None else 0
    text_out = _int_attr(out_details, "text_tokens") if out_details is not None else 0

    accumulator["input_tokens"] = accumulator.get("input_tokens", 0) + input_tokens
    accumulator["output_tokens"] = accumulator.get("output_tokens", 0) + output_tokens
    accumulator["input_cached_tokens"] = (
        accumulator.get("input_cached_tokens", 0) + cached
    )
    accumulator["input_audio_tokens"] = (
        accumulator.get("input_audio_tokens", 0) + audio_in
    )
    accumulator["input_text_tokens"] = accumulator.get("input_text_tokens", 0) + text_in
    accumulator["output_audio_tokens"] = (
        accumulator.get("output_audio_tokens", 0) + audio_out
    )
    accumulator["output_text_tokens"] = (
        accumulator.get("output_text_tokens", 0) + text_out
    )
    if total_tokens and not input_tokens and not output_tokens:
        # Some payloads only expose total_tokens.
        accumulator["input_tokens"] = accumulator.get("input_tokens", 0) + total_tokens


def snapshot_from_turn_accumulator(
    accumulator: dict[str, int],
) -> dict[str, Any] | None:
    if not accumulator:
        return None
    if not any(int(v) > 0 for v in accumulator.values()):
        return None
    payload: dict[str, Any] = {"provider": "openai", "model": None}
    for field in _USAGE_INT_FIELDS:
        payload[field] = int(accumulator.get(field, 0))
    return payload

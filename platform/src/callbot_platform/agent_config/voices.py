"""Controlled OpenAI Realtime voice catalog (LiveKit Agents plugin).

Source: LiveKit OpenAI Realtime plugin defaults to ``marin``.
Voice options align with OpenAI Realtime voice identifiers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class VoiceDef:
    key: str
    display_name: str
    provider: str
    languages: tuple[str, ...]
    available: bool = True


# OpenAI Realtime voices commonly supported with gpt-realtime / LiveKit plugin.
VOICES: tuple[VoiceDef, ...] = (
    VoiceDef("marin", "Marin", "openai_realtime", ("en",), True),
    VoiceDef("cedar", "Cedar", "openai_realtime", ("en",), True),
    VoiceDef("alloy", "Alloy", "openai_realtime", ("en", "es", "fr"), True),
    VoiceDef("ash", "Ash", "openai_realtime", ("en",), True),
    VoiceDef("ballad", "Ballad", "openai_realtime", ("en",), True),
    VoiceDef("coral", "Coral", "openai_realtime", ("en", "es"), True),
    VoiceDef("echo", "Echo", "openai_realtime", ("en",), True),
    VoiceDef("sage", "Sage", "openai_realtime", ("en",), True),
    VoiceDef("shimmer", "Shimmer", "openai_realtime", ("en",), True),
    VoiceDef("verse", "Verse", "openai_realtime", ("en",), True),
)

VOICE_BY_KEY: dict[str, VoiceDef] = {v.key: v for v in VOICES}
VOICE_KEYS: frozenset[str] = frozenset(VOICE_BY_KEY)
DEFAULT_VOICE = "marin"


def list_voices() -> list[dict[str, Any]]:
    return [
        {
            "key": v.key,
            "display_name": v.display_name,
            "provider": v.provider,
            "languages": list(v.languages),
            "available": v.available,
        }
        for v in VOICES
        if v.available
    ]


def normalize_voice(raw: str | None) -> str:
    key = (raw or DEFAULT_VOICE).strip().lower()
    return key if key in VOICE_KEYS else DEFAULT_VOICE


def assert_voice(raw: str | None) -> str:
    key = (raw or "").strip().lower()
    if key not in VOICE_KEYS:
        raise ValueError(f"Unsupported voice: {raw}")
    if not VOICE_BY_KEY[key].available:
        raise ValueError(f"Voice unavailable: {key}")
    return key


def voice_supports_language(voice_key: str, language: str) -> bool:
    voice = VOICE_BY_KEY.get(voice_key)
    if voice is None:
        return False
    lang = language.strip().lower().split("-", 1)[0]
    # Catalog languages are hints; OpenAI Realtime is multilingual for most voices.
    # Only reject when catalog explicitly lists languages and lang is far outside.
    if not voice.languages:
        return True
    if lang in voice.languages or lang == "en":
        return True
    # Allow other codes — provider may still work; UI shows compatibility hint.
    return True

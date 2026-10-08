"""Controlled agent tone options."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToneDef:
    key: str
    display_name: str
    description: str


TONES: tuple[ToneDef, ...] = (
    ToneDef("professional", "Professional", "Clear, polished, business-appropriate"),
    ToneDef("friendly", "Friendly", "Warm and approachable without being casual"),
    ToneDef("warm", "Warm", "Empathetic and reassuring"),
    ToneDef("concise", "Concise", "Short answers; minimal small talk"),
    ToneDef("conversational", "Conversational", "Natural dialogue pacing"),
    ToneDef("formal", "Formal", "Reserved and precise"),
)

TONE_BY_KEY: dict[str, ToneDef] = {t.key: t for t in TONES}
TONE_KEYS: frozenset[str] = frozenset(TONE_BY_KEY)
DEFAULT_TONE = "professional"


def list_tones() -> list[dict[str, str]]:
    return [
        {
            "key": t.key,
            "display_name": t.display_name,
            "description": t.description,
        }
        for t in TONES
    ]


def normalize_tone(raw: str | None) -> str:
    key = (raw or DEFAULT_TONE).strip().lower().replace(" ", "_")
    aliases = {"casual": "conversational", "support": "warm", "sales": "friendly"}
    key = aliases.get(key, key)
    return key if key in TONE_KEYS else DEFAULT_TONE


def assert_tone(raw: str | None) -> str:
    cleaned = (raw or "").strip().lower().replace(" ", "_")
    aliases = {"casual": "conversational", "support": "warm", "sales": "friendly"}
    key = aliases.get(cleaned, cleaned)
    if key not in TONE_KEYS:
        raise ValueError(f"Unsupported tone: {raw}")
    return key

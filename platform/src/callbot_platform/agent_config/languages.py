"""Languages the voice runtime currently claims support for."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LanguageDef:
    code: str
    display_name: str


# Codes used by AgentProfile.language / supported_languages.
# Keep conservative — only languages we document as supported for prompts/routing.
LANGUAGES: tuple[LanguageDef, ...] = (
    LanguageDef("en", "English"),
    LanguageDef("es", "Spanish"),
    LanguageDef("fr", "French"),
    LanguageDef("de", "German"),
    LanguageDef("pt", "Portuguese"),
    LanguageDef("it", "Italian"),
)

LANGUAGE_BY_CODE: dict[str, LanguageDef] = {lang.code: lang for lang in LANGUAGES}
LANGUAGE_CODES: frozenset[str] = frozenset(LANGUAGE_BY_CODE)
DEFAULT_LANGUAGE = "en"


def list_languages() -> list[dict[str, str]]:
    return [
        {"code": lang.code, "display_name": lang.display_name} for lang in LANGUAGES
    ]


def normalize_language(raw: str | None) -> str:
    code = (raw or DEFAULT_LANGUAGE).strip().lower().replace("_", "-")
    base = code.split("-", 1)[0]
    return base if base in LANGUAGE_CODES else DEFAULT_LANGUAGE


def assert_language(raw: str | None) -> str:
    code = (raw or "").strip().lower().replace("_", "-")
    base = code.split("-", 1)[0]
    if base not in LANGUAGE_CODES:
        raise ValueError(f"Unsupported language: {raw}")
    return base

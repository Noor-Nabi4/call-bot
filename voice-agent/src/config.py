"""Validated environment configuration for the voice agent."""

from __future__ import annotations

import os
from dataclasses import dataclass

from prompts.business import BusinessFacts


class ConfigurationError(ValueError):
    """Raised when required configuration is missing or invalid."""


REQUIRED_ENV_VARS = (
    "LIVEKIT_URL",
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET",
    "OPENAI_API_KEY",
)


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigurationError(f"Missing required environment variable: {name}")
    return value


def _optional(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a number, got {raw!r}") from exc


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer, got {raw!r}") from exc


@dataclass(frozen=True, slots=True)
class Settings:
    """Production settings loaded from the environment."""

    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str
    openai_api_key: str
    business_name: str
    business_facts: BusinessFacts
    openai_realtime_model: str
    openai_voice: str
    temperature: float
    language: str
    user_away_timeout_sec: float
    max_call_duration_sec: float
    inactivity_check_limit: int
    inactivity_check_interval_sec: float
    max_spoken_sentences: int
    agent_name: str
    # Phase 0/1 single-tenant runtime. Multi-tenant resolution comes in Phase 2-3.
    tenant_id: str | None

    @classmethod
    def from_env(cls) -> Settings:
        temperature = _float_env("OPENAI_TEMPERATURE", 0.8)
        if not 0.6 <= temperature <= 1.2:
            raise ConfigurationError(
                "OPENAI_TEMPERATURE must be between 0.6 and 1.2 "
                "(OpenAI Realtime valid range)"
            )

        max_call_duration_sec = _float_env("MAX_CALL_DURATION_SEC", 900.0)
        if max_call_duration_sec <= 0:
            raise ConfigurationError("MAX_CALL_DURATION_SEC must be positive")

        user_away_timeout_sec = _float_env("USER_AWAY_TIMEOUT_SEC", 15.0)
        if user_away_timeout_sec <= 0:
            raise ConfigurationError("USER_AWAY_TIMEOUT_SEC must be positive")

        business_facts = BusinessFacts(
            hours=_optional("BUSINESS_HOURS"),
            service_area=_optional("BUSINESS_SERVICE_AREA"),
            phone=_optional("BUSINESS_PHONE"),
            address=_optional("BUSINESS_ADDRESS"),
            services=_optional("BUSINESS_SERVICES"),
            extra=_optional("BUSINESS_EXTRA_FACTS"),
        )

        return cls(
            livekit_url=_require("LIVEKIT_URL"),
            livekit_api_key=_require("LIVEKIT_API_KEY"),
            livekit_api_secret=_require("LIVEKIT_API_SECRET"),
            openai_api_key=_require("OPENAI_API_KEY"),
            business_name=os.getenv("BUSINESS_NAME", "our business").strip()
            or "our business",
            business_facts=business_facts,
            openai_realtime_model=os.getenv(
                "OPENAI_REALTIME_MODEL", "gpt-realtime"
            ).strip()
            or "gpt-realtime",
            openai_voice=os.getenv("OPENAI_VOICE", "marin").strip() or "marin",
            temperature=temperature,
            language=os.getenv("AGENT_LANGUAGE", "en").strip() or "en",
            user_away_timeout_sec=user_away_timeout_sec,
            max_call_duration_sec=max_call_duration_sec,
            inactivity_check_limit=_int_env("INACTIVITY_CHECK_LIMIT", 2),
            inactivity_check_interval_sec=_float_env(
                "INACTIVITY_CHECK_INTERVAL_SEC", 10.0
            ),
            max_spoken_sentences=_int_env("MAX_SPOKEN_SENTENCES", 2),
            agent_name=os.getenv("AGENT_NAME", "voice-agent").strip() or "voice-agent",
            tenant_id=_optional("TENANT_ID"),
        )


def missing_required_env_vars() -> list[str]:
    """Return required env var names that are unset or empty (never values)."""
    return [name for name in REQUIRED_ENV_VARS if not os.getenv(name, "").strip()]

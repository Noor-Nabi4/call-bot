"""Tests for validated Settings."""

from __future__ import annotations

import pytest

from config import ConfigurationError, Settings, missing_required_env_vars


def test_from_env_requires_core_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "LIVEKIT_URL",
        "LIVEKIT_API_KEY",
        "LIVEKIT_API_SECRET",
        "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(ConfigurationError, match="LIVEKIT_URL"):
        Settings.from_env()


def test_from_env_loads_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "secret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("BUSINESS_NAME", raising=False)
    monkeypatch.delenv("OPENAI_TEMPERATURE", raising=False)
    monkeypatch.delenv("OPENAI_VAD_EAGERNESS", raising=False)
    monkeypatch.delenv("OPENAI_INPUT_AUDIO_NOISE_REDUCTION", raising=False)
    monkeypatch.delenv("MIN_CONSECUTIVE_SPEECH_DELAY_SEC", raising=False)
    monkeypatch.delenv("MIN_INTERRUPTION_DURATION_SEC", raising=False)
    monkeypatch.delenv("TENANT_ID", raising=False)
    monkeypatch.delenv("BUSINESS_HOURS", raising=False)

    settings = Settings.from_env()
    assert settings.openai_realtime_model == "gpt-realtime"
    assert settings.openai_voice == "marin"
    assert settings.temperature == 0.85
    assert settings.vad_eagerness == "low"
    assert settings.input_audio_noise_reduction is None
    assert settings.min_consecutive_speech_delay_sec == 0.25
    assert settings.min_interruption_duration_sec == 0.5
    assert settings.max_call_duration_sec == 900.0
    assert settings.business_name == "our business"
    assert settings.tenant_id is None
    assert settings.business_facts.hours is None


def test_from_env_loads_business_facts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "secret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("BUSINESS_NAME", "Acme HVAC")
    monkeypatch.setenv("TENANT_ID", "tenant_demo_acme")
    monkeypatch.setenv("BUSINESS_HOURS", "Mon-Fri 8-6")
    monkeypatch.setenv("BUSINESS_SERVICES", "HVAC repair")

    settings = Settings.from_env()
    assert settings.business_name == "Acme HVAC"
    assert settings.tenant_id == "tenant_demo_acme"
    assert settings.business_facts.hours == "Mon-Fri 8-6"
    assert settings.business_facts.services == "HVAC repair"


def test_temperature_out_of_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "secret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_TEMPERATURE", "0.1")

    with pytest.raises(ConfigurationError, match="OPENAI_TEMPERATURE"):
        Settings.from_env()


def test_vad_eagerness_and_noise_reduction(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "secret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_VAD_EAGERNESS", "medium")
    monkeypatch.setenv("OPENAI_INPUT_AUDIO_NOISE_REDUCTION", "far_field")
    monkeypatch.setenv("MIN_CONSECUTIVE_SPEECH_DELAY_SEC", "0.3")
    monkeypatch.setenv("MIN_INTERRUPTION_DURATION_SEC", "0.4")

    settings = Settings.from_env()
    assert settings.vad_eagerness == "medium"
    assert settings.input_audio_noise_reduction == "far_field"
    assert settings.min_consecutive_speech_delay_sec == 0.3
    assert settings.min_interruption_duration_sec == 0.4


def test_invalid_vad_eagerness(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "secret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_VAD_EAGERNESS", "instant")

    with pytest.raises(ConfigurationError, match="OPENAI_VAD_EAGERNESS"):
        Settings.from_env()


def test_missing_required_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "secret")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert missing_required_env_vars() == ["OPENAI_API_KEY"]

"""Canonical public origins for Call & Flow production."""

from __future__ import annotations

from typing import Any

from callbot_platform.config import Settings, missing_production_settings
from callbot_platform.origins import (
    PROD_API_ORIGIN,
    PROD_WEB_ORIGIN,
    PROD_WEB_WWW_ORIGIN,
    cors_allow_origins,
    session_cookie_params,
)


def _settings(**kwargs: Any) -> Settings:
    return Settings(_env_file=None, **kwargs)


def test_unified_frontend_url_defaults() -> None:
    fields = Settings.model_fields
    assert fields["ops_cors_origins"].default == "http://localhost:3002"
    assert (
        fields["stripe_checkout_success_url"].default
        == "http://localhost:3002/settings/billing?checkout=success"
    )
    assert (
        fields["stripe_checkout_cancel_url"].default
        == "http://localhost:3002/signup?canceled=1"
    )
    assert (
        fields["stripe_portal_return_url"].default
        == "http://localhost:3002/settings/billing"
    )


def test_production_origins() -> None:
    assert PROD_WEB_ORIGIN == "https://callandflow.com"
    assert PROD_WEB_WWW_ORIGIN == "https://www.callandflow.com"
    assert PROD_API_ORIGIN == "https://api.callandflow.com"


def test_cookie_secure_in_production() -> None:
    settings = _settings(
        environment="production",
        ops_cors_origins=PROD_WEB_ORIGIN,
        session_secret="test-session-secret",
    )
    assert settings.is_production is True
    assert settings.cookie_secure is True
    assert settings.env_tenant_fallback_allowed is False
    params = session_cookie_params(settings)
    assert params["secure"] is True
    assert params["httponly"] is True
    assert params["samesite"] == "lax"


def test_cookie_secure_override() -> None:
    settings = _settings(
        environment="development",
        cookie_secure_override=True,
        session_secret="test-session-secret",
    )
    assert settings.cookie_secure is True


def test_production_cors_excludes_localhost() -> None:
    settings = _settings(
        environment="production",
        ops_cors_origins=PROD_WEB_ORIGIN,
        session_secret="test-session-secret",
    )
    origins = cors_allow_origins(settings)
    assert PROD_WEB_ORIGIN in origins
    assert PROD_WEB_WWW_ORIGIN in origins
    assert "http://localhost:3002" not in origins
    assert "http://127.0.0.1:3002" not in origins


def test_production_cors_strips_localhost_even_if_configured() -> None:
    settings = _settings(
        environment="production",
        ops_cors_origins="http://localhost:3002,https://callandflow.com",
        session_secret="test-session-secret",
    )
    origins = cors_allow_origins(settings)
    assert PROD_WEB_ORIGIN in origins
    assert PROD_WEB_WWW_ORIGIN in origins
    assert "http://localhost:3002" not in origins


def test_production_cors_keeps_extra_https_origins() -> None:
    extra = "https://preview.callandflow.com"
    settings = _settings(
        environment="production",
        ops_cors_origins=f"{PROD_WEB_ORIGIN},{extra}",
        session_secret="test-session-secret",
    )
    origins = cors_allow_origins(settings)
    assert PROD_WEB_ORIGIN in origins
    assert PROD_WEB_WWW_ORIGIN in origins
    assert extra in origins
    assert all(origin.startswith("https://") for origin in origins)


def test_production_requires_secrets_and_non_local_database() -> None:
    incomplete = _settings(
        environment="production",
        ops_cors_origins=PROD_WEB_ORIGIN,
        session_secret="test-session-secret",
        credentials_encryption_key="",
        metadata_hmac_secret="",
        internal_service_token="",
        livekit_url="",
        livekit_api_key="",
        livekit_api_secret="",
        stripe_secret_key="",
        stripe_webhook_secret="",
        database_url="postgresql+psycopg://postgres:postgres@localhost:5432/call_bot",
    )
    missing = missing_production_settings(incomplete)
    assert "credentials_encryption_key" in missing
    assert "database_url" in missing

    complete = _settings(
        environment="production",
        database_url="postgresql+psycopg://app:secret@db.internal:5432/call_bot",
        session_secret="session-secret",
        credentials_encryption_key="enc-key",
        metadata_hmac_secret="hmac-secret",
        internal_service_token="internal-token",
        livekit_url="wss://example.livekit.cloud",
        livekit_api_key="key",
        livekit_api_secret="secret",
        stripe_secret_key="sk_test_x",
        stripe_webhook_secret="whsec_x",
    )
    assert missing_production_settings(complete) == []


def test_development_cors_includes_local_and_prod_web() -> None:
    settings = _settings(
        environment="development",
        ops_cors_origins="http://localhost:3002",
        session_secret="test-session-secret",
    )
    origins = cors_allow_origins(settings)
    assert "http://localhost:3002" in origins
    assert "http://127.0.0.1:3002" in origins
    assert PROD_WEB_ORIGIN in origins
    assert PROD_WEB_WWW_ORIGIN in origins

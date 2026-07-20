"""Validated environment configuration for the platform API."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/call_bot",
        alias="DATABASE_URL",
    )
    platform_api_host: str = Field(default="0.0.0.0", alias="PLATFORM_API_HOST")
    platform_api_port: int = Field(default=8000, alias="PLATFORM_API_PORT")

    livekit_url: str = Field(default="", alias="LIVEKIT_URL")
    livekit_api_key: str = Field(default="", alias="LIVEKIT_API_KEY")
    livekit_api_secret: str = Field(default="", alias="LIVEKIT_API_SECRET")
    livekit_sip_host: str = Field(default="", alias="LIVEKIT_SIP_HOST")
    agent_name: str = Field(default="voice-agent", alias="AGENT_NAME")

    twilio_account_sid: str = Field(default="", alias="TWILIO_ACCOUNT_SID")
    twilio_auth_token: str = Field(default="", alias="TWILIO_AUTH_TOKEN")

    credentials_encryption_key: str = Field(
        default="", alias="CREDENTIALS_ENCRYPTION_KEY"
    )
    metadata_hmac_secret: str = Field(default="", alias="METADATA_HMAC_SECRET")
    internal_service_token: str = Field(default="", alias="INTERNAL_SERVICE_TOKEN")
    session_secret: str = Field(default="", alias="SESSION_SECRET")
    ops_cors_origins: str = Field(
        default="http://localhost:3001",
        alias="OPS_CORS_ORIGINS",
    )
    session_cookie_name: str = Field(
        default="callbot_ops_session", alias="SESSION_COOKIE_NAME"
    )
    session_ttl_hours: int = Field(default=72, alias="SESSION_TTL_HOURS")

    # Platform SaaS Stripe account (subscriptions). Do NOT use Stripe Connect keys here.
    # Plans live in code (billing/plans.py); Checkout uses price_data — no Stripe Products/Prices to register.
    stripe_secret_key: str = Field(default="", alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: str = Field(default="", alias="STRIPE_WEBHOOK_SECRET")
    stripe_checkout_success_url: str = Field(
        default="http://localhost:3001/settings/billing?checkout=success",
        alias="STRIPE_CHECKOUT_SUCCESS_URL",
    )
    stripe_checkout_cancel_url: str = Field(
        default="http://localhost:3002/signup?canceled=1",
        alias="STRIPE_CHECKOUT_CANCEL_URL",
    )
    stripe_portal_return_url: str = Field(
        default="http://localhost:3001/settings/billing",
        alias="STRIPE_PORTAL_RETURN_URL",
    )

    allow_env_tenant_fallback: bool = Field(
        default=True, alias="ALLOW_ENV_TENANT_FALLBACK"
    )

    @property
    def ops_cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.ops_cors_origins.split(",") if o.strip()]

    @property
    def livekit_origination_uri(self) -> str:
        host = self.livekit_sip_host.strip()
        if host.startswith("sip:"):
            return f"{host};transport=tcp"
        return f"sip:{host};transport=tcp"


@lru_cache
def get_settings() -> Settings:
    return Settings()

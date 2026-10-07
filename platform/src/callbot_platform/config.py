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
    db_pool_size: int = Field(default=5, alias="DB_POOL_SIZE", ge=1, le=100)
    db_max_overflow: int = Field(default=10, alias="DB_MAX_OVERFLOW", ge=0, le=100)
    db_pool_timeout: int = Field(default=30, alias="DB_POOL_TIMEOUT", ge=1, le=300)
    db_pool_recycle: int = Field(default=1800, alias="DB_POOL_RECYCLE", ge=60)
    db_pool_pre_ping: bool = Field(default=True, alias="DB_POOL_PRE_PING")

    outbox_batch_size: int = Field(default=20, alias="OUTBOX_BATCH_SIZE", ge=1, le=500)
    outbox_max_retries: int = Field(default=8, alias="OUTBOX_MAX_RETRIES", ge=1, le=50)
    outbox_base_backoff_seconds: float = Field(
        default=5.0, alias="OUTBOX_BASE_BACKOFF_SECONDS", ge=0.1
    )
    outbox_max_backoff_seconds: float = Field(
        default=900.0, alias="OUTBOX_MAX_BACKOFF_SECONDS", ge=1.0
    )
    outbox_poll_interval_seconds: float = Field(
        default=2.0, alias="OUTBOX_POLL_INTERVAL_SECONDS", ge=0.2
    )
    outbox_lease_seconds: float = Field(
        default=120.0, alias="OUTBOX_LEASE_SECONDS", ge=10.0
    )
    job_batch_size: int = Field(default=10, alias="JOB_BATCH_SIZE", ge=1, le=200)
    job_max_attempts: int = Field(default=8, alias="JOB_MAX_ATTEMPTS", ge=1, le=50)
    job_base_backoff_seconds: float = Field(
        default=5.0, alias="JOB_BASE_BACKOFF_SECONDS", ge=0.1
    )
    job_max_backoff_seconds: float = Field(
        default=900.0, alias="JOB_MAX_BACKOFF_SECONDS", ge=1.0
    )
    job_poll_interval_seconds: float = Field(
        default=2.0, alias="JOB_POLL_INTERVAL_SECONDS", ge=0.2
    )
    job_lease_seconds: float = Field(default=180.0, alias="JOB_LEASE_SECONDS", ge=10.0)
    job_shutdown_timeout_seconds: float = Field(
        default=30.0, alias="JOB_SHUTDOWN_TIMEOUT_SECONDS", ge=1.0
    )
    require_call_scope: bool = Field(default=False, alias="REQUIRE_CALL_SCOPE")
    call_scope_ttl_seconds: int = Field(
        default=14_400, alias="CALL_SCOPE_TTL_SECONDS", ge=60
    )
    object_storage_backend: str = Field(
        default="filesystem", alias="OBJECT_STORAGE_BACKEND"
    )
    object_storage_root: str = Field(
        default="./data/object-storage", alias="OBJECT_STORAGE_ROOT"
    )
    s3_endpoint_url: str = Field(default="", alias="S3_ENDPOINT_URL")
    s3_region: str = Field(default="us-east-1", alias="S3_REGION")
    s3_bucket: str = Field(default="", alias="S3_BUCKET")
    s3_access_key_id: str = Field(default="", alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: str = Field(default="", alias="S3_SECRET_ACCESS_KEY")
    s3_force_path_style: bool = Field(default=False, alias="S3_FORCE_PATH_STYLE")
    object_storage_max_upload_bytes: int = Field(
        default=52_428_800, alias="OBJECT_STORAGE_MAX_UPLOAD_BYTES", ge=1024
    )
    object_storage_signed_url_ttl_seconds: int = Field(
        default=300, alias="OBJECT_STORAGE_SIGNED_URL_TTL_SECONDS", ge=30
    )
    recording_retention_days: int = Field(
        default=30, alias="RECORDING_RETENTION_DAYS", ge=1, le=3650
    )
    dedicated_db_idle_seconds: int = Field(
        default=600, alias="DEDICATED_DB_IDLE_SECONDS", ge=60
    )
    health_db_timeout_seconds: float = Field(
        default=2.0, alias="HEALTH_DB_TIMEOUT_SECONDS", ge=0.2, le=30.0
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
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    knowledge_embedding_model: str = Field(
        default="text-embedding-3-small", alias="KNOWLEDGE_EMBEDDING_MODEL"
    )
    knowledge_embedding_dimension: int = Field(
        default=1536, alias="KNOWLEDGE_EMBEDDING_DIMENSION"
    )
    knowledge_embedding_version: str = Field(
        default="v1", alias="KNOWLEDGE_EMBEDDING_VERSION"
    )
    knowledge_relevance_threshold: float = Field(
        default=0.35, alias="KNOWLEDGE_RELEVANCE_THRESHOLD"
    )
    knowledge_retrieval_top_k: int = Field(
        default=5, alias="KNOWLEDGE_RETRIEVAL_TOP_K"
    )
    internal_service_token: str = Field(default="", alias="INTERNAL_SERVICE_TOKEN")
    session_secret: str = Field(default="", alias="SESSION_SECRET")
    ops_cors_origins: str = Field(
        default="http://localhost:3002",
        alias="OPS_CORS_ORIGINS",
    )
    session_cookie_name: str = Field(
        default="callbot_ops_session", alias="SESSION_COOKIE_NAME"
    )
    session_ttl_hours: int = Field(default=72, alias="SESSION_TTL_HOURS")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    cookie_secure_override: bool | None = Field(default=None, alias="COOKIE_SECURE")

    # Platform SaaS Stripe account (subscriptions). Do NOT use Stripe Connect keys here.
    # Plans live in code (billing/plans.py); Checkout uses price_data — no Stripe Products/Prices to register.
    stripe_secret_key: str = Field(default="", alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: str = Field(default="", alias="STRIPE_WEBHOOK_SECRET")
    stripe_checkout_success_url: str = Field(
        default="http://localhost:3002/settings/billing?checkout=success",
        alias="STRIPE_CHECKOUT_SUCCESS_URL",
    )
    stripe_checkout_cancel_url: str = Field(
        default="http://localhost:3002/signup?canceled=1",
        alias="STRIPE_CHECKOUT_CANCEL_URL",
    )
    stripe_portal_return_url: str = Field(
        default="http://localhost:3002/settings/billing",
        alias="STRIPE_PORTAL_RETURN_URL",
    )

    allow_env_tenant_fallback: bool = Field(
        default=True, alias="ALLOW_ENV_TENANT_FALLBACK"
    )

    # Internal voice COGS estimates (USD). Not customer billing.
    cogs_openai_per_minute_usd: float = Field(
        default=0.0676, alias="COGS_OPENAI_PER_MINUTE_USD"
    )
    cogs_openai_sensitivity_low_usd: float = Field(
        default=0.05, alias="COGS_OPENAI_SENSITIVITY_LOW_USD"
    )
    cogs_openai_sensitivity_high_usd: float = Field(
        default=0.10, alias="COGS_OPENAI_SENSITIVITY_HIGH_USD"
    )
    # Token rates per 1M tokens for gpt-realtime-class models (BYOK).
    cogs_openai_audio_input_per_1m_usd: float = Field(
        default=32.0, alias="COGS_OPENAI_AUDIO_INPUT_PER_1M_USD"
    )
    cogs_openai_audio_cached_input_per_1m_usd: float = Field(
        default=0.40, alias="COGS_OPENAI_AUDIO_CACHED_INPUT_PER_1M_USD"
    )
    cogs_openai_audio_output_per_1m_usd: float = Field(
        default=64.0, alias="COGS_OPENAI_AUDIO_OUTPUT_PER_1M_USD"
    )
    cogs_openai_text_input_per_1m_usd: float = Field(
        default=4.0, alias="COGS_OPENAI_TEXT_INPUT_PER_1M_USD"
    )
    cogs_openai_text_cached_input_per_1m_usd: float = Field(
        default=0.40, alias="COGS_OPENAI_TEXT_CACHED_INPUT_PER_1M_USD"
    )
    cogs_openai_text_output_per_1m_usd: float = Field(
        default=16.0, alias="COGS_OPENAI_TEXT_OUTPUT_PER_1M_USD"
    )
    cogs_livekit_agent_per_minute_usd: float = Field(
        default=0.01, alias="COGS_LIVEKIT_AGENT_PER_MINUTE_USD"
    )
    cogs_livekit_agent_included_minutes_monthly: int = Field(
        default=0, alias="COGS_LIVEKIT_AGENT_INCLUDED_MINUTES_MONTHLY"
    )
    cogs_livekit_plan: str = Field(default="ship", alias="COGS_LIVEKIT_PLAN")
    cogs_livekit_sip_ship_per_minute_usd: float = Field(
        default=0.004, alias="COGS_LIVEKIT_SIP_SHIP_PER_MINUTE_USD"
    )
    cogs_livekit_sip_scale_per_minute_usd: float = Field(
        default=0.003, alias="COGS_LIVEKIT_SIP_SCALE_PER_MINUTE_USD"
    )
    cogs_livekit_bvc_telephony_per_minute_usd: float = Field(
        default=0.0012, alias="COGS_LIVEKIT_BVC_TELEPHONY_PER_MINUTE_USD"
    )
    cogs_livekit_bvc_per_minute_usd: float = Field(
        default=0.0, alias="COGS_LIVEKIT_BVC_PER_MINUTE_USD"
    )
    cogs_twilio_us_local_origination_per_minute_usd: float = Field(
        default=0.0034, alias="COGS_TWILIO_US_LOCAL_ORIGINATION_PER_MINUTE_USD"
    )
    cogs_twilio_termination_per_minute_usd: float = Field(
        default=0.01, alias="COGS_TWILIO_TERMINATION_PER_MINUTE_USD"
    )
    # None / omit → use call billable_seconds for warm outbound leg estimate.
    cogs_warm_transfer_termination_seconds: int | None = Field(
        default=None, alias="COGS_WARM_TRANSFER_TERMINATION_SECONDS"
    )
    cogs_livekit_fixed_monthly_usd: float = Field(
        default=0.0, alias="COGS_LIVEKIT_FIXED_MONTHLY_USD"
    )
    cogs_phone_rental_monthly_usd: float = Field(
        default=0.0, alias="COGS_PHONE_RENTAL_MONTHLY_USD"
    )
    cogs_sms_monthly_usd: float = Field(default=0.0, alias="COGS_SMS_MONTHLY_USD")

    @property
    def ops_cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.ops_cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() in {"prod", "production"}

    @property
    def cookie_secure(self) -> bool:
        if self.cookie_secure_override is not None:
            return self.cookie_secure_override
        if self.is_production:
            return True
        return any(
            origin.startswith("https://") for origin in self.ops_cors_origin_list
        )

    @property
    def env_tenant_fallback_allowed(self) -> bool:
        if self.is_production:
            return False
        return self.allow_env_tenant_fallback

    @property
    def livekit_origination_uri(self) -> str:
        host = self.livekit_sip_host.strip()
        if host.startswith("sip:"):
            return f"{host};transport=tcp"
        return f"sip:{host};transport=tcp"


PRODUCTION_REQUIRED_FIELDS: tuple[str, ...] = (
    "session_secret",
    "credentials_encryption_key",
    "metadata_hmac_secret",
    "internal_service_token",
    "livekit_url",
    "livekit_api_key",
    "livekit_api_secret",
    "stripe_secret_key",
    "stripe_webhook_secret",
)


def missing_production_settings(settings: Settings) -> list[str]:
    missing: list[str] = []
    for field in PRODUCTION_REQUIRED_FIELDS:
        value = getattr(settings, field)
        if not str(value).strip():
            missing.append(field)
    database_url = settings.database_url.lower()
    if "localhost" in database_url or "127.0.0.1" in database_url:
        missing.append("database_url")
    if not settings.require_call_scope:
        missing.append("require_call_scope")
    return missing


def require_production_settings(settings: Settings) -> None:
    if not settings.is_production:
        return
    missing = missing_production_settings(settings)
    if missing:
        names = ", ".join(sorted(missing))
        raise RuntimeError(f"production configuration incomplete: {names}")


@lru_cache
def get_settings() -> Settings:
    return Settings()

"""Reusable OAuth state + authorization URL helpers."""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.db.models.integrations import IntegrationOauthState
from callbot_platform.integrations.constants import OAUTH_STATE_TTL_SECONDS
from callbot_platform.integrations.errors import IntegrationError
from callbot_platform.integrations.http import request_with_retry

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OAuthAppConfig:
    provider: str
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    scopes: tuple[str, ...]
    extra_auth_params: dict[str, str] | None = None


class OAuthStateService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        provider: str,
        redirect_uri: str,
    ) -> str:
        state = secrets.token_urlsafe(32)
        row = IntegrationOauthState(
            tenant_id=tenant_id,
            user_id=user_id,
            provider=provider,
            state=state,
            redirect_uri=redirect_uri,
            expires_at=datetime.now(UTC) + timedelta(seconds=OAUTH_STATE_TTL_SECONDS),
        )
        self._session.add(row)
        self._session.flush()
        return state

    def consume(
        self,
        *,
        state: str,
        provider: str,
        tenant_id: UUID,
        user_id: UUID,
    ) -> IntegrationOauthState:
        row = self._session.scalar(
            select(IntegrationOauthState)
            .where(IntegrationOauthState.state == state)
            .with_for_update()
        )
        if row is None:
            raise IntegrationError("OAUTH_STATE_INVALID", "Invalid OAuth state")
        if row.consumed_at is not None:
            raise IntegrationError("OAUTH_STATE_REUSED", "OAuth state already used")
        expires = row.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if expires < datetime.now(UTC):
            raise IntegrationError("OAUTH_STATE_EXPIRED", "OAuth state expired")
        if row.provider != provider:
            raise IntegrationError("OAUTH_STATE_MISMATCH", "Provider mismatch")
        if row.tenant_id != tenant_id or row.user_id != user_id:
            raise IntegrationError("OAUTH_STATE_MISMATCH", "Tenant/user mismatch")
        row.consumed_at = datetime.now(UTC)
        self._session.flush()
        return row


def build_authorization_url(
    config: OAuthAppConfig,
    *,
    redirect_uri: str,
    state: str,
) -> str:
    params: dict[str, str] = {
        "client_id": config.client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "state": state,
        "scope": " ".join(config.scopes),
    }
    if config.extra_auth_params:
        params.update(config.extra_auth_params)
    sep = "&" if "?" in config.authorize_url else "?"
    return f"{config.authorize_url}{sep}{urlencode(params)}"


def _normalize_token_payload(
    provider: str, payload: dict[str, Any]
) -> dict[str, Any] | None:
    if not payload.get("access_token"):
        logger.warning("oauth_token_payload_invalid provider=%s", provider)
        return None
    expires_in = payload.get("expires_in")
    expires_at: datetime | None = None
    if isinstance(expires_in, (int, float)):
        expires_at = datetime.now(UTC) + timedelta(seconds=int(expires_in))
    return {
        "access_token": str(payload["access_token"]),
        "refresh_token": (
            str(payload["refresh_token"]) if payload.get("refresh_token") else None
        ),
        "token_type": (
            str(payload["token_type"]) if payload.get("token_type") else "Bearer"
        ),
        "scope": str(payload["scope"]) if payload.get("scope") else None,
        "expires_at": expires_at,
        "external_account_id": (
            str(payload.get("realmId") or payload.get("tenant_id") or "") or None
        ),
    }


def exchange_authorization_code(
    config: OAuthAppConfig,
    *,
    code: str,
    redirect_uri: str,
) -> dict[str, Any] | None:
    """Exchange authorization code for tokens. Returns None if token_url unset."""
    if not config.token_url:
        return None
    response = request_with_retry(
        "POST",
        config.token_url,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
        },
        headers={"Accept": "application/json"},
        max_retries=2,
    )
    payload = response.json()
    if not isinstance(payload, dict):
        return None
    return _normalize_token_payload(config.provider, payload)


def refresh_access_token(
    config: OAuthAppConfig,
    *,
    refresh_token: str,
) -> dict[str, Any] | None:
    """Refresh OAuth access token. Preserves prior refresh_token if provider omits rotation."""
    if not config.token_url or not refresh_token:
        return None
    response = request_with_retry(
        "POST",
        config.token_url,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
        },
        headers={"Accept": "application/json"},
        max_retries=2,
    )
    payload = response.json()
    if not isinstance(payload, dict):
        return None
    normalized = _normalize_token_payload(config.provider, payload)
    if normalized is None:
        return None
    # Do not drop existing refresh token when provider omits a rotated value.
    if not normalized.get("refresh_token"):
        normalized["refresh_token"] = refresh_token
    return normalized


def oauth_config_from_settings(provider: str, settings: Any) -> OAuthAppConfig | None:
    """Resolve OAuth app config from Settings env fields. None = not configured."""
    mapping = {
        "google_calendar": (
            "integrations_google_client_id",
            "integrations_google_client_secret",
            "https://accounts.google.com/o/oauth2/v2/auth",
            "https://oauth2.googleapis.com/token",
            (
                "https://www.googleapis.com/auth/calendar",
                "https://www.googleapis.com/auth/calendar.events",
            ),
            {"access_type": "offline", "prompt": "consent"},
        ),
        "outlook_calendar": (
            "integrations_microsoft_client_id",
            "integrations_microsoft_client_secret",
            "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            ("Calendars.ReadWrite", "offline_access", "User.Read"),
            None,
        ),
        "hubspot": (
            "integrations_hubspot_client_id",
            "integrations_hubspot_client_secret",
            "https://app.hubspot.com/oauth/authorize",
            "https://api.hubapi.com/oauth/v1/token",
            ("crm.objects.contacts.read", "crm.objects.contacts.write"),
            None,
        ),
        "salesforce": (
            "integrations_salesforce_client_id",
            "integrations_salesforce_client_secret",
            "https://login.salesforce.com/services/oauth2/authorize",
            "https://login.salesforce.com/services/oauth2/token",
            ("api", "refresh_token"),
            None,
        ),
        "shopify": (
            "integrations_shopify_client_id",
            "integrations_shopify_client_secret",
            "",  # shop-specific URL built by adapter
            "",
            ("read_products", "read_orders", "read_customers"),
            None,
        ),
        "quickbooks": (
            "integrations_quickbooks_client_id",
            "integrations_quickbooks_client_secret",
            "https://appcenter.intuit.com/connect/oauth2",
            "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer",
            ("com.intuit.quickbooks.accounting",),
            None,
        ),
        "xero": (
            "integrations_xero_client_id",
            "integrations_xero_client_secret",
            "https://login.xero.com/identity/connect/authorize",
            "https://identity.xero.com/connect/token",
            ("openid", "profile", "email", "accounting.transactions", "offline_access"),
            None,
        ),
    }
    spec = mapping.get(provider)
    if not spec:
        return None
    id_attr, secret_attr, auth_url, token_url, scopes, extra = spec
    client_id = (getattr(settings, id_attr, None) or "").strip()
    client_secret = (getattr(settings, secret_attr, None) or "").strip()
    if not client_id or not client_secret:
        return None
    return OAuthAppConfig(
        provider=provider,
        client_id=client_id,
        client_secret=client_secret,
        authorize_url=auth_url,
        token_url=token_url,
        scopes=scopes,
        extra_auth_params=extra,
    )

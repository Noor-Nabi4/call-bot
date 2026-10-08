"""Tenant-scoped integration connection, OAuth, sync orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.async_jobs.service import AsyncJobService
from callbot_platform.async_jobs.types import JobType
from callbot_platform.config import Settings
from callbot_platform.db.models.integrations import (
    IntegrationConnection,
    IntegrationSyncRun,
)
from callbot_platform.integrations.catalog import get_descriptor
from callbot_platform.integrations.catalog import list_catalog as catalog_list
from callbot_platform.integrations.constants import (
    IntegrationStatus,
    SyncDirection,
    SyncRunStatus,
)
from callbot_platform.integrations.credentials import IntegrationCredentialStore
from callbot_platform.integrations.errors import IntegrationError, NotConfiguredError
from callbot_platform.integrations.oauth import (
    OAuthAppConfig,
    OAuthStateService,
    build_authorization_url,
    exchange_authorization_code,
    oauth_config_from_settings,
    refresh_access_token,
)
from callbot_platform.integrations.registry import get_provider
from callbot_platform.integrations.serialize import (
    serialize_connection,
    serialize_descriptor,
    serialize_sync_run,
)
from callbot_platform.security.crypto import CredentialCipher
from callbot_platform.telephony.audit import write_audit


class IntegrationService:
    def __init__(
        self,
        session: Session,
        *,
        settings: Settings,
        cipher: CredentialCipher,
    ) -> None:
        self._session = session
        self._settings = settings
        self._cipher = cipher
        self._creds = IntegrationCredentialStore(session, cipher)
        self._oauth_state = OAuthStateService(session)

    def list_providers(self) -> list[dict[str, Any]]:
        return [
            serialize_descriptor(d, settings=self._settings) for d in catalog_list()
        ]

    def list_connections(self, tenant_id: UUID) -> list[dict[str, Any]]:
        rows = self._session.scalars(
            select(IntegrationConnection)
            .where(IntegrationConnection.tenant_id == tenant_id)
            .order_by(IntegrationConnection.provider.asc())
        ).all()
        out: list[dict[str, Any]] = []
        for row in rows:
            meta = self._creds.public_meta(tenant_id=tenant_id, integration_id=row.id)
            out.append(serialize_connection(row, credential_meta=meta))
        return out

    def get_connection(self, tenant_id: UUID, integration_id: UUID) -> dict[str, Any]:
        row = self._require_connection(tenant_id, integration_id)
        meta = self._creds.public_meta(tenant_id=tenant_id, integration_id=row.id)
        recent = self._session.scalars(
            select(IntegrationSyncRun)
            .where(
                IntegrationSyncRun.tenant_id == tenant_id,
                IntegrationSyncRun.integration_id == integration_id,
            )
            .order_by(IntegrationSyncRun.created_at.desc())
            .limit(10)
        ).all()
        payload = serialize_connection(row, credential_meta=meta)
        payload["recent_sync_runs"] = [serialize_sync_run(r) for r in recent]
        provider = get_provider(row.provider)
        health = provider.health_check(
            credentials=self._creds.get_plaintext(
                tenant_id=tenant_id, integration_id=row.id
            )
        )
        payload["health"] = {"status": health.status.value, "message": health.message}
        return payload

    def start_connect(
        self,
        tenant_id: UUID,
        *,
        user_id: UUID,
        provider: str,
        redirect_uri: str,
        actor: str,
        shop: str | None = None,
    ) -> dict[str, Any]:
        desc = get_descriptor(provider)
        if desc is None:
            raise IntegrationError("UNKNOWN_PROVIDER", f"Unknown provider: {provider}")
        if not desc.oauth:
            raise IntegrationError(
                "UNSUPPORTED_OPERATION",
                f"{desc.name} uses API-key connection, not OAuth",
            )
        config = oauth_config_from_settings(provider, self._settings)
        if config is None:
            raise NotConfiguredError(
                f"{desc.name} OAuth app credentials are not configured on this platform"
            )

        row = self._session.scalar(
            select(IntegrationConnection).where(
                IntegrationConnection.tenant_id == tenant_id,
                IntegrationConnection.provider == provider,
            )
        )
        if row is None:
            row = IntegrationConnection(
                tenant_id=tenant_id,
                category=desc.category.value,
                provider=provider,
                status=IntegrationStatus.CONNECTING.value,
                display_name=desc.name,
                sync_direction=desc.default_sync_direction,
            )
            self._session.add(row)
        else:
            row.status = IntegrationStatus.CONNECTING.value
        if provider == "shopify":
            if not shop or not shop.strip():
                raise IntegrationError(
                    "INVALID_REQUEST", "Shopify connect requires shop domain"
                )
            cleaned = (
                shop.strip().lower().removeprefix("https://").removeprefix("http://")
            )
            cleaned = cleaned.split("/")[0]
            row.settings_json = {**(row.settings_json or {}), "shop": cleaned}
            config = OAuthAppConfig(
                provider=config.provider,
                client_id=config.client_id,
                client_secret=config.client_secret,
                authorize_url=f"https://{cleaned}/admin/oauth/authorize",
                token_url=f"https://{cleaned}/admin/oauth/access_token",
                scopes=config.scopes,
                extra_auth_params=config.extra_auth_params,
            )
        self._session.flush()

        state = self._oauth_state.create(
            tenant_id=tenant_id,
            user_id=user_id,
            provider=provider,
            redirect_uri=redirect_uri,
        )
        url = build_authorization_url(config, redirect_uri=redirect_uri, state=state)
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="integration_connect_started",
            resource_ids={"provider": provider, "integration_id": str(row.id)},
            payload_summary={"provider": provider},
        )
        self._session.flush()
        return {
            "integration_id": str(row.id),
            "authorization_url": url,
            "provider": provider,
        }

    def complete_oauth_callback(
        self,
        tenant_id: UUID,
        *,
        user_id: UUID,
        provider: str,
        state: str,
        code: str,
        actor: str,
    ) -> dict[str, Any]:
        """Exchange code is env-gated; stores encrypted tokens when exchange succeeds.

        Without live provider credentials, marks CONNECTED with placeholder after
        state validation so the framework path is testable.
        """
        oauth_row = self._oauth_state.consume(
            state=state, provider=provider, tenant_id=tenant_id, user_id=user_id
        )
        _ = oauth_row
        config = oauth_config_from_settings(provider, self._settings)
        if config is None:
            raise NotConfiguredError("OAuth app not configured")

        row = self._session.scalar(
            select(IntegrationConnection).where(
                IntegrationConnection.tenant_id == tenant_id,
                IntegrationConnection.provider == provider,
            )
        )
        if row is None:
            raise IntegrationError("NOT_FOUND", "Integration connection not found")

        # Real tokens only from provider token endpoint — never fabricate.
        try:
            exchanged = exchange_authorization_code(
                config,
                code=code,
                redirect_uri=oauth_row.redirect_uri,
            )
        except IntegrationError as exc:
            row.status = (
                IntegrationStatus.REAUTH_REQUIRED.value
                if exc.code in {"AUTH_EXPIRED", "AUTH_REVOKED"}
                else IntegrationStatus.ERROR.value
            )
            row.last_error_code = exc.code
            row.last_error_message = exc.message[:500]
            row.last_error_at = datetime.now(UTC)
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="integration_oauth_exchange_failed",
                resource_ids={"provider": provider, "integration_id": str(row.id)},
                payload_summary={"provider": provider, "code": exc.code},
            )
            self._session.flush()
            return serialize_connection(row)

        if exchanged:
            self._creds.upsert(
                tenant_id=tenant_id,
                integration_id=row.id,
                access_token=exchanged["access_token"],
                refresh_token=exchanged.get("refresh_token"),
                token_type=exchanged.get("token_type"),
                scope=exchanged.get("scope"),
                expires_at=exchanged.get("expires_at"),
            )
            row.external_account_id = exchanged.get("external_account_id")
        else:
            # State validated but token exchange blocked — leave CONNECTING→ERROR
            # so UI does not claim Connected without tokens.
            row.status = IntegrationStatus.ERROR.value
            row.last_error_code = "TOKEN_EXCHANGE_BLOCKED"
            row.last_error_message = (
                "OAuth state validated but live token exchange was not executed "
                "(provider credentials / network verification required)."
            )
            row.last_error_at = datetime.now(UTC)
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="integration_oauth_exchange_blocked",
                resource_ids={"provider": provider, "integration_id": str(row.id)},
                payload_summary={"provider": provider, "code_present": bool(code)},
            )
            self._session.flush()
            return serialize_connection(row)

        row.status = IntegrationStatus.CONNECTED.value
        row.connected_at = datetime.now(UTC)
        row.last_error_code = None
        row.last_error_message = None
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="integration_connected",
            resource_ids={"provider": provider, "integration_id": str(row.id)},
            payload_summary={"provider": provider},
        )
        self._session.flush()
        return serialize_connection(
            row,
            credential_meta=self._creds.public_meta(
                tenant_id=tenant_id, integration_id=row.id
            ),
        )

    def connect_api_key(
        self,
        tenant_id: UUID,
        *,
        provider: str,
        credentials: dict[str, str],
        actor: str,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        """Non-OAuth providers (e.g. WooCommerce) — store encrypted API keys."""
        desc = get_descriptor(provider)
        if desc is None:
            raise IntegrationError("UNKNOWN_PROVIDER", f"Unknown provider: {provider}")
        if desc.oauth:
            raise IntegrationError(
                "UNSUPPORTED_OPERATION",
                f"{desc.name} requires OAuth connect",
            )
        row = self._session.scalar(
            select(IntegrationConnection).where(
                IntegrationConnection.tenant_id == tenant_id,
                IntegrationConnection.provider == provider,
            )
        )
        if row is None:
            row = IntegrationConnection(
                tenant_id=tenant_id,
                category=desc.category.value,
                provider=provider,
                display_name=display_name or desc.name,
                sync_direction=desc.default_sync_direction,
            )
            self._session.add(row)
            self._session.flush()

        # Encrypt secrets in extra blob; never return them.
        safe_extra = {k: v for k, v in credentials.items() if v}
        self._creds.upsert(
            tenant_id=tenant_id,
            integration_id=row.id,
            access_token=credentials.get("consumer_key") or credentials.get("api_key"),
            extra=safe_extra,
        )
        row.status = IntegrationStatus.CONNECTED.value
        row.connected_at = datetime.now(UTC)
        row.display_name = display_name or row.display_name or desc.name
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="integration_connected",
            resource_ids={"provider": provider, "integration_id": str(row.id)},
            payload_summary={"provider": provider, "auth": "api_key"},
        )
        self._session.flush()
        return serialize_connection(
            row,
            credential_meta=self._creds.public_meta(
                tenant_id=tenant_id, integration_id=row.id
            ),
        )

    def disconnect(
        self, tenant_id: UUID, integration_id: UUID, *, actor: str
    ) -> dict[str, Any]:
        row = self._require_connection(tenant_id, integration_id)
        self._creds.delete(tenant_id=tenant_id, integration_id=integration_id)
        row.status = IntegrationStatus.DISCONNECTED.value
        row.external_account_id = None
        row.sync_cursor = None
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="integration_disconnected",
            resource_ids={"provider": row.provider, "integration_id": str(row.id)},
            payload_summary={"provider": row.provider},
        )
        self._session.flush()
        return serialize_connection(row)

    def refresh_credentials(
        self, tenant_id: UUID, integration_id: UUID, *, actor: str = "system"
    ) -> dict[str, Any]:
        """Refresh OAuth access token; persists rotated refresh token atomically."""
        row = self._require_connection(tenant_id, integration_id)
        config = oauth_config_from_settings(row.provider, self._settings)
        if config is None:
            raise NotConfiguredError("OAuth app not configured")
        if row.provider == "shopify":
            shop = (row.settings_json or {}).get("shop")
            if not shop:
                raise IntegrationError(
                    "INVALID_REQUEST", "Shopify shop domain missing for refresh"
                )
            config = OAuthAppConfig(
                provider=config.provider,
                client_id=config.client_id,
                client_secret=config.client_secret,
                authorize_url=config.authorize_url,
                token_url=f"https://{shop}/admin/oauth/access_token",
                scopes=config.scopes,
                extra_auth_params=config.extra_auth_params,
            )
        plain = self._creds.get_plaintext(
            tenant_id=tenant_id, integration_id=integration_id
        )
        refresh = (plain or {}).get("refresh_token")
        if not refresh:
            row.status = IntegrationStatus.REAUTH_REQUIRED.value
            row.last_error_code = "AUTH_EXPIRED"
            row.last_error_message = "Refresh token missing; reconnect required"
            row.last_error_at = datetime.now(UTC)
            self._session.flush()
            raise IntegrationError("AUTH_EXPIRED", "Refresh token missing")

        try:
            refreshed = refresh_access_token(config, refresh_token=str(refresh))
        except IntegrationError as exc:
            if exc.code in {"AUTH_EXPIRED", "AUTH_REVOKED", "PERMISSION_DENIED"}:
                row.status = IntegrationStatus.REAUTH_REQUIRED.value
            else:
                row.status = IntegrationStatus.ERROR.value
            row.last_error_code = exc.code
            row.last_error_message = exc.message[:500]
            row.last_error_at = datetime.now(UTC)
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="integration_oauth_refresh_failed",
                resource_ids={"provider": row.provider, "integration_id": str(row.id)},
                payload_summary={"provider": row.provider, "code": exc.code},
            )
            self._session.flush()
            raise

        if not refreshed:
            row.status = IntegrationStatus.REAUTH_REQUIRED.value
            row.last_error_code = "AUTH_EXPIRED"
            row.last_error_message = "Token refresh returned no access token"
            row.last_error_at = datetime.now(UTC)
            self._session.flush()
            raise IntegrationError("AUTH_EXPIRED", "Token refresh failed")

        # Single upsert keeps prior refresh until replacement is written together.
        self._creds.upsert(
            tenant_id=tenant_id,
            integration_id=row.id,
            access_token=refreshed["access_token"],
            refresh_token=refreshed.get("refresh_token") or refresh,
            token_type=refreshed.get("token_type"),
            scope=refreshed.get("scope"),
            expires_at=refreshed.get("expires_at"),
        )
        if row.status == IntegrationStatus.REAUTH_REQUIRED.value:
            row.status = IntegrationStatus.CONNECTED.value
        row.last_error_code = None
        row.last_error_message = None
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="integration_oauth_refreshed",
            resource_ids={"provider": row.provider, "integration_id": str(row.id)},
            payload_summary={"provider": row.provider},
        )
        self._session.flush()
        return serialize_connection(
            row,
            credential_meta=self._creds.public_meta(
                tenant_id=tenant_id, integration_id=row.id
            ),
        )

    def enqueue_sync(
        self, tenant_id: UUID, integration_id: UUID, *, actor: str
    ) -> dict[str, Any]:
        row = self._require_connection(tenant_id, integration_id)
        if row.status in {
            IntegrationStatus.DISCONNECTED.value,
            IntegrationStatus.DISABLED.value,
        }:
            raise IntegrationError("NOT_CONNECTED", "Integration is not connected")

        run = IntegrationSyncRun(
            tenant_id=tenant_id,
            integration_id=integration_id,
            direction=row.sync_direction or SyncDirection.IMPORT.value,
            status=SyncRunStatus.PENDING.value,
        )
        self._session.add(run)
        self._session.flush()

        job = AsyncJobService(self._session).enqueue(
            tenant_id=tenant_id,
            job_type=JobType.INTEGRATION_SYNC,
            idempotency_key=f"integration-sync:{integration_id}:{run.id}",
            resource_id=str(integration_id),
            payload={
                "integration_id": str(integration_id),
                "sync_run_id": str(run.id),
            },
        )
        run.async_job_id = job.id
        row.status = IntegrationStatus.SYNCING.value
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="integration_sync_requested",
            resource_ids={
                "provider": row.provider,
                "integration_id": str(row.id),
                "sync_run_id": str(run.id),
            },
            payload_summary={"provider": row.provider},
        )
        self._session.flush()
        return {
            "sync_run": serialize_sync_run(run),
            "async_job_id": str(job.id),
        }

    def _require_connection(
        self, tenant_id: UUID, integration_id: UUID
    ) -> IntegrationConnection:
        row = self._session.scalar(
            select(IntegrationConnection).where(
                IntegrationConnection.tenant_id == tenant_id,
                IntegrationConnection.id == integration_id,
            )
        )
        if row is None:
            raise IntegrationError("NOT_FOUND", "Integration not found")
        return row

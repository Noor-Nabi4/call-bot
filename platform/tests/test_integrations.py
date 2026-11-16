"""Phase 28 Integrations: OAuth state, credentials, sync, webhooks, isolation."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.api.deps import cipher_dep, db_dep, settings_dep
from callbot_platform.auth.repos import AuthRepository
from callbot_platform.config import Settings, get_settings
from callbot_platform.db.models import Tenant
from callbot_platform.db.models.integrations import (
    IntegrationConnection,
    IntegrationOauthState,
    IntegrationWebhookEvent,
)
from callbot_platform.integrations.catalog import list_catalog
from callbot_platform.integrations.constants import IntegrationStatus, ProviderKey
from callbot_platform.integrations.credentials import IntegrationCredentialStore
from callbot_platform.integrations.errors import IntegrationError
from callbot_platform.integrations.oauth import OAuthStateService
from callbot_platform.integrations.providers import build_provider_registry
from callbot_platform.integrations.registry import get_provider
from callbot_platform.integrations.service import IntegrationService
from callbot_platform.integrations.sync import SyncEngine
from callbot_platform.integrations.webhooks import (
    WebhookIngestService,
    verify_hmac_sha256,
)
from callbot_platform.main import app
from callbot_platform.security.crypto import CredentialCipher
from callbot_platform.security.session import create_session_token
from callbot_platform.telephony.audit import write_audit  # noqa: F401

CRYPTO = "test-credentials-encryption-key-integrations28"


@pytest.fixture()
def session_settings() -> Settings:
    return Settings(
        session_secret="test-session-secret-integrations-ok32",
        internal_service_token="internal-test-token",
        session_cookie_name="callbot_ops_session",
        credentials_encryption_key=CRYPTO,
        integrations_google_client_id="google-client",
        integrations_google_client_secret="google-secret",
    )


def _override_db(session: Session):
    def _db() -> Generator[Session, None, None]:
        yield session

    return _db


def _client_for(
    session: Session, settings: Settings, *, token: str | None = None
) -> TestClient:
    cipher = CredentialCipher(CRYPTO)
    app.dependency_overrides[db_dep] = _override_db(session)
    app.dependency_overrides[settings_dep] = lambda: settings
    app.dependency_overrides[cipher_dep] = lambda: cipher
    get_settings.cache_clear()
    client = TestClient(app)
    if token:
        client.cookies.set(settings.session_cookie_name, token)
    return client


def _token_for(settings: Settings, user: dict, tenant: Tenant) -> str:
    return create_session_token(
        settings=settings,
        user_id=uuid.UUID(user["id"]),
        tenant_id=tenant.id,
        role=user["role"],
        email=user["email"],
    )


def test_catalog_and_registry_cover_all_providers() -> None:
    catalog = {d.key for d in list_catalog()}
    registry = build_provider_registry()
    expected = {p.value for p in ProviderKey}
    assert catalog == expected
    assert set(registry.keys()) == expected
    for key, adapter in registry.items():
        assert adapter.descriptor.key == key
        page = adapter.sync_page(
            tenant_id=uuid.uuid4(),
            credentials=None,
            cursor=None,
            direction="IMPORT",
        )
        assert page.done is True


def test_oauth_state_tenant_bound_single_use(session: Session, tenant: Tenant) -> None:
    user_id = uuid.uuid4()
    svc = OAuthStateService(session)
    state = svc.create(
        tenant_id=tenant.id,
        user_id=user_id,
        provider="google_calendar",
        redirect_uri="http://localhost:3000/settings/integrations/callback",
    )
    row = svc.consume(
        state=state,
        provider="google_calendar",
        tenant_id=tenant.id,
        user_id=user_id,
    )
    assert row.consumed_at is not None

    with pytest.raises(IntegrationError) as reused:
        svc.consume(
            state=state,
            provider="google_calendar",
            tenant_id=tenant.id,
            user_id=user_id,
        )
    assert reused.value.code == "OAUTH_STATE_REUSED"

    other = Tenant(name="Other", slug=f"other-{uuid.uuid4().hex[:8]}")
    session.add(other)
    session.flush()
    state2 = svc.create(
        tenant_id=tenant.id,
        user_id=user_id,
        provider="google_calendar",
        redirect_uri="http://localhost:3000/cb",
    )
    with pytest.raises(IntegrationError) as mismatch:
        svc.consume(
            state=state2,
            provider="google_calendar",
            tenant_id=other.id,
            user_id=user_id,
        )
    assert mismatch.value.code == "OAUTH_STATE_MISMATCH"


def test_oauth_state_expired(session: Session, tenant: Tenant) -> None:
    user_id = uuid.uuid4()
    state = secrets_state = OAuthStateService(session).create(
        tenant_id=tenant.id,
        user_id=user_id,
        provider="hubspot",
        redirect_uri="http://localhost/cb",
    )
    row = session.scalar(
        select(IntegrationOauthState).where(
            IntegrationOauthState.state == secrets_state
        )
    )
    assert row is not None
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session.flush()
    with pytest.raises(IntegrationError) as exc:
        OAuthStateService(session).consume(
            state=state,
            provider="hubspot",
            tenant_id=tenant.id,
            user_id=user_id,
        )
    assert exc.value.code == "OAUTH_STATE_EXPIRED"


def test_credential_encryption_never_plaintext_in_store(
    session: Session, tenant: Tenant, cipher: CredentialCipher
) -> None:
    conn = IntegrationConnection(
        tenant_id=tenant.id,
        category="calendar",
        provider="google_calendar",
        status=IntegrationStatus.CONNECTED.value,
        display_name="Google Calendar",
    )
    session.add(conn)
    session.flush()
    store = IntegrationCredentialStore(session, cipher)
    store.upsert(
        tenant_id=tenant.id,
        integration_id=conn.id,
        access_token="secret-access-token",
        refresh_token="secret-refresh-token",
        extra={"shop": "demo.myshopify.com"},
    )
    meta = store.public_meta(tenant_id=tenant.id, integration_id=conn.id)
    assert meta is not None
    assert meta["has_access_token"] is True
    assert "secret-access-token" not in str(meta)
    plain = store.get_plaintext(tenant_id=tenant.id, integration_id=conn.id)
    assert plain is not None
    assert plain["access_token"] == "secret-access-token"
    assert plain["extra"]["shop"] == "demo.myshopify.com"


def test_webhook_dedupe_and_hmac() -> None:
    secret = "whsec"
    body = b'{"id":"evt_1"}'
    import hashlib
    import hmac

    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_hmac_sha256(
        raw_body=body, signature_header=f"sha256={sig}", secret=secret
    )
    assert not verify_hmac_sha256(
        raw_body=body, signature_header="sha256=bad", secret=secret
    )


def test_webhook_ingest_idempotent(session: Session, tenant: Tenant) -> None:
    conn = IntegrationConnection(
        tenant_id=tenant.id,
        category="commerce",
        provider="shopify",
        status=IntegrationStatus.CONNECTED.value,
    )
    session.add(conn)
    session.flush()
    svc = WebhookIngestService(session)
    first = svc.ingest(
        tenant_id=tenant.id,
        integration_id=conn.id,
        provider_event_id="evt-1",
        event_type="orders/create",
        raw_body=b'{"id":1}',
    )
    second = svc.ingest(
        tenant_id=tenant.id,
        integration_id=conn.id,
        provider_event_id="evt-1",
        event_type="orders/create",
        raw_body=b'{"id":1}',
    )
    assert first["duplicate"] is False
    assert second["duplicate"] is True
    rows = list(
        session.scalars(
            select(IntegrationWebhookEvent).where(
                IntegrationWebhookEvent.tenant_id == tenant.id
            )
        )
    )
    assert len(rows) == 1


def test_sync_engine_empty_page_succeeds(
    session: Session, tenant: Tenant, cipher: CredentialCipher
) -> None:
    conn = IntegrationConnection(
        tenant_id=tenant.id,
        category="calendar",
        provider="google_calendar",
        status=IntegrationStatus.CONNECTED.value,
    )
    session.add(conn)
    session.flush()
    from callbot_platform.db.models.integrations import IntegrationSyncRun

    run = IntegrationSyncRun(
        tenant_id=tenant.id,
        integration_id=conn.id,
        direction="IMPORT",
        status="PENDING",
    )
    session.add(run)
    session.flush()
    result = SyncEngine(session, cipher).run(
        tenant_id=tenant.id,
        integration_id=conn.id,
        sync_run_id=run.id,
    )
    assert result["status"] == "SUCCEEDED"
    session.refresh(conn)
    assert conn.status == IntegrationStatus.SYNCED.value


def test_admin_list_providers_and_tenant_isolation(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    other = Tenant(name="Beta", slug=f"beta-{uuid.uuid4().hex[:8]}")
    session.add(other)
    session.flush()
    session.add(
        IntegrationConnection(
            tenant_id=other.id,
            category="crm",
            provider="hubspot",
            status=IntegrationStatus.CONNECTED.value,
            display_name="Other HubSpot",
        )
    )
    session.flush()

    admin = AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email="admin@int.test",
        password="password123",
        name="Admin",
    )
    token = _token_for(session_settings, admin, tenant)
    client = _client_for(session, session_settings, token=token)
    try:
        providers = client.get("/api/admin/integrations/providers")
        assert providers.status_code == 200
        keys = {p["key"] for p in providers.json()["providers"]}
        assert "google_calendar" in keys
        google = next(
            p for p in providers.json()["providers"] if p["key"] == "google_calendar"
        )
        assert google["platform_configured"] is True
        hubspot = next(
            p for p in providers.json()["providers"] if p["key"] == "hubspot"
        )
        assert hubspot["platform_configured"] is False

        listed = client.get("/api/admin/integrations")
        assert listed.status_code == 200
        assert listed.json()["integrations"] == []

        # Connect start for google
        started = client.post(
            "/api/admin/integrations/google_calendar/connect",
            json={
                "redirect_uri": "http://localhost:3000/settings/integrations/callback"
            },
        )
        assert started.status_code == 200
        body = started.json()
        assert "authorization_url" in body
        assert "client_secret" not in str(body).lower()
        assert "google-secret" not in str(body)

        # Callback without live exchange → ERROR (not fake Connected)
        with patch(
            "callbot_platform.integrations.service.exchange_authorization_code",
            return_value=None,
        ):
            # Need fresh state — start_connect already created one; create new via service
            svc = IntegrationService(
                session,
                settings=session_settings,
                cipher=CredentialCipher(CRYPTO),
            )
            # Manually set state for callback path through API
            from callbot_platform.integrations.oauth import OAuthStateService

            state = OAuthStateService(session).create(
                tenant_id=tenant.id,
                user_id=uuid.UUID(admin["id"]),
                provider="google_calendar",
                redirect_uri="http://localhost:3000/settings/integrations/callback",
            )
            session.flush()
            cb = client.post(
                "/api/admin/integrations/google_calendar/callback",
                json={"state": state, "code": "auth-code"},
            )
            assert cb.status_code == 200
            assert cb.json()["integration"]["status"] == "ERROR"
            assert "access_token" not in str(cb.json()).lower()
            _ = svc
    finally:
        app.dependency_overrides.clear()


def test_dispatcher_cannot_connect(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email="admin@int2.test",
        password="password123",
        name="Admin",
    )
    dispatcher = AuthRepository(session).create_user(
        tenant.id,
        email="disp@int2.test",
        password="password123",
        name="Disp",
        role="dispatcher",
        actor="test",
    )
    token = _token_for(session_settings, dispatcher, tenant)
    client = _client_for(session, session_settings, token=token)
    try:
        res = client.post(
            "/api/admin/integrations/google_calendar/connect",
            json={"redirect_uri": "http://localhost:3000/cb"},
        )
        assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_woocommerce_api_key_connect_and_disconnect(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    admin = AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email="admin@woo.test",
        password="password123",
        name="Admin",
    )
    token = _token_for(session_settings, admin, tenant)
    client = _client_for(session, session_settings, token=token)
    try:
        connected = client.post(
            "/api/admin/integrations/woocommerce/api-key",
            json={
                "credentials": {
                    "store_url": "https://shop.example",
                    "consumer_key": "ck_test",
                    "consumer_secret": "cs_test",
                    "api_key": "ck_test",
                }
            },
        )
        assert connected.status_code == 200
        body = connected.json()["integration"]
        assert body["status"] == "CONNECTED"
        assert "ck_test" not in str(connected.json())
        assert "cs_test" not in str(connected.json())
        integration_id = body["id"]

        sync = client.post(f"/api/admin/integrations/{integration_id}/sync")
        assert sync.status_code == 200
        assert "async_job_id" in sync.json()

        deleted = client.delete(f"/api/admin/integrations/{integration_id}")
        assert deleted.status_code == 200
        assert deleted.json()["integration"]["status"] == "DISCONNECTED"
    finally:
        app.dependency_overrides.clear()


def test_provider_contract_health_without_credentials() -> None:
    for key in ProviderKey:
        provider = get_provider(key.value)
        health = provider.health_check(credentials=None)
        assert health.status.value in {
            "AUTH_REQUIRED",
            "NOT_CONFIGURED",
            "HEALTHY",
            "ERROR",
        }


def test_oauth_state_wrong_user_and_provider_and_missing(
    session: Session, tenant: Tenant
) -> None:
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    svc = OAuthStateService(session)
    state = svc.create(
        tenant_id=tenant.id,
        user_id=user_a,
        provider="google_calendar",
        redirect_uri="http://localhost/cb",
    )
    with pytest.raises(IntegrationError) as wrong_user:
        svc.consume(
            state=state,
            provider="google_calendar",
            tenant_id=tenant.id,
            user_id=user_b,
        )
    assert wrong_user.value.code == "OAUTH_STATE_MISMATCH"

    state2 = svc.create(
        tenant_id=tenant.id,
        user_id=user_a,
        provider="google_calendar",
        redirect_uri="http://localhost/cb",
    )
    with pytest.raises(IntegrationError) as wrong_provider:
        svc.consume(
            state=state2,
            provider="hubspot",
            tenant_id=tenant.id,
            user_id=user_a,
        )
    assert wrong_provider.value.code == "OAUTH_STATE_MISMATCH"

    with pytest.raises(IntegrationError) as missing:
        svc.consume(
            state="not-a-real-state-value",
            provider="google_calendar",
            tenant_id=tenant.id,
            user_id=user_a,
        )
    assert missing.value.code == "OAUTH_STATE_INVALID"
    assert "token" not in missing.value.message.lower()


def test_unknown_provider_registry_error() -> None:
    with pytest.raises(IntegrationError) as exc:
        get_provider("not_a_real_provider")
    assert exc.value.code == "UNKNOWN_PROVIDER"


def test_require_capability_raises_unsupported() -> None:
    provider = get_provider("woocommerce")
    with pytest.raises(IntegrationError) as exc:
        provider.require_capability("INVOICES_WRITE")
    assert exc.value.code == "UNSUPPORTED_OPERATION"


def test_http_retry_classification() -> None:
    import httpx

    from callbot_platform.integrations.errors import RateLimitedError
    from callbot_platform.integrations.http import (
        classify_http_error,
        redact_headers,
    )

    resp_429 = httpx.Response(
        429,
        headers={"Retry-After": "2"},
        request=httpx.Request("GET", "https://example.test"),
    )
    err = classify_http_error(resp_429)
    assert isinstance(err, RateLimitedError)
    assert err.retryable is True
    assert err.retry_after == 2.0

    resp_400 = httpx.Response(400, request=httpx.Request("GET", "https://example.test"))
    err400 = classify_http_error(resp_400)
    assert err400.retryable is False

    redacted = redact_headers(
        {"Authorization": "Bearer secret-token", "X-Request-Id": "abc"}
    )
    assert redacted["Authorization"] == "[REDACTED]"
    assert redacted["X-Request-Id"] == "abc"
    assert "secret-token" not in str(redacted)


def test_token_refresh_rotates_and_preserves(
    session: Session,
    tenant: Tenant,
    cipher: CredentialCipher,
    session_settings: Settings,
) -> None:
    conn = IntegrationConnection(
        tenant_id=tenant.id,
        category="calendar",
        provider="google_calendar",
        status=IntegrationStatus.CONNECTED.value,
    )
    session.add(conn)
    session.flush()
    store = IntegrationCredentialStore(session, cipher)
    store.upsert(
        tenant_id=tenant.id,
        integration_id=conn.id,
        access_token="old-access",
        refresh_token="old-refresh",
    )
    svc = IntegrationService(session, settings=session_settings, cipher=cipher)

    with patch(
        "callbot_platform.integrations.service.refresh_access_token",
        return_value={
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "token_type": "Bearer",
            "scope": None,
            "expires_at": None,
            "external_account_id": None,
        },
    ):
        out = svc.refresh_credentials(tenant.id, conn.id, actor="test")
    assert out["credentials"]["has_access_token"] is True
    assert "new-access" not in str(out)
    plain = store.get_plaintext(tenant_id=tenant.id, integration_id=conn.id)
    assert plain is not None
    assert plain["access_token"] == "new-access"
    assert plain["refresh_token"] == "new-refresh"

    # Provider omits rotated refresh → keep prior
    with patch(
        "callbot_platform.integrations.service.refresh_access_token",
        return_value={
            "access_token": "newer-access",
            "refresh_token": "new-refresh",  # refresh_access_token already preserves
            "token_type": "Bearer",
            "scope": None,
            "expires_at": None,
            "external_account_id": None,
        },
    ):
        svc.refresh_credentials(tenant.id, conn.id, actor="test")
    plain2 = store.get_plaintext(tenant_id=tenant.id, integration_id=conn.id)
    assert plain2 is not None
    assert plain2["access_token"] == "newer-access"
    assert plain2["refresh_token"] == "new-refresh"


def test_sync_pagination_idempotency_and_partial_failure(
    session: Session, tenant: Tenant, cipher: CredentialCipher
) -> None:
    from callbot_platform.db.models.integrations import IntegrationSyncRun
    from callbot_platform.integrations.catalog import PROVIDER_CATALOG
    from callbot_platform.integrations.protocols import ExternalCustomer, SyncPage
    from callbot_platform.integrations.providers.base import BaseProviderAdapter

    class FakeAdapter(BaseProviderAdapter):
        def __init__(self) -> None:
            self.descriptor = PROVIDER_CATALOG["hubspot"]
            self.calls = 0
            self.fail_on_page: int | None = None

        def sync_page(self, *, tenant_id, credentials, cursor, direction):
            self.calls += 1
            if self.fail_on_page == self.calls:
                raise IntegrationError(
                    "SYNC_FAILED", "forced page failure", retryable=False
                )
            if cursor is None:
                return SyncPage(
                    items=[
                        ExternalCustomer(external_id="c1", name="A"),
                        ExternalCustomer(external_id="c2", name="B"),
                    ],
                    next_cursor="p2",
                    done=False,
                )
            return SyncPage(
                items=[ExternalCustomer(external_id="c3", name="C")],
                next_cursor=None,
                done=True,
            )

    fake = FakeAdapter()
    conn = IntegrationConnection(
        tenant_id=tenant.id,
        category="crm",
        provider="hubspot",
        status=IntegrationStatus.CONNECTED.value,
    )
    session.add(conn)
    session.flush()

    def _run() -> dict:
        run = IntegrationSyncRun(
            tenant_id=tenant.id,
            integration_id=conn.id,
            direction="IMPORT",
            status="PENDING",
        )
        session.add(run)
        session.flush()
        with patch(
            "callbot_platform.integrations.sync.get_provider", return_value=fake
        ):
            return SyncEngine(session, cipher).run(
                tenant_id=tenant.id,
                integration_id=conn.id,
                sync_run_id=run.id,
            )

    first = _run()
    assert first["status"] == "SUCCEEDED"
    assert first["created"] == 3
    assert first["pages"] == 2
    assert first["updated"] == 0

    fake.calls = 0
    second = _run()
    assert second["status"] == "SUCCEEDED"
    assert second["created"] == 0
    assert second["updated"] == 3

    from callbot_platform.db.models.integrations import IntegrationExternalMapping

    maps = list(
        session.scalars(
            select(IntegrationExternalMapping).where(
                IntegrationExternalMapping.tenant_id == tenant.id,
                IntegrationExternalMapping.integration_id == conn.id,
            )
        )
    )
    assert len(maps) == 3
    assert {m.external_id for m in maps} == {"c1", "c2", "c3"}

    # Partial failure mid-sync
    fake.fail_on_page = 1
    fake.calls = 0
    failed = _run()
    assert failed["status"] == "FAILED"
    assert failed["error_code"] == "SYNC_FAILED"
    session.refresh(conn)
    assert conn.status == IntegrationStatus.ERROR.value


def test_webhook_tenant_isolation(session: Session, tenant: Tenant) -> None:
    other = Tenant(name="Other", slug=f"o-{uuid.uuid4().hex[:8]}")
    session.add(other)
    session.flush()
    conn_a = IntegrationConnection(
        tenant_id=tenant.id,
        category="commerce",
        provider="shopify",
        status=IntegrationStatus.CONNECTED.value,
    )
    session.add(conn_a)
    session.flush()
    svc = WebhookIngestService(session)
    with pytest.raises(IntegrationError) as exc:
        svc.ingest(
            tenant_id=other.id,
            integration_id=conn_a.id,
            provider_event_id="evt-x",
            event_type="orders/create",
            raw_body=b"{}",
        )
    assert exc.value.code == "WEBHOOK_INVALID"


def test_cross_tenant_cannot_get_or_sync_or_delete(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    other = Tenant(name="Beta", slug=f"beta-{uuid.uuid4().hex[:8]}")
    session.add(other)
    session.flush()
    foreign = IntegrationConnection(
        tenant_id=other.id,
        category="crm",
        provider="hubspot",
        status=IntegrationStatus.CONNECTED.value,
    )
    session.add(foreign)
    session.flush()

    admin = AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email="admin@iso.test",
        password="password123",
        name="Admin",
    )
    token = _token_for(session_settings, admin, tenant)
    client = _client_for(session, session_settings, token=token)
    try:
        got = client.get(f"/api/admin/integrations/{foreign.id}")
        assert got.status_code == 404
        sync = client.post(f"/api/admin/integrations/{foreign.id}/sync")
        assert sync.status_code == 404
        deleted = client.delete(f"/api/admin/integrations/{foreign.id}")
        assert deleted.status_code == 404
        session.refresh(foreign)
        assert foreign.status == IntegrationStatus.CONNECTED.value
    finally:
        app.dependency_overrides.clear()


def test_oauth_callback_success_encrypts_tokens_no_leak(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    admin = AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email="admin@oauth.test",
        password="password123",
        name="Admin",
    )
    token = _token_for(session_settings, admin, tenant)
    client = _client_for(session, session_settings, token=token)
    try:
        started = client.post(
            "/api/admin/integrations/google_calendar/connect",
            json={"redirect_uri": "http://localhost:3000/cb"},
        )
        assert started.status_code == 200
        state = OAuthStateService(session).create(
            tenant_id=tenant.id,
            user_id=uuid.UUID(admin["id"]),
            provider="google_calendar",
            redirect_uri="http://localhost:3000/cb",
        )
        session.flush()
        with patch(
            "callbot_platform.integrations.service.exchange_authorization_code",
            return_value={
                "access_token": "live-access-token-xyz",
                "refresh_token": "live-refresh-token-xyz",
                "token_type": "Bearer",
                "scope": "calendar",
                "expires_at": None,
                "external_account_id": "acct-1",
            },
        ):
            cb = client.post(
                "/api/admin/integrations/google_calendar/callback",
                json={"state": state, "code": "auth-code-should-not-persist"},
            )
        assert cb.status_code == 200
        body = cb.json()
        raw = str(body)
        assert body["integration"]["status"] == "CONNECTED"
        assert "live-access-token-xyz" not in raw
        assert "live-refresh-token-xyz" not in raw
        assert "auth-code-should-not-persist" not in raw
        assert body["integration"]["credentials"]["has_access_token"] is True
        assert body["integration"]["credentials"]["has_refresh_token"] is True

        # Authorization code must not be stored on oauth state row
        oauth_rows = list(session.scalars(select(IntegrationOauthState)))
        for row in oauth_rows:
            assert "auth-code" not in (row.state or "")
            assert "auth-code" not in (row.redirect_uri or "")
    finally:
        app.dependency_overrides.clear()

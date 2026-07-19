"""Authenticated agent-settings security tests."""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from callbot_platform.api.deps import db_dep, settings_dep
from callbot_platform.auth.repos import AuthRepository
from callbot_platform.config import Settings, get_settings
from callbot_platform.crm.repos import AgentSettingsRepository
from callbot_platform.db.models import Tenant, TelephonyAuditEvent
from callbot_platform.main import app
from callbot_platform.security.session import create_session_token
from sqlalchemy import select


@pytest.fixture()
def session_settings() -> Settings:
    return Settings(
        session_secret="test-session-secret-agent-settings-ok32",
        internal_service_token="internal-test-token",
        session_cookie_name="callbot_ops_session",
    )


@pytest.fixture()
def tenant_b(session: Session) -> Tenant:
    row = Tenant(name="Beta Co", slug=f"beta-{uuid.uuid4().hex[:8]}")
    session.add(row)
    session.flush()
    return row


def _override_db(session: Session):
    def _db() -> Generator[Session, None, None]:
        yield session

    return _db


def _client_for(
    session: Session, settings: Settings, *, token: str | None = None
) -> TestClient:
    app.dependency_overrides[db_dep] = _override_db(session)
    app.dependency_overrides[settings_dep] = lambda: settings
    get_settings.cache_clear()
    client = TestClient(app)
    if token:
        client.cookies.set(settings.session_cookie_name, token)
    return client


def _make_user(
    session: Session,
    tenant: Tenant,
    *,
    email: str,
    role: str,
    password: str = "password123",
) -> dict:
    auth = AuthRepository(session)
    if role == "admin":
        try:
            return auth.bootstrap_admin(
                tenant_id=tenant.id,
                email=email,
                password=password,
                name=email.split("@")[0],
            )
        except Exception:
            return auth.create_user(
                tenant.id,
                email=email,
                password=password,
                name=email.split("@")[0],
                role=role,
                actor="test",
            )
    return auth.create_user(
        tenant.id,
        email=email,
        password=password,
        name=email.split("@")[0],
        role=role,
        actor="test",
    )


def _token_for(settings: Settings, user: dict, tenant: Tenant) -> str:
    return create_session_token(
        settings=settings,
        user_id=uuid.UUID(user["id"]),
        tenant_id=tenant.id,
        role=user["role"],
        email=user["email"],
    )


def test_unauthenticated_legacy_put_returns_401(
    session: Session, tenant: Tenant
) -> None:
    client = _client_for(
        session,
        Settings(
            session_secret="x" * 32,
            internal_service_token="tok",
        ),
    )
    try:
        res = client.put(
            f"/tenants/{tenant.id}/agent-settings",
            json={"greeting": "hacked"},
        )
        assert res.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_unauthenticated_admin_put_returns_401(
    session: Session, session_settings: Settings
) -> None:
    client = _client_for(session, session_settings)
    try:
        res = client.put("/api/admin/agent-settings", json={"greeting": "hi"})
        assert res.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_dispatcher_cannot_edit_profile(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email="admin@t.test",
        password="password123",
        name="Admin",
    )
    dispatcher = _make_user(session, tenant, email="disp@t.test", role="dispatcher")
    token = _token_for(session_settings, dispatcher, tenant)
    client = _client_for(session, session_settings, token=token)
    try:
        res = client.put(
            "/api/admin/agent-settings",
            json={"greeting": "dispatcher edit"},
        )
        assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_technician_cannot_edit_profile(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email="admin@t.test",
        password="password123",
        name="Admin",
    )
    tech = _make_user(session, tenant, email="tech@t.test", role="technician")
    token = _token_for(session_settings, tech, tenant)
    client = _client_for(session, session_settings, token=token)
    try:
        res = client.put(
            "/api/admin/agent-settings",
            json={"greeting": "tech edit"},
        )
        assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_admin_updates_only_own_tenant(
    session: Session,
    tenant: Tenant,
    tenant_b: Tenant,
    session_settings: Settings,
) -> None:
    admin_a = AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email="admin-a@t.test",
        password="password123",
        name="AdminA",
    )
    AuthRepository(session).bootstrap_admin(
        tenant_id=tenant_b.id,
        email="admin-b@t.test",
        password="password123",
        name="AdminB",
    )
    AgentSettingsRepository(session).upsert(
        tenant_b.id, greeting="Beta only", actor="seed"
    )
    token = _token_for(session_settings, admin_a, tenant)
    client = _client_for(session, session_settings, token=token)
    try:
        res = client.put(
            "/api/admin/agent-settings",
            json={"greeting": "Acme greeting", "assistant_name": "Riley"},
        )
        assert res.status_code == 200
        body = res.json()["settings"]
        assert body["tenant_id"] == str(tenant.id)
        assert body["greeting"] == "Acme greeting"
        assert body["profile_version"] == 1

        # Other tenant unchanged
        other = AgentSettingsRepository(session).get(tenant_b.id)
        assert other is not None
        assert other["greeting"] == "Beta only"
    finally:
        app.dependency_overrides.clear()


def test_other_tenant_admin_cannot_read_via_path(
    session: Session,
    tenant: Tenant,
    tenant_b: Tenant,
    session_settings: Settings,
) -> None:
    """Legacy path endpoints stay locked; no cross-tenant write surface."""
    admin_b = AuthRepository(session).bootstrap_admin(
        tenant_id=tenant_b.id,
        email="admin-b@t.test",
        password="password123",
        name="AdminB",
    )
    token = _token_for(session_settings, admin_b, tenant_b)
    client = _client_for(session, session_settings, token=token)
    try:
        # Even with a valid session cookie, legacy path PUT is rejected (401 auth_required
        # for the deprecated route — use /api/admin which is session-scoped).
        res = client.put(
            f"/tenants/{tenant.id}/agent-settings",
            json={"greeting": "cross tenant"},
        )
        assert res.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_profile_update_increments_version_and_audits(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    admin = AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email="admin@t.test",
        password="password123",
        name="Admin",
    )
    token = _token_for(session_settings, admin, tenant)
    client = _client_for(session, session_settings, token=token)
    try:
        first = client.put(
            "/api/admin/agent-settings",
            json={"greeting": "v1"},
        )
        assert first.status_code == 200
        assert first.json()["settings"]["profile_version"] == 1

        second = client.put(
            "/api/admin/agent-settings",
            json={"greeting": "v2"},
        )
        assert second.status_code == 200
        assert second.json()["settings"]["profile_version"] == 2

        events = session.scalars(
            select(TelephonyAuditEvent).where(
                TelephonyAuditEvent.tenant_id == tenant.id,
                TelephonyAuditEvent.action == "agent_settings_upserted",
            )
        ).all()
        assert len(events) >= 2
        latest = events[-1]
        assert latest.actor == "admin@t.test"
        assert "greeting" in (latest.payload_summary or {}).get("changed_fields", [])
        assert latest.payload_summary.get("profile_version") == 2
    finally:
        app.dependency_overrides.clear()


def test_empty_active_profile_fails_closed_on_internal_get(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    client = _client_for(session, session_settings)
    try:
        res = client.get(
            f"/internal/tenants/{tenant.id}/agent-profile",
            headers={"X-Internal-Token": session_settings.internal_service_token},
        )
        assert res.status_code == 404
        assert res.json()["detail"]["code"] == "agent_profile_missing"
    finally:
        app.dependency_overrides.clear()


def test_internal_token_platform_override(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    client = _client_for(session, session_settings)
    try:
        res = client.put(
            f"/internal/tenants/{tenant.id}/agent-settings",
            headers={"X-Internal-Token": session_settings.internal_service_token},
            json={"greeting": "platform override", "language": "en"},
        )
        assert res.status_code == 200
        assert res.json()["settings"]["greeting"] == "platform override"

        denied = client.put(
            f"/internal/tenants/{tenant.id}/agent-settings",
            json={"greeting": "no token"},
        )
        assert denied.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_rejects_tenant_id_in_body(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    admin = AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email="admin@t.test",
        password="password123",
        name="Admin",
    )
    token = _token_for(session_settings, admin, tenant)
    client = _client_for(session, session_settings, token=token)
    try:
        res = client.put(
            "/api/admin/agent-settings",
            json={
                "tenant_id": str(uuid.uuid4()),
                "greeting": "should fail",
            },
        )
        assert res.status_code == 422
    finally:
        app.dependency_overrides.clear()

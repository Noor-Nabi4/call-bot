"""Organization (tenant business) profile tests."""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.api.deps import db_dep, settings_dep
from callbot_platform.auth.repos import AuthRepository
from callbot_platform.config import Settings, get_settings
from callbot_platform.db.models import TelephonyAuditEvent, Tenant
from callbot_platform.main import app
from callbot_platform.organization import OrganizationError, OrganizationService
from callbot_platform.security.session import create_session_token


@pytest.fixture()
def session_settings() -> Settings:
    return Settings(
        session_secret="test-session-secret-organization-ok32",
        internal_service_token="internal-test-token",
        session_cookie_name="callbot_ops_session",
    )


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


def _token_for(settings: Settings, user: dict, tenant: Tenant) -> str:
    return create_session_token(
        settings=settings,
        user_id=uuid.UUID(user["id"]),
        tenant_id=tenant.id,
        role=user["role"],
        email=user["email"],
    )


def test_create_organization_defaults(session: Session, tenant: Tenant) -> None:
    assert tenant.currency == "USD"
    assert tenant.updated_at is not None
    profile = OrganizationService(session).get(tenant.id)
    assert profile["id"] == str(tenant.id)
    assert profile["industry"] is None
    assert profile["business_type"] is None
    assert profile["currency"] == "USD"


def test_update_organization_profile_and_validation(
    session: Session, tenant: Tenant
) -> None:
    svc = OrganizationService(session)
    saved = svc.update(
        tenant.id,
        actor="admin@t.test",
        name="Acme Comfort",
        industry="hvac",
        business_type="products and services",
        timezone="America/Chicago",
        currency="usd",
        country="us",
        state="TX",
        website="https://acme.example",
        phone="+1 555 000 1212",
        email="ops@acme.example",
    )
    assert saved["name"] == "Acme Comfort"
    assert saved["industry"] == "hvac"
    assert saved["industry_key"] == "hvac"
    assert saved["business_type"] == "products_and_services"
    assert saved["timezone"] == "America/Chicago"
    assert saved["currency"] == "USD"
    assert saved["country"] == "US"
    assert saved["phone"].startswith("+")
    assert saved["email"] == "ops@acme.example"

    events = list(
        session.scalars(
            select(TelephonyAuditEvent).where(
                TelephonyAuditEvent.tenant_id == tenant.id,
                TelephonyAuditEvent.action == "organization_updated",
            )
        )
    )
    assert len(events) == 1
    assert "name" in (events[0].payload_summary or {}).get("changed_fields", [])

    with pytest.raises(OrganizationError) as currency_err:
        svc.update(tenant.id, actor="admin@t.test", currency="ZZZ")
    assert currency_err.value.code == "invalid_currency"

    with pytest.raises(OrganizationError) as tz_err:
        svc.update(tenant.id, actor="admin@t.test", timezone="Not/AZone")
    assert tz_err.value.code == "invalid_timezone"

    with pytest.raises(OrganizationError) as web_err:
        svc.update(tenant.id, actor="admin@t.test", website="ftp://x.example")
    assert web_err.value.code == "invalid_website"

    with pytest.raises(OrganizationError) as type_err:
        svc.update(tenant.id, actor="admin@t.test", business_type="franchise")
    assert type_err.value.code == "invalid_business_type"


def test_create_rejects_duplicate_slug(session: Session, tenant: Tenant) -> None:
    svc = OrganizationService(session)
    with pytest.raises(OrganizationError) as exc:
        svc.create(name="Other", slug=tenant.slug, actor="internal")
    assert exc.value.code == "slug_taken"


def test_admin_patch_is_session_scoped(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    other = Tenant(name="Beta", slug=f"beta-{uuid.uuid4().hex[:8]}")
    session.add(other)
    session.flush()
    other.website = "https://beta.example"
    session.flush()

    admin = AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email="admin@t.test",
        password="password123",
        name="Admin",
    )
    token = _token_for(session_settings, admin, tenant)
    client = _client_for(session, session_settings, token=token)
    try:
        got = client.get("/api/admin/organization")
        assert got.status_code == 200
        assert got.json()["organization"]["id"] == str(tenant.id)

        patched = client.patch(
            "/api/admin/organization",
            json={"website": "https://acme.example", "currency": "CAD"},
        )
        assert patched.status_code == 200
        body = patched.json()["organization"]
        assert body["website"] == "https://acme.example"
        assert body["currency"] == "CAD"
        assert body["id"] == str(tenant.id)

        session.refresh(other)
        assert other.website == "https://beta.example"
        assert other.currency == "USD"
    finally:
        app.dependency_overrides.clear()


def test_dispatcher_cannot_edit_organization(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email="admin@t.test",
        password="password123",
        name="Admin",
    )
    dispatcher = AuthRepository(session).create_user(
        tenant.id,
        email="disp@t.test",
        password="password123",
        name="Disp",
        role="dispatcher",
        actor="test",
    )
    token = _token_for(session_settings, dispatcher, tenant)
    client = _client_for(session, session_settings, token=token)
    try:
        res = client.patch(
            "/api/admin/organization",
            json={"name": "Hacked"},
        )
        assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_rejects_tenant_id_override_in_body(
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
        res = client.patch(
            "/api/admin/organization",
            json={"tenant_id": str(uuid.uuid4()), "name": "Nope"},
        )
        assert res.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_unauthenticated_organization_returns_401(
    session: Session, session_settings: Settings
) -> None:
    client = _client_for(session, session_settings)
    try:
        res = client.get("/api/admin/organization")
        assert res.status_code == 401
    finally:
        app.dependency_overrides.clear()

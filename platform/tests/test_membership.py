"""Organization membership isolation and status tests."""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from callbot_platform.api.deps import db_dep, settings_dep
from callbot_platform.auth.repos import AuthError, AuthRepository
from callbot_platform.config import Settings, get_settings
from callbot_platform.db.models import Tenant
from callbot_platform.main import app
from callbot_platform.organization.errors import OrganizationError
from callbot_platform.organization.membership import (
    MEMBERSHIP_ACTIVE,
    MEMBERSHIP_DISABLED,
    MEMBERSHIP_INVITED,
)
from callbot_platform.organization.membership_repos import MembershipRepository
from callbot_platform.security.session import ROLE_DISPATCHER, create_session_token


@pytest.fixture()
def session_settings() -> Settings:
    return Settings(
        session_secret="test-session-secret-membership-ok32xx",
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


def test_membership_unique_email_and_status(session: Session, tenant: Tenant) -> None:
    auth = AuthRepository(session)
    members = MembershipRepository(session)
    admin = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="owner@t.test",
        password="password123",
        name="Owner",
    )
    assert admin["status"] == MEMBERSHIP_ACTIVE
    assert admin["organization_id"] == str(tenant.id)

    invited = members.create(
        tenant.id,
        email="csr@t.test",
        password="password123",
        name="CSR",
        role=ROLE_DISPATCHER,
        status=MEMBERSHIP_INVITED,
        actor=admin["email"],
    )
    assert invited["status"] == MEMBERSHIP_INVITED
    assert invited["is_active"] is False

    with pytest.raises(AuthError) as taken:
        auth.authenticate(
            tenant_slug=tenant.slug,
            email="csr@t.test",
            password="password123",
        )
    assert taken.value.code == "invalid_credentials"

    with pytest.raises(OrganizationError) as dup:
        members.create(
            tenant.id,
            email="csr@t.test",
            password="password123",
            name="CSR2",
            role=ROLE_DISPATCHER,
            actor=admin["email"],
        )
    assert dup.value.code == "email_taken"

    disabled = members.update(
        tenant.id,
        uuid.UUID(invited["id"]),
        actor_user_id=uuid.UUID(admin["id"]),
        actor_email=admin["email"],
        status=MEMBERSHIP_DISABLED,
    )
    assert disabled["status"] == MEMBERSHIP_DISABLED
    assert disabled["is_active"] is False


def test_membership_api_is_session_scoped(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    other = Tenant(name="Beta", slug=f"beta-{uuid.uuid4().hex[:8]}")
    session.add(other)
    session.flush()
    auth = AuthRepository(session)
    admin_a = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="a@t.test",
        password="password123",
        name="A",
    )
    admin_b = auth.bootstrap_admin(
        tenant_id=other.id,
        email="b@t.test",
        password="password123",
        name="B",
    )
    member_b = auth.create_user(
        other.id,
        email="tech@b.test",
        password="password123",
        name="Tech B",
        role="technician",
        actor=admin_b["email"],
    )
    token = _token_for(session_settings, admin_a, tenant)
    client = _client_for(session, session_settings, token=token)
    try:
        listed = client.get("/api/admin/organization/members")
        assert listed.status_code == 200
        emails = {m["email"] for m in listed.json()["members"]}
        assert "a@t.test" in emails
        assert "b@t.test" not in emails
        assert "tech@b.test" not in emails

        leaked = client.get(f"/api/admin/organization/members/{member_b['id']}")
        assert leaked.status_code == 404

        patched = client.patch(
            f"/api/admin/organization/members/{member_b['id']}",
            json={"status": MEMBERSHIP_DISABLED},
        )
        assert patched.status_code == 404

        created = client.post(
            "/api/admin/organization/members",
            json={
                "email": "disp@t.test",
                "password": "password123",
                "name": "Dispatcher",
                "role": ROLE_DISPATCHER,
            },
        )
        assert created.status_code == 200
        body = created.json()["member"]
        assert body["organization_id"] == str(tenant.id)
        assert body["role"] == ROLE_DISPATCHER
        assert body["status"] == MEMBERSHIP_ACTIVE
    finally:
        app.dependency_overrides.clear()


def test_membership_rejects_org_override_and_dispatcher(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    auth = AuthRepository(session)
    auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="admin@t.test",
        password="password123",
        name="Admin",
    )
    dispatcher = auth.create_user(
        tenant.id,
        email="disp@t.test",
        password="password123",
        name="Disp",
        role=ROLE_DISPATCHER,
        actor="test",
    )

    admin_user = AuthRepository(session).authenticate(
        tenant_slug=tenant.slug,
        email="admin@t.test",
        password="password123",
    )
    admin_token = _token_for(session_settings, admin_user, tenant)
    client = _client_for(session, session_settings, token=admin_token)
    try:
        res = client.post(
            "/api/admin/organization/members",
            json={
                "email": "x@t.test",
                "password": "password123",
                "name": "X",
                "role": ROLE_DISPATCHER,
                "tenant_id": str(uuid.uuid4()),
            },
        )
        assert res.status_code == 422
    finally:
        app.dependency_overrides.clear()

    disp_token = _token_for(session_settings, dispatcher, tenant)
    client = _client_for(session, session_settings, token=disp_token)
    try:
        res = client.get("/api/admin/organization/members")
        assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()

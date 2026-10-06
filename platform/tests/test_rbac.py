"""Organization-managed RBAC tests."""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from callbot_platform.api.deps import db_dep, settings_dep
from callbot_platform.auth.repos import AuthRepository
from callbot_platform.config import Settings, get_settings
from callbot_platform.db.models import Tenant
from callbot_platform.main import app
from callbot_platform.rbac.catalog import (
    SYSTEM_ROLE_ADMIN,
    SYSTEM_ROLE_AI_AGENT,
    SYSTEM_ROLE_OWNER,
)
from callbot_platform.rbac.errors import RbacError
from callbot_platform.rbac.repos import RoleRepository
from callbot_platform.rbac.seed import (
    backfill_tenant_rbac,
    ensure_system_roles_for_tenant,
)
from callbot_platform.rbac.service import AuthorizationService, ResourceContext
from callbot_platform.security.session import ROLE_DISPATCHER, create_session_token


@pytest.fixture()
def session_settings() -> Settings:
    return Settings(
        session_secret="test-session-secret-rbac-ok32xxxxxxxx",
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


def test_legacy_roles_migrate_to_member_roles(session: Session, tenant: Tenant) -> None:
    auth = AuthRepository(session)
    owner = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="owner@t.test",
        password="password123",
        name="Owner",
    )
    disp = auth.create_user(
        tenant.id,
        email="disp@t.test",
        password="password123",
        name="Disp",
        role=ROLE_DISPATCHER,
        actor=owner["email"],
    )
    tech = auth.create_user(
        tenant.id,
        email="tech@t.test",
        password="password123",
        name="Tech",
        role="technician",
        actor=owner["email"],
    )
    authz = AuthorizationService(session)
    assert SYSTEM_ROLE_OWNER in authz.member_role_names(
        tenant.id, uuid.UUID(owner["id"])
    )
    assert "Dispatcher" in authz.member_role_names(tenant.id, uuid.UUID(disp["id"]))
    assert "Technician" in authz.member_role_names(tenant.id, uuid.UUID(tech["id"]))
    assert authz.has_permission(tenant.id, uuid.UUID(owner["id"]), "roles.assign")
    assert authz.has_permission(tenant.id, uuid.UUID(disp["id"]), "jobs.assign")
    assert not authz.has_permission(tenant.id, uuid.UUID(tech["id"]), "roles.assign")


def test_technician_assigned_scope(session: Session, tenant: Tenant) -> None:
    auth = AuthRepository(session)
    owner = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="owner@t.test",
        password="password123",
        name="Owner",
    )
    tech = auth.create_user(
        tenant.id,
        email="tech@t.test",
        password="password123",
        name="Tech",
        role="technician",
        actor=owner["email"],
    )
    tech_id = uuid.UUID(tech["id"])
    authz = AuthorizationService(session)
    # Fail-closed: ASSIGNED grants require ResourceContext.
    assert not authz.has_permission(tenant.id, tech_id, "jobs.read")
    assert authz.list_access_mode(tenant.id, tech_id, "jobs.read") == "assigned"
    assert not authz.has_permission(
        tenant.id,
        tech_id,
        "jobs.read",
        resource=ResourceContext(
            tenant_id=tenant.id,
            assigned_technician_user_id=uuid.uuid4(),
        ),
    )
    assert authz.has_permission(
        tenant.id,
        tech_id,
        "jobs.read",
        resource=ResourceContext(
            tenant_id=tenant.id,
            assigned_technician_user_id=tech_id,
        ),
    )


def test_cross_tenant_role_isolation(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    other = Tenant(name="Beta", slug=f"beta-{uuid.uuid4().hex[:8]}")
    session.add(other)
    session.flush()
    auth = AuthRepository(session)
    a = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="a@t.test",
        password="password123",
        name="A",
    )
    b = auth.bootstrap_admin(
        tenant_id=other.id,
        email="b@t.test",
        password="password123",
        name="B",
    )
    roles_b = RoleRepository(session).list_roles(other.id)
    role_b_id = roles_b[0]["id"]

    token = _token_for(session_settings, a, tenant)
    client = _client_for(session, session_settings, token=token)
    try:
        listed = client.get("/api/admin/organization/roles")
        assert listed.status_code == 200
        names = {r["name"] for r in listed.json()["roles"]}
        assert SYSTEM_ROLE_OWNER in names
        assert all(
            r["organization_id"] == str(tenant.id) for r in listed.json()["roles"]
        )

        leaked = client.get(f"/api/admin/organization/roles/{role_b_id}")
        assert leaked.status_code == 404

        assign = client.post(
            f"/api/admin/organization/members/{b['id']}/roles",
            json={"role_id": role_b_id},
        )
        assert assign.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_admin_cannot_self_assign_owner(session: Session, tenant: Tenant) -> None:
    auth = AuthRepository(session)
    owner = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="owner@t.test",
        password="password123",
        name="Owner",
    )
    admin = auth.create_user(
        tenant.id,
        email="admin@t.test",
        password="password123",
        name="Admin",
        role="admin",
        actor=owner["email"],
    )
    roles = {r["name"]: r for r in RoleRepository(session).list_roles(tenant.id)}
    owner_role_id = uuid.UUID(roles[SYSTEM_ROLE_OWNER]["id"])
    with pytest.raises(RbacError) as exc:
        RoleRepository(session).assign_role(
            tenant.id,
            member_id=uuid.UUID(admin["id"]),
            role_id=owner_role_id,
            actor=admin["email"],
            actor_user_id=uuid.UUID(admin["id"]),
        )
    assert exc.value.code in {"owner_protected", "privilege_escalation"}


def test_cannot_remove_last_owner(session: Session, tenant: Tenant) -> None:
    auth = AuthRepository(session)
    owner = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="owner@t.test",
        password="password123",
        name="Owner",
    )
    roles = {r["name"]: r for r in RoleRepository(session).list_roles(tenant.id)}
    owner_role_id = uuid.UUID(roles[SYSTEM_ROLE_OWNER]["id"])
    with pytest.raises(RbacError) as exc:
        RoleRepository(session).remove_role(
            tenant.id,
            member_id=uuid.UUID(owner["id"]),
            role_id=owner_role_id,
            actor=owner["email"],
            actor_user_id=uuid.UUID(owner["id"]),
        )
    assert exc.value.code == "last_owner"


def test_custom_role_cannot_invent_permissions(
    session: Session, tenant: Tenant
) -> None:
    auth = AuthRepository(session)
    owner = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="owner@t.test",
        password="password123",
        name="Owner",
    )
    with pytest.raises(RbacError) as exc:
        RoleRepository(session).create_role(
            tenant.id,
            name="Sales Rep",
            description="Custom",
            permissions=[{"key": "spaceship.launch", "scope": "ALL_ORGANIZATION"}],
            actor=owner["email"],
            actor_user_id=uuid.UUID(owner["id"]),
        )
    assert exc.value.code == "unknown_permission"


def test_ai_tool_authorization(session: Session, tenant: Tenant) -> None:
    ensure_system_roles_for_tenant(session, tenant.id)
    authz = AuthorizationService(session)
    authz.check_ai_tool(tenant.id, "crm")
    # Revoke CRM tool permission from AI Agent
    roles = {r["name"]: r for r in RoleRepository(session).list_roles(tenant.id)}
    ai_role = RoleRepository(session).get_role(
        tenant.id, uuid.UUID(roles[SYSTEM_ROLE_AI_AGENT]["id"])
    )
    remaining = [
        {"key": p["key"], "scope": p["scope"]}
        for p in ai_role["permissions"]
        if p["key"] != "ai.tools_crm"
    ]
    # Need an owner actor to update AI Agent permissions
    owner = AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email="owner@t.test",
        password="password123",
        name="Owner",
    )
    RoleRepository(session).update_role(
        tenant.id,
        uuid.UUID(roles[SYSTEM_ROLE_AI_AGENT]["id"]),
        actor=owner["email"],
        actor_user_id=uuid.UUID(owner["id"]),
        permissions=remaining,
    )
    with pytest.raises(RbacError) as exc:
        AuthorizationService(session).check_ai_tool(tenant.id, "crm")
    assert exc.value.code == "permission_denied"


def test_ai_crm_route_denied_without_permission(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    ensure_system_roles_for_tenant(session, tenant.id)
    owner = AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email="owner@t.test",
        password="password123",
        name="Owner",
    )
    roles = {r["name"]: r for r in RoleRepository(session).list_roles(tenant.id)}
    RoleRepository(session).update_role(
        tenant.id,
        uuid.UUID(roles[SYSTEM_ROLE_AI_AGENT]["id"]),
        actor=owner["email"],
        actor_user_id=uuid.UUID(owner["id"]),
        permissions=[
            {"key": "ai.tools_scheduling", "scope": "ALL_ORGANIZATION"},
        ],
    )
    client = _client_for(session, session_settings)
    try:
        res = client.post(
            "/internal/crm/customers/lookup",
            headers={"X-Internal-Token": session_settings.internal_service_token},
            json={"tenant_id": str(tenant.id), "phone": "+15551234567"},
        )
        assert res.status_code == 403
        assert res.json()["detail"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()


def test_roles_api_and_member_assignment(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    auth = AuthRepository(session)
    owner = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="owner@t.test",
        password="password123",
        name="Owner",
    )
    member = auth.create_user(
        tenant.id,
        email="disp@t.test",
        password="password123",
        name="Disp",
        role=ROLE_DISPATCHER,
        actor=owner["email"],
    )
    token = _token_for(session_settings, owner, tenant)
    client = _client_for(session, session_settings, token=token)
    try:
        created = client.post(
            "/api/admin/organization/roles",
            json={
                "name": "Office Manager",
                "description": "Custom ops",
                "permissions": [
                    {"key": "customers.read", "scope": "ALL_ORGANIZATION"},
                    {"key": "team.read", "scope": "ALL_ORGANIZATION"},
                ],
            },
        )
        assert created.status_code == 200
        role_id = created.json()["role"]["id"]

        assigned = client.post(
            f"/api/admin/organization/members/{member['id']}/roles",
            json={"role_id": role_id},
        )
        assert assigned.status_code == 200
        names = {r["name"] for r in assigned.json()["roles"]}
        assert "Office Manager" in names
        assert "Dispatcher" in names

        catalog = client.get("/api/admin/organization/permissions")
        assert catalog.status_code == 200
        assert any(p["key"] == "customers.read" for p in catalog.json()["permissions"])
    finally:
        app.dependency_overrides.clear()


def test_legacy_role_change_replaces_primary_system_role(
    session: Session, tenant: Tenant
) -> None:
    auth = AuthRepository(session)
    owner = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="owner@t.test",
        password="password123",
        name="Owner",
    )
    member = auth.create_user(
        tenant.id,
        email="disp@t.test",
        password="password123",
        name="Disp",
        role=ROLE_DISPATCHER,
        actor=owner["email"],
    )
    auth.update_user_admin(
        tenant.id,
        uuid.UUID(member["id"]),
        actor_user_id=uuid.UUID(owner["id"]),
        actor_email=owner["email"],
        role="technician",
    )
    names = set(
        AuthorizationService(session).member_role_names(
            tenant.id, uuid.UUID(member["id"])
        )
    )
    assert "Technician" in names
    assert "Dispatcher" not in names


def test_cannot_demote_owner_via_legacy_role(session: Session, tenant: Tenant) -> None:
    from callbot_platform.auth.repos import AuthError

    auth = AuthRepository(session)
    owner = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="owner@t.test",
        password="password123",
        name="Owner",
    )
    # Second admin so last_admin check does not fire first
    auth.create_user(
        tenant.id,
        email="admin2@t.test",
        password="password123",
        name="Admin2",
        role="admin",
        actor=owner["email"],
    )
    with pytest.raises(AuthError) as exc:
        auth.update_user_admin(
            tenant.id,
            uuid.UUID(owner["id"]),
            actor_user_id=uuid.UUID(owner["id"]),
            actor_email=owner["email"],
            role="dispatcher",
        )
    assert exc.value.code == "owner_protected"


def test_backfill_idempotent(session: Session, tenant: Tenant) -> None:
    auth = AuthRepository(session)
    auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="owner@t.test",
        password="password123",
        name="Owner",
    )
    backfill_tenant_rbac(session, tenant.id)
    backfill_tenant_rbac(session, tenant.id)
    roles = RoleRepository(session).list_roles(tenant.id)
    assert len([r for r in roles if r["name"] == SYSTEM_ROLE_ADMIN]) == 1
    assert len([r for r in roles if r["name"] == SYSTEM_ROLE_OWNER]) == 1


def test_legacy_role_string_not_authoritative(session: Session, tenant: Tenant) -> None:
    """Changing tenant_users.role alone must not grant permissions."""
    auth = AuthRepository(session)
    owner = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="owner@t.test",
        password="password123",
        name="Owner",
    )
    tech = auth.create_user(
        tenant.id,
        email="tech@t.test",
        password="password123",
        name="Tech",
        role="technician",
        actor=owner["email"],
    )
    from callbot_platform.db.models.jobs import TenantUser

    row = session.get(TenantUser, uuid.UUID(tech["id"]))
    assert row is not None
    row.role = "admin"
    session.flush()
    authz = AuthorizationService(session)
    assert not authz.has_permission(tenant.id, uuid.UUID(tech["id"]), "roles.assign")
    assert authz.list_access_mode(tenant.id, uuid.UUID(tech["id"]), "jobs.read") == (
        "assigned"
    )


def test_fail_closed_scopes(session: Session, tenant: Tenant) -> None:
    auth = AuthRepository(session)
    owner = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="owner@t.test",
        password="password123",
        name="Owner",
    )
    tech = auth.create_user(
        tenant.id,
        email="tech@t.test",
        password="password123",
        name="Tech",
        role="technician",
        actor=owner["email"],
    )
    tech_id = uuid.UUID(tech["id"])
    authz = AuthorizationService(session)
    other = uuid.uuid4()

    # ASSIGNED
    assert not authz.has_permission(tenant.id, tech_id, "jobs.update")
    assert not authz.has_permission(
        tenant.id,
        tech_id,
        "jobs.update",
        resource=ResourceContext(tenant_id=tenant.id, assigned_technician_user_id=None),
    )
    assert not authz.has_permission(
        tenant.id,
        tech_id,
        "jobs.update",
        resource=ResourceContext(
            tenant_id=tenant.id, assigned_technician_user_id=other
        ),
    )
    assert authz.has_permission(
        tenant.id,
        tech_id,
        "jobs.update",
        resource=ResourceContext(
            tenant_id=tenant.id, assigned_technician_user_id=tech_id
        ),
    )
    assert not authz.has_permission(
        tenant.id,
        tech_id,
        "jobs.update",
        resource=ResourceContext(
            tenant_id=uuid.uuid4(), assigned_technician_user_id=tech_id
        ),
    )

    # OWN — technician has no OWN grants; org-wide owner does without resource.
    assert authz.has_permission(tenant.id, uuid.UUID(owner["id"]), "jobs.update")
    owner_id = uuid.UUID(owner["id"])
    # Force OWN-only evaluation via ResourceContext on a permission the tech lacks OWN for
    assert not authz.has_permission(
        tenant.id,
        tech_id,
        "jobs.update",
        resource=ResourceContext(tenant_id=tenant.id, owner_user_id=owner_id),
    )

    # TEAM missing context
    assert not authz.has_permission(
        tenant.id,
        tech_id,
        "jobs.update",
        resource=ResourceContext(tenant_id=tenant.id, team_user_ids=None),
    )


def test_disabled_member_has_no_permissions(session: Session, tenant: Tenant) -> None:
    auth = AuthRepository(session)
    owner = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="owner@t.test",
        password="password123",
        name="Owner",
    )
    admin = auth.create_user(
        tenant.id,
        email="admin@t.test",
        password="password123",
        name="Admin",
        role="admin",
        actor=owner["email"],
    )
    auth.update_user_admin(
        tenant.id,
        uuid.UUID(admin["id"]),
        actor_user_id=uuid.UUID(owner["id"]),
        actor_email=owner["email"],
        is_active=False,
    )
    authz = AuthorizationService(session)
    assert not authz.has_permission(tenant.id, uuid.UUID(admin["id"]), "team.manage")


def test_billing_permission_for_admin(session: Session, tenant: Tenant) -> None:
    auth = AuthRepository(session)
    owner = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="owner@t.test",
        password="password123",
        name="Owner",
    )
    admin = auth.create_user(
        tenant.id,
        email="admin@t.test",
        password="password123",
        name="Admin",
        role="admin",
        actor=owner["email"],
    )
    authz = AuthorizationService(session)
    assert authz.has_permission(tenant.id, uuid.UUID(admin["id"]), "billing.read")
    assert authz.has_permission(tenant.id, uuid.UUID(admin["id"]), "billing.manage")
    assert authz.has_permission(tenant.id, uuid.UUID(owner["id"]), "billing.manage")


def test_jobs_list_assigned_mode_api(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    auth = AuthRepository(session)
    owner = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="owner@t.test",
        password="password123",
        name="Owner",
    )
    tech = auth.create_user(
        tenant.id,
        email="tech@t.test",
        password="password123",
        name="Tech",
        role="technician",
        actor=owner["email"],
        phone="+15550001111",
    )
    token = _token_for(session_settings, tech, tenant)
    client = _client_for(session, session_settings, token=token)
    try:
        res = client.get("/api/jobs")
        assert res.status_code == 200
        assert res.json()["jobs"] == []
    finally:
        app.dependency_overrides.clear()

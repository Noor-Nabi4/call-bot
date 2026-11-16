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
    # Isolate from platform/.env.local (e.g. REQUIRE_CALL_SCOPE=true).
    return Settings(
        _env_file=None,
        session_secret="test-session-secret-rbac-ok32xxxxxxxx",
        internal_service_token="internal-test-token",
        session_cookie_name="callbot_ops_session",
        require_call_scope=False,
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


def test_reconcile_preserves_revocation_custom_role_and_idempotent(
    session: Session, tenant: Tenant
) -> None:
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    from callbot_platform.rbac.catalog import SYSTEM_ROLE_ADMIN
    from callbot_platform.rbac.models import (
        OrganizationRole,
        Permission,
        RolePermission,
        RolePermissionTombstone,
    )
    from callbot_platform.rbac.reconcile import reconcile_system_roles_for_tenant
    from callbot_platform.rbac.seed import ensure_system_roles_for_tenant

    auth = AuthRepository(session)
    owner = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="owner@t.test",
        password="password123",
        name="Owner",
    )
    owner_id = uuid.UUID(owner["id"])
    ensure_system_roles_for_tenant(session, tenant.id)

    admin = session.scalar(
        select(OrganizationRole).where(
            OrganizationRole.tenant_id == tenant.id,
            OrganizationRole.name == SYSTEM_ROLE_ADMIN,
        )
    )
    assert admin is not None
    billing = session.scalar(
        select(Permission).where(
            Permission.resource == "billing", Permission.action == "manage"
        )
    )
    assert billing is not None
    rp = session.scalar(
        select(RolePermission).where(
            RolePermission.role_id == admin.id,
            RolePermission.permission_id == billing.id,
        )
    )
    assert rp is not None
    session.delete(rp)
    session.add(RolePermissionTombstone(role_id=admin.id, permission_id=billing.id))

    jobs_read = session.scalar(
        select(Permission).where(
            Permission.resource == "jobs", Permission.action == "read"
        )
    )
    assert jobs_read is not None
    jobs_rp = session.scalar(
        select(RolePermission).where(
            RolePermission.role_id == admin.id,
            RolePermission.permission_id == jobs_read.id,
        )
    )
    assert jobs_rp is not None
    jobs_rp.scope = "OWN"
    jobs_rp.source = "ORG_CUSTOM"
    session.flush()

    custom = RoleRepository(session).create_role(
        tenant.id,
        name="Custom Role A",
        description="limited",
        actor=owner["email"],
        actor_user_id=owner_id,
        permissions=[
            {"key": "customers.read", "scope": "ALL_ORGANIZATION"},
            {"key": "jobs.read", "scope": "ALL_ORGANIZATION"},
        ],
    )
    custom_id = uuid.UUID(custom["id"])

    first = reconcile_system_roles_for_tenant(session, tenant.id, actor="test")
    second = reconcile_system_roles_for_tenant(session, tenant.id, actor="test")
    assert second["added_count"] == 0

    restored = session.scalar(
        select(RolePermission).where(
            RolePermission.role_id == admin.id,
            RolePermission.permission_id == billing.id,
        )
    )
    assert restored is None

    jobs_rp2 = session.scalar(
        select(RolePermission).where(
            RolePermission.role_id == admin.id,
            RolePermission.permission_id == jobs_read.id,
        )
    )
    assert jobs_rp2 is not None
    assert jobs_rp2.scope == "OWN"
    assert jobs_rp2.source == "ORG_CUSTOM"

    custom_after = RoleRepository(session).get_role(tenant.id, custom_id)
    custom_keys_after = {p["key"] for p in custom_after["permissions"]}
    assert custom_keys_after == {"customers.read", "jobs.read"}
    assert first["tenant_id"] == str(tenant.id)


def test_legacy_role_without_member_roles_denies(
    session: Session, tenant: Tenant
) -> None:
    """Legacy role string with no member_roles grants nothing."""
    from sqlalchemy import select

    from callbot_platform.db.models.jobs import TenantUser
    from callbot_platform.rbac.models import MemberRole

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
    admin_id = uuid.UUID(admin["id"])
    for link in list(
        session.scalars(select(MemberRole).where(MemberRole.tenant_user_id == admin_id))
    ):
        session.delete(link)
    user = session.get(TenantUser, admin_id)
    assert user is not None
    user.role = "admin"
    session.flush()

    authz = AuthorizationService(session)
    assert not authz.has_permission(tenant.id, admin_id, "billing.manage")
    assert not authz.has_permission(tenant.id, admin_id, "team.manage")


def test_me_includes_effective_permissions(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    auth = AuthRepository(session)
    owner = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="owner@t.test",
        password="password123",
        name="Owner",
    )
    token = _token_for(session_settings, owner, tenant)
    client = _client_for(session, session_settings, token=token)
    try:
        me = client.get("/auth/me")
        assert me.status_code == 200
        body = me.json()["user"]
        assert "permissions" in body
        assert "roles" in body
        keys = {p["key"] for p in body["permissions"]}
        assert "roles.assign" in keys
        assert any(r["name"] == SYSTEM_ROLE_OWNER for r in body["roles"])

        perms = client.get("/auth/me/permissions")
        assert perms.status_code == 200
        assert "permissions" in perms.json()
        assert "roles" in perms.json()
    finally:
        app.dependency_overrides.clear()


def test_reconcile_adds_missing_default_without_duplicating(
    session: Session, tenant: Tenant
) -> None:
    from sqlalchemy import select

    from callbot_platform.rbac.catalog import SYSTEM_ROLE_DISPATCHER
    from callbot_platform.rbac.models import (
        OrganizationRole,
        Permission,
        RolePermission,
    )
    from callbot_platform.rbac.reconcile import reconcile_system_roles_for_tenant
    from callbot_platform.rbac.seed import ensure_system_roles_for_tenant

    auth = AuthRepository(session)
    auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="owner@t.test",
        password="password123",
        name="Owner",
    )
    ensure_system_roles_for_tenant(session, tenant.id)
    dispatcher = session.scalar(
        select(OrganizationRole).where(
            OrganizationRole.tenant_id == tenant.id,
            OrganizationRole.name == SYSTEM_ROLE_DISPATCHER,
        )
    )
    assert dispatcher is not None
    knowledge = session.scalar(
        select(Permission).where(
            Permission.resource == "knowledge", Permission.action == "manage"
        )
    )
    assert knowledge is not None
    existing = session.scalar(
        select(RolePermission).where(
            RolePermission.role_id == dispatcher.id,
            RolePermission.permission_id == knowledge.id,
        )
    )
    if existing is not None:
        session.delete(existing)
        session.flush()

    result = reconcile_system_roles_for_tenant(session, tenant.id, actor="test")
    assert any(
        a["permission"] == "knowledge.manage" and a["role"] == SYSTEM_ROLE_DISPATCHER
        for a in result["added"]
    )
    again = reconcile_system_roles_for_tenant(session, tenant.id, actor="test")
    assert again["added_count"] == 0
    count = len(
        list(
            session.scalars(
                select(RolePermission).where(
                    RolePermission.role_id == dispatcher.id,
                    RolePermission.permission_id == knowledge.id,
                )
            )
        )
    )
    assert count == 1


def test_freeze_gap_then_reconcile_preserves_absence(
    session: Session, tenant: Tenant
) -> None:
    """Scenario A: pre-existing gap becomes tombstone and stays missing."""
    from sqlalchemy import select

    from callbot_platform.rbac.catalog import SYSTEM_ROLE_ADMIN
    from callbot_platform.rbac.models import (
        OrganizationRole,
        Permission,
        RolePermission,
        RolePermissionTombstone,
    )
    from callbot_platform.rbac.reconcile import (
        freeze_system_role_gaps_for_tenant,
        reconcile_system_roles_for_tenant,
    )
    from callbot_platform.rbac.seed import ensure_system_roles_for_tenant

    auth = AuthRepository(session)
    auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="owner@t.test",
        password="password123",
        name="Owner",
    )
    ensure_system_roles_for_tenant(session, tenant.id)
    admin = session.scalar(
        select(OrganizationRole).where(
            OrganizationRole.tenant_id == tenant.id,
            OrganizationRole.name == SYSTEM_ROLE_ADMIN,
        )
    )
    assert admin is not None
    billing = session.scalar(
        select(Permission).where(
            Permission.resource == "billing", Permission.action == "manage"
        )
    )
    assert billing is not None
    rp = session.scalar(
        select(RolePermission).where(
            RolePermission.role_id == admin.id,
            RolePermission.permission_id == billing.id,
        )
    )
    if rp is not None:
        session.delete(rp)
        session.flush()

    frozen = freeze_system_role_gaps_for_tenant(session, tenant.id)
    assert frozen >= 1
    tomb = session.scalar(
        select(RolePermissionTombstone).where(
            RolePermissionTombstone.role_id == admin.id,
            RolePermissionTombstone.permission_id == billing.id,
        )
    )
    assert tomb is not None
    reconcile_system_roles_for_tenant(session, tenant.id, actor="test")
    restored = session.scalar(
        select(RolePermission).where(
            RolePermission.role_id == admin.id,
            RolePermission.permission_id == billing.id,
        )
    )
    assert restored is None


def test_revoke_regrant_revoke_tombstone_lifecycle(
    session: Session, tenant: Tenant
) -> None:
    """Scenarios C/D: revoke → tombstone; re-grant → clear; revoke again → tombstone."""
    from sqlalchemy import select

    from callbot_platform.rbac.catalog import SYSTEM_ROLE_ADMIN
    from callbot_platform.rbac.models import (
        OrganizationRole,
        Permission,
        RolePermission,
        RolePermissionTombstone,
    )
    from callbot_platform.rbac.reconcile import reconcile_system_roles_for_tenant
    from callbot_platform.rbac.seed import ensure_system_roles_for_tenant

    auth = AuthRepository(session)
    owner = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="owner@t.test",
        password="password123",
        name="Owner",
    )
    owner_id = uuid.UUID(owner["id"])
    ensure_system_roles_for_tenant(session, tenant.id)
    admin = session.scalar(
        select(OrganizationRole).where(
            OrganizationRole.tenant_id == tenant.id,
            OrganizationRole.name == SYSTEM_ROLE_ADMIN,
        )
    )
    assert admin is not None
    customers = session.scalar(
        select(Permission).where(
            Permission.resource == "customers", Permission.action == "read"
        )
    )
    assert customers is not None

    # Collect current Admin permissions minus customers.read
    current = RoleRepository(session).get_role(tenant.id, admin.id)
    remaining = [
        {"key": p["key"], "scope": p["scope"]}
        for p in current["permissions"]
        if p["key"] != "customers.read"
    ]
    RoleRepository(session).update_role(
        tenant.id,
        admin.id,
        actor=owner["email"],
        actor_user_id=owner_id,
        permissions=remaining,
    )
    assert (
        session.scalar(
            select(RolePermission).where(
                RolePermission.role_id == admin.id,
                RolePermission.permission_id == customers.id,
            )
        )
        is None
    )
    assert (
        session.scalar(
            select(RolePermissionTombstone).where(
                RolePermissionTombstone.role_id == admin.id,
                RolePermissionTombstone.permission_id == customers.id,
            )
        )
        is not None
    )
    reconcile_system_roles_for_tenant(session, tenant.id, actor="test")
    assert (
        session.scalar(
            select(RolePermission).where(
                RolePermission.role_id == admin.id,
                RolePermission.permission_id == customers.id,
            )
        )
        is None
    )

    # Re-grant
    RoleRepository(session).update_role(
        tenant.id,
        admin.id,
        actor=owner["email"],
        actor_user_id=owner_id,
        permissions=[
            *remaining,
            {"key": "customers.read", "scope": "ALL_ORGANIZATION"},
        ],
    )
    rp = session.scalar(
        select(RolePermission).where(
            RolePermission.role_id == admin.id,
            RolePermission.permission_id == customers.id,
        )
    )
    assert rp is not None
    assert rp.source == "ORG_CUSTOM"
    assert (
        session.scalar(
            select(RolePermissionTombstone).where(
                RolePermissionTombstone.role_id == admin.id,
                RolePermissionTombstone.permission_id == customers.id,
            )
        )
        is None
    )
    reconcile_system_roles_for_tenant(session, tenant.id, actor="test")
    assert (
        session.scalar(
            select(RolePermission).where(
                RolePermission.role_id == admin.id,
                RolePermission.permission_id == customers.id,
            )
        )
        is not None
    )

    # Revoke again after ORG_CUSTOM re-grant — must still tombstone
    RoleRepository(session).update_role(
        tenant.id,
        admin.id,
        actor=owner["email"],
        actor_user_id=owner_id,
        permissions=remaining,
    )
    assert (
        session.scalar(
            select(RolePermissionTombstone).where(
                RolePermissionTombstone.role_id == admin.id,
                RolePermissionTombstone.permission_id == customers.id,
            )
        )
        is not None
    )
    for _ in range(3):
        result = reconcile_system_roles_for_tenant(session, tenant.id, actor="test")
        assert result["added_count"] == 0
    assert (
        session.scalar(
            select(RolePermission).where(
                RolePermission.role_id == admin.id,
                RolePermission.permission_id == customers.id,
            )
        )
        is None
    )


def test_authz_cache_invalidated_on_permission_revoke(
    session: Session, tenant: Tenant
) -> None:
    from callbot_platform.rbac.catalog import SYSTEM_ROLE_ADMIN
    from callbot_platform.rbac.models import OrganizationRole
    from callbot_platform.rbac.seed import ensure_system_roles_for_tenant
    from sqlalchemy import select

    auth = AuthRepository(session)
    owner = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="owner@t.test",
        password="password123",
        name="Owner",
    )
    admin_user = auth.create_user(
        tenant.id,
        email="admin@t.test",
        password="password123",
        name="Admin",
        role="admin",
        actor=owner["email"],
    )
    admin_id = uuid.UUID(admin_user["id"])
    owner_id = uuid.UUID(owner["id"])
    ensure_system_roles_for_tenant(session, tenant.id)
    authz = AuthorizationService(session)
    assert authz.has_permission(tenant.id, admin_id, "billing.manage")

    admin_role = session.scalar(
        select(OrganizationRole).where(
            OrganizationRole.tenant_id == tenant.id,
            OrganizationRole.name == SYSTEM_ROLE_ADMIN,
        )
    )
    assert admin_role is not None
    current = RoleRepository(session).get_role(tenant.id, admin_role.id)
    remaining = [
        {"key": p["key"], "scope": p["scope"]}
        for p in current["permissions"]
        if p["key"] != "billing.manage"
    ]
    RoleRepository(session).update_role(
        tenant.id,
        admin_role.id,
        actor=owner["email"],
        actor_user_id=owner_id,
        permissions=remaining,
    )
    assert not authz.has_permission(tenant.id, admin_id, "billing.manage")


def test_reconcile_endpoint_is_tenant_scoped(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    other = Tenant(name="Other", slug=f"other-{uuid.uuid4().hex[:8]}")
    session.add(other)
    session.flush()
    auth = AuthRepository(session)
    a = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="a@t.test",
        password="password123",
        name="A",
    )
    auth.bootstrap_admin(
        tenant_id=other.id,
        email="b@t.test",
        password="password123",
        name="B",
    )
    token = _token_for(session_settings, a, tenant)
    client = _client_for(session, session_settings, token=token)
    try:
        res = client.post("/api/admin/organization/reconcile")
        assert res.status_code == 200
        body = res.json()
        assert body["tenant_id"] == str(tenant.id)
        assert "added_count" in body
    finally:
        app.dependency_overrides.clear()


def _admin_role_and_perm(
    session: Session, tenant: Tenant, *, resource: str, action: str
):
    from sqlalchemy import select

    from callbot_platform.rbac.catalog import SYSTEM_ROLE_ADMIN
    from callbot_platform.rbac.models import OrganizationRole, Permission
    from callbot_platform.rbac.seed import ensure_system_roles_for_tenant

    ensure_system_roles_for_tenant(session, tenant.id)
    role = session.scalar(
        select(OrganizationRole).where(
            OrganizationRole.tenant_id == tenant.id,
            OrganizationRole.name == SYSTEM_ROLE_ADMIN,
        )
    )
    perm = session.scalar(
        select(Permission).where(
            Permission.resource == resource, Permission.action == action
        )
    )
    assert role is not None and perm is not None
    return role, perm


def test_billing_manage_full_tombstone_lifecycle(
    session: Session, tenant: Tenant
) -> None:
    """States 1–6 for Admin.billing.manage (catalog default)."""
    from sqlalchemy import select

    from callbot_platform.rbac.models import RolePermission, RolePermissionTombstone
    from callbot_platform.rbac.reconcile import reconcile_system_roles_for_tenant

    auth = AuthRepository(session)
    owner = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="owner@t.test",
        password="password123",
        name="Owner",
    )
    owner_id = uuid.UUID(owner["id"])
    admin, billing = _admin_role_and_perm(
        session, tenant, resource="billing", action="manage"
    )

    # State 1 — default exists as SYSTEM_DEFAULT
    rp = session.scalar(
        select(RolePermission).where(
            RolePermission.role_id == admin.id,
            RolePermission.permission_id == billing.id,
        )
    )
    assert rp is not None
    assert rp.source == "SYSTEM_DEFAULT"
    noop = reconcile_system_roles_for_tenant(session, tenant.id, actor="test")
    assert all(a["permission"] != "billing.manage" for a in noop["added"])

    current = RoleRepository(session).get_role(tenant.id, admin.id)
    remaining = [
        {"key": p["key"], "scope": p["scope"]}
        for p in current["permissions"]
        if p["key"] != "billing.manage"
    ]

    # State 2 — explicit revoke → tombstone
    RoleRepository(session).update_role(
        tenant.id,
        admin.id,
        actor=owner["email"],
        actor_user_id=owner_id,
        permissions=remaining,
    )
    assert (
        session.scalar(
            select(RolePermission).where(
                RolePermission.role_id == admin.id,
                RolePermission.permission_id == billing.id,
            )
        )
        is None
    )
    assert (
        session.scalar(
            select(RolePermissionTombstone).where(
                RolePermissionTombstone.role_id == admin.id,
                RolePermissionTombstone.permission_id == billing.id,
            )
        )
        is not None
    )

    # State 3 — reconcile must not restore
    reconcile_system_roles_for_tenant(session, tenant.id, actor="test")
    assert (
        session.scalar(
            select(RolePermission).where(
                RolePermission.role_id == admin.id,
                RolePermission.permission_id == billing.id,
            )
        )
        is None
    )

    # State 4 — re-grant as ORG_CUSTOM clears tombstone
    RoleRepository(session).update_role(
        tenant.id,
        admin.id,
        actor=owner["email"],
        actor_user_id=owner_id,
        permissions=[
            *remaining,
            {"key": "billing.manage", "scope": "ALL_ORGANIZATION"},
        ],
    )
    rp2 = session.scalar(
        select(RolePermission).where(
            RolePermission.role_id == admin.id,
            RolePermission.permission_id == billing.id,
        )
    )
    assert rp2 is not None
    assert rp2.source == "ORG_CUSTOM"
    assert (
        session.scalar(
            select(RolePermissionTombstone).where(
                RolePermissionTombstone.role_id == admin.id,
                RolePermissionTombstone.permission_id == billing.id,
            )
        )
        is None
    )

    # State 5 — revoke again after ORG_CUSTOM
    RoleRepository(session).update_role(
        tenant.id,
        admin.id,
        actor=owner["email"],
        actor_user_id=owner_id,
        permissions=remaining,
    )
    assert (
        session.scalar(
            select(RolePermission).where(
                RolePermission.role_id == admin.id,
                RolePermission.permission_id == billing.id,
            )
        )
        is None
    )
    assert (
        session.scalar(
            select(RolePermissionTombstone).where(
                RolePermissionTombstone.role_id == admin.id,
                RolePermissionTombstone.permission_id == billing.id,
            )
        )
        is not None
    )

    # State 6 — reconcile still preserves revocation
    for _ in range(3):
        r = reconcile_system_roles_for_tenant(session, tenant.id, actor="test")
        assert r["added_count"] == 0
    assert (
        session.scalar(
            select(RolePermission).where(
                RolePermission.role_id == admin.id,
                RolePermission.permission_id == billing.id,
            )
        )
        is None
    )


def test_admin_revoke_does_not_affect_custom_role(
    session: Session, tenant: Tenant
) -> None:
    from sqlalchemy import select

    from callbot_platform.rbac.models import RolePermission

    auth = AuthRepository(session)
    owner = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="owner@t.test",
        password="password123",
        name="Owner",
    )
    owner_id = uuid.UUID(owner["id"])
    admin, billing = _admin_role_and_perm(
        session, tenant, resource="billing", action="manage"
    )
    custom = RoleRepository(session).create_role(
        tenant.id,
        name="Custom Manager",
        description="custom",
        actor=owner["email"],
        actor_user_id=owner_id,
        permissions=[
            {"key": "billing.manage", "scope": "ALL_ORGANIZATION"},
            {"key": "customers.read", "scope": "ALL_ORGANIZATION"},
        ],
    )
    custom_id = uuid.UUID(custom["id"])
    before = {
        p["key"]
        for p in RoleRepository(session).get_role(tenant.id, custom_id)["permissions"]
    }

    remaining = [
        {"key": p["key"], "scope": p["scope"]}
        for p in RoleRepository(session).get_role(tenant.id, admin.id)["permissions"]
        if p["key"] != "billing.manage"
    ]
    RoleRepository(session).update_role(
        tenant.id,
        admin.id,
        actor=owner["email"],
        actor_user_id=owner_id,
        permissions=remaining,
    )
    after = {
        p["key"]
        for p in RoleRepository(session).get_role(tenant.id, custom_id)["permissions"]
    }
    assert after == before
    assert (
        session.scalar(
            select(RolePermission).where(
                RolePermission.role_id == custom_id,
                RolePermission.permission_id == billing.id,
            )
        )
        is not None
    )


def test_tombstone_does_not_leak_across_tenants(
    session: Session, tenant: Tenant
) -> None:
    from sqlalchemy import select

    from callbot_platform.rbac.models import RolePermission, RolePermissionTombstone
    from callbot_platform.rbac.reconcile import reconcile_system_roles_for_tenant
    from callbot_platform.rbac.seed import ensure_system_roles_for_tenant

    other = Tenant(name="Beta", slug=f"beta-{uuid.uuid4().hex[:8]}")
    session.add(other)
    session.flush()
    auth = AuthRepository(session)
    owner_a = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="a@t.test",
        password="password123",
        name="A",
    )
    auth.bootstrap_admin(
        tenant_id=other.id,
        email="b@t.test",
        password="password123",
        name="B",
    )
    ensure_system_roles_for_tenant(session, other.id)
    admin_a, billing = _admin_role_and_perm(
        session, tenant, resource="billing", action="manage"
    )
    admin_b, _ = _admin_role_and_perm(
        session, other, resource="billing", action="manage"
    )

    remaining = [
        {"key": p["key"], "scope": p["scope"]}
        for p in RoleRepository(session).get_role(tenant.id, admin_a.id)["permissions"]
        if p["key"] != "billing.manage"
    ]
    RoleRepository(session).update_role(
        tenant.id,
        admin_a.id,
        actor=owner_a["email"],
        actor_user_id=uuid.UUID(owner_a["id"]),
        permissions=remaining,
    )
    assert (
        session.scalar(
            select(RolePermissionTombstone).where(
                RolePermissionTombstone.role_id == admin_a.id,
                RolePermissionTombstone.permission_id == billing.id,
            )
        )
        is not None
    )
    assert (
        session.scalar(
            select(RolePermissionTombstone).where(
                RolePermissionTombstone.role_id == admin_b.id,
                RolePermissionTombstone.permission_id == billing.id,
            )
        )
        is None
    )
    assert (
        session.scalar(
            select(RolePermission).where(
                RolePermission.role_id == admin_b.id,
                RolePermission.permission_id == billing.id,
            )
        )
        is not None
    )
    reconcile_system_roles_for_tenant(session, other.id, actor="test")
    assert (
        session.scalar(
            select(RolePermission).where(
                RolePermission.role_id == admin_b.id,
                RolePermission.permission_id == billing.id,
            )
        )
        is not None
    )


def test_authz_cache_shared_across_service_instances(
    session: Session, tenant: Tenant
) -> None:
    """Service A caches; Service B invalidates via role update; A must deny."""
    from sqlalchemy import select

    from callbot_platform.rbac.catalog import SYSTEM_ROLE_ADMIN
    from callbot_platform.rbac.models import OrganizationRole
    from callbot_platform.rbac.seed import ensure_system_roles_for_tenant

    auth = AuthRepository(session)
    owner = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="owner@t.test",
        password="password123",
        name="Owner",
    )
    admin_user = auth.create_user(
        tenant.id,
        email="admin@t.test",
        password="password123",
        name="Admin",
        role="admin",
        actor=owner["email"],
    )
    admin_id = uuid.UUID(admin_user["id"])
    ensure_system_roles_for_tenant(session, tenant.id)

    svc_a = AuthorizationService(session)
    svc_b = AuthorizationService(session)
    assert svc_a._cache is svc_b._cache
    assert svc_a._cache is session.info["rbac_authz_cache"]
    assert svc_a.has_permission(tenant.id, admin_id, "billing.manage")

    admin_role = session.scalar(
        select(OrganizationRole).where(
            OrganizationRole.tenant_id == tenant.id,
            OrganizationRole.name == SYSTEM_ROLE_ADMIN,
        )
    )
    assert admin_role is not None
    remaining = [
        {"key": p["key"], "scope": p["scope"]}
        for p in RoleRepository(session).get_role(tenant.id, admin_role.id)[
            "permissions"
        ]
        if p["key"] != "billing.manage"
    ]
    # RoleRepository constructs its own AuthorizationService to invalidate —
    # must clear the shared session cache used by svc_a.
    RoleRepository(session).update_role(
        tenant.id,
        admin_role.id,
        actor=owner["email"],
        actor_user_id=uuid.UUID(owner["id"]),
        permissions=remaining,
    )
    assert not svc_a.has_permission(tenant.id, admin_id, "billing.manage")
    assert not svc_b.has_permission(tenant.id, admin_id, "billing.manage")

    # Re-grant → ALLOW on both instances
    RoleRepository(session).update_role(
        tenant.id,
        admin_role.id,
        actor=owner["email"],
        actor_user_id=uuid.UUID(owner["id"]),
        permissions=[
            *remaining,
            {"key": "billing.manage", "scope": "ALL_ORGANIZATION"},
        ],
    )
    assert svc_a.has_permission(tenant.id, admin_id, "billing.manage")
    assert svc_b.has_permission(tenant.id, admin_id, "billing.manage")


def test_authz_cache_not_shared_across_sessions(
    session: Session, tenant: Tenant
) -> None:
    """Distinct Sessions must not share mutable cache dicts."""
    from callbot_platform.db import get_session_factory

    auth = AuthRepository(session)
    owner = auth.bootstrap_admin(
        tenant_id=tenant.id,
        email="owner@t.test",
        password="password123",
        name="Owner",
    )
    owner_id = uuid.UUID(owner["id"])
    svc_a = AuthorizationService(session)
    assert svc_a.has_permission(tenant.id, owner_id, "roles.assign")
    cache_a = session.info["rbac_authz_cache"]

    factory = get_session_factory()
    other = factory()
    try:
        svc_b = AuthorizationService(other)
        cache_b = other.info.get("rbac_authz_cache")
        # Until first use, B may create its own empty cache on init.
        assert cache_b is not None
        assert cache_b is not cache_a
        assert svc_b._cache is not cache_a
    finally:
        other.close()

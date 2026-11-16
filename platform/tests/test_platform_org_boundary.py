"""Organization Owner ≠ Platform Owner — API and DTO boundary tests."""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from callbot_platform.api import deps as api_deps
from callbot_platform.auth.repos import AuthRepository
from callbot_platform.billing.usage_ledger import UsageCostAggregationService
from callbot_platform.billing.usage_ledger.categories import (
    AccountingProvenance,
    BillingStatus,
    UsageType,
)
from callbot_platform.billing.usage_ledger.ledger import UsageLedgerService
from callbot_platform.config import Settings, get_settings
from callbot_platform.db.models import Tenant
from callbot_platform.main import app
from callbot_platform.rbac.catalog import (
    PLATFORM_PERMISSION_KEYS,
    SYSTEM_ROLE_OWNER,
    all_permission_keys,
    default_role_permissions,
)
from callbot_platform.rbac.seed import ensure_system_roles_for_tenant
from callbot_platform.security.session import create_session_token


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        session_secret="boundary-session-secret-32chars-min",
        internal_service_token="boundary-internal-token",
        credentials_encryption_key="boundary-credentials-encryption-key",
        metadata_hmac_secret="boundary-metadata-hmac",
        cookie_secure=False,
        environment="development",
        session_cookie_name="callbot_ops_session",
    )


@pytest.fixture()
def owner_client(
    session: Session, tenant: Tenant, settings: Settings
) -> Generator[TestClient, None, None]:
    ensure_system_roles_for_tenant(session, tenant.id)
    user = AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email=f"owner-{uuid.uuid4().hex[:8]}@t.test",
        password="password12345",
        name="Org Owner",
    )
    session.commit()
    token = create_session_token(
        settings=settings,
        user_id=uuid.UUID(user["id"]),
        tenant_id=tenant.id,
        role=user["role"],
        email=user["email"],
    )

    def _db() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[api_deps.db_dep] = _db
    app.dependency_overrides[api_deps.settings_dep] = lambda: settings
    get_settings.cache_clear()
    client = TestClient(app)
    client.cookies.set(settings.session_cookie_name, token)
    try:
        yield client
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_owner_role_never_includes_platform_permissions() -> None:
    owner_keys = {k for k, _ in default_role_permissions(SYSTEM_ROLE_OWNER)}
    assert owner_keys.isdisjoint(PLATFORM_PERMISSION_KEYS)
    assert PLATFORM_PERMISSION_KEYS.isdisjoint(all_permission_keys())


def test_org_owner_usage_summary_omits_platform_financials(
    owner_client: TestClient, session: Session, tenant: Tenant
) -> None:
    ledger = UsageLedgerService(session)
    ledger.record(
        tenant_id=tenant.id,
        usage_type=UsageType.VOICE_MINUTES,
        quantity=10,
        idempotency_key=f"boundary-voice-{uuid.uuid4()}",
        source_type="test",
        source_id="1",
        usage_provenance=AccountingProvenance.ACTUAL_INTERNAL,
        cost_provenance=AccountingProvenance.CONFIGURED_RATE,
        unit_cost_micros_override=1000,
        billing_status=BillingStatus.UNBILLED,
    )
    session.commit()

    res = owner_client.get("/api/admin/usage-cost/summary")
    assert res.status_code == 200, res.text
    body = res.json()["usage_cost"]
    assert body.get("boundary") == "organization"
    assert "usage" in body
    assert "limits" in body
    assert "billing" in body
    # Platform-only fields must not appear in the customer DTO.
    for forbidden in (
        "cogs",
        "cost",
        "gross_margin",
        "revenue",
        "by_type",
        "billing_usage",
    ):
        assert forbidden not in body
    # Nested leak checks
    assert "total_cogs_usd" not in body.get("billing", {})
    assert "infrastructure" not in body.get("billing", {})
    daily = body.get("daily_series") or []
    for row in daily:
        assert "cost_usd" not in row


def test_org_owner_cannot_access_platform_cogs(
    owner_client: TestClient, tenant: Tenant
) -> None:
    denied = owner_client.get(
        f"/api/admin/cogs/summary?tenant_id={tenant.id}",
    )
    # Session cookie present but platform operator token missing → 401
    assert denied.status_code in {401, 403}

    scenarios = owner_client.get("/api/admin/cogs/scenarios")
    assert scenarios.status_code in {401, 403}

    fleet = owner_client.get("/api/admin/usage-cost/fleet")
    assert fleet.status_code in {401, 403}

    platform_sum = owner_client.get(
        f"/api/admin/usage-cost/platform-summary?tenant_id={tenant.id}",
    )
    assert platform_sum.status_code in {401, 403}


def test_platform_operator_can_access_cogs_and_full_summary(
    session: Session, tenant: Tenant, settings: Settings
) -> None:
    def _db() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[api_deps.db_dep] = _db
    app.dependency_overrides[api_deps.settings_dep] = lambda: settings
    get_settings.cache_clear()
    client = TestClient(app)
    headers = {"X-Internal-Token": settings.internal_service_token}
    try:
        cogs = client.get(
            f"/api/admin/cogs/summary?tenant_id={tenant.id}",
            headers=headers,
        )
        assert cogs.status_code == 200, cogs.text
        assert cogs.json().get("boundary") == "platform"

        full = client.get(
            f"/api/admin/usage-cost/platform-summary?tenant_id={tenant.id}",
            headers=headers,
        )
        assert full.status_code == 200, full.text
        payload = full.json()["usage_cost"]
        assert "cogs" in payload or "cost" in payload
        assert "gross_margin" in payload
        assert payload.get("boundary") == "platform"

        fleet = client.get("/api/admin/usage-cost/fleet", headers=headers)
        assert fleet.status_code == 200
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_customer_usage_summary_service_strips_fields(
    session: Session, tenant: Tenant
) -> None:
    ensure_system_roles_for_tenant(session, tenant.id)
    cust = UsageCostAggregationService(session).customer_usage_summary(tenant.id)
    plat = UsageCostAggregationService(session).organization_summary(tenant.id)
    assert "gross_margin" in plat
    assert "gross_margin" not in cust
    assert "cogs" not in cust
    assert cust["boundary"] == "organization"


def test_org_owner_cannot_assign_platform_permissions(
    session: Session, tenant: Tenant
) -> None:
    from callbot_platform.rbac.errors import RbacError
    from callbot_platform.rbac.repos import RoleRepository

    ensure_system_roles_for_tenant(session, tenant.id)
    owner = AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email=f"esc-{uuid.uuid4().hex[:8]}@t.test",
        password="password12345",
        name="Owner",
    )
    roles = RoleRepository(session)
    with pytest.raises(RbacError) as exc:
        roles.create_role(
            tenant.id,
            name=f"Escalation-{uuid.uuid4().hex[:6]}",
            description="must fail",
            permissions=[
                {"key": "platform.cogs.read", "scope": "ALL_ORGANIZATION"},
            ],
            actor=owner["email"],
            actor_user_id=uuid.UUID(owner["id"]),
        )
    assert exc.value.code == "platform_permission_forbidden"


def test_org_permission_catalog_excludes_platform_keys(
    session: Session, tenant: Tenant, owner_client: TestClient
) -> None:
    from callbot_platform.rbac.service import AuthorizationService

    ensure_system_roles_for_tenant(session, tenant.id)
    catalog = AuthorizationService(session).list_permissions_catalog()
    keys = {p["key"] for p in catalog}
    assert keys.isdisjoint(PLATFORM_PERMISSION_KEYS)
    assert not any(k.startswith("platform.") for k in keys)

    me = owner_client.get("/auth/me/permissions")
    assert me.status_code == 200
    eff = me.json()
    eff_keys = {p["key"] for p in eff.get("permissions", [])}
    assert eff_keys.isdisjoint(PLATFORM_PERMISSION_KEYS)


def test_ai_tool_registry_has_no_platform_cogs_tools() -> None:
    from callbot_platform.ai_tools.registry import TOOL_SPECS

    names = " ".join(sorted(TOOL_SPECS.keys())).lower()
    for needle in ("cogs", "gross_margin", "platform_revenue", "provider_cost"):
        assert needle not in names


def test_admin_role_also_denied_platform_cogs(
    session: Session, tenant: Tenant, settings: Settings
) -> None:
    """Organization Admin (not only Owner) must not reach platform COGS."""
    from callbot_platform.rbac.catalog import SYSTEM_ROLE_ADMIN
    from callbot_platform.rbac.repos import RoleRepository

    ensure_system_roles_for_tenant(session, tenant.id)
    owner = AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email=f"own2-{uuid.uuid4().hex[:8]}@t.test",
        password="password12345",
        name="Owner",
    )
    admin = AuthRepository(session).create_user(
        tenant.id,
        email=f"adm-{uuid.uuid4().hex[:8]}@t.test",
        password="password12345",
        name="Admin",
        role="admin",
        actor=owner["email"],
    )
    roles = RoleRepository(session)
    admin_role = next(
        r for r in roles.list_roles(tenant.id) if r["name"] == SYSTEM_ROLE_ADMIN
    )
    # Ensure Admin system role is assigned (create_user may already do this).
    try:
        roles.assign_role(
            tenant.id,
            member_id=uuid.UUID(admin["id"]),
            role_id=uuid.UUID(admin_role["id"]),
            actor=owner["email"],
            actor_user_id=uuid.UUID(owner["id"]),
        )
    except Exception:
        pass
    session.commit()

    token = create_session_token(
        settings=settings,
        user_id=uuid.UUID(admin["id"]),
        tenant_id=tenant.id,
        role=admin["role"],
        email=admin["email"],
    )

    def _db() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[api_deps.db_dep] = _db
    app.dependency_overrides[api_deps.settings_dep] = lambda: settings
    get_settings.cache_clear()
    client = TestClient(app)
    client.cookies.set(settings.session_cookie_name, token)
    try:
        assert client.get(
            f"/api/admin/cogs/summary?tenant_id={tenant.id}"
        ).status_code in {401, 403}
        assert client.get("/api/admin/usage-cost/fleet").status_code in {401, 403}
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()

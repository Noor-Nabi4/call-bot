"""Mandatory onboarding gate — API enforcement and signup row creation."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from callbot_platform.api import deps as api_deps
from callbot_platform.auth.repos import AuthRepository
from callbot_platform.billing.errors import BillingError
from callbot_platform.billing.service import BillingService
from callbot_platform.config import Settings, get_settings
from callbot_platform.db.models import Tenant
from callbot_platform.main import app
from callbot_platform.onboarding import (
    STATUS_COMPLETED,
    STATUS_IN_PROGRESS,
    STATUS_NOT_STARTED,
    STATUS_SKIPPED,
    OnboardingService,
)
from callbot_platform.onboarding.access import (
    is_onboarding_satisfied,
    mark_legacy_tenant_onboarding_complete,
)
from callbot_platform.onboarding.errors import OnboardingError
from callbot_platform.onboarding.repos import OnboardingRepository
from callbot_platform.onboarding.steps import REQUIRED_STEPS
from callbot_platform.rbac.seed import ensure_system_roles_for_tenant
from callbot_platform.security.session import create_session_token


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        session_secret="onboarding-gate-session-secret-32ch",
        internal_service_token="onboarding-gate-internal",
        credentials_encryption_key="onboarding-gate-credentials-key",
        metadata_hmac_secret="onboarding-gate-metadata-hmac",
        cookie_secure=False,
        environment="development",
        session_cookie_name="callbot_ops_session",
        stripe_secret_key="sk_test_gate",
    )


def _client(
    session: Session, settings: Settings, *, token: str | None = None
) -> TestClient:
    def _db() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[api_deps.db_dep] = _db
    app.dependency_overrides[api_deps.settings_dep] = lambda: settings
    get_settings.cache_clear()
    client = TestClient(app)
    if token:
        client.cookies.set(settings.session_cookie_name, token)
    return client


def _admin_client(
    session: Session, settings: Settings, tenant: Tenant
) -> tuple[TestClient, dict]:
    ensure_system_roles_for_tenant(session, tenant.id)
    user = AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email=f"owner-{uuid.uuid4().hex[:8]}@gate.test",
        password="password12345",
        name="Gate Owner",
    )
    session.flush()
    token = create_session_token(
        settings=settings,
        user_id=uuid.UUID(user["id"]),
        tenant_id=tenant.id,
        role=user["role"],
        email=user["email"],
    )
    return _client(session, settings, token=token), user


def test_missing_onboarding_row_is_not_satisfied(session: Session) -> None:
    tenant = Tenant(name="No Row", slug=f"norow-{uuid.uuid4().hex[:8]}")
    session.add(tenant)
    session.flush()
    assert is_onboarding_satisfied(session, tenant.id) is False


def test_signup_creates_not_started_onboarding(
    session: Session, settings: Settings
) -> None:
    svc = BillingService(session, settings)
    with (
        patch.object(svc, "_require_stripe"),
        patch(
            "callbot_platform.async_jobs.service.AsyncJobService.enqueue",
            return_value=MagicMock(id=uuid.uuid4()),
        ),
    ):
        result = svc.signup(
            business_name="New Co",
            slug=f"newco-{uuid.uuid4().hex[:8]}",
            timezone="UTC",
            name="Owner",
            email=f"owner-{uuid.uuid4().hex[:8]}@new.test",
            password="password12345",
            plan_key="starter",
        )
    tenant_id = uuid.UUID(str(result["tenant_id"]))
    row = OnboardingRepository(session).get(tenant_id)
    assert row is not None
    assert row.status == STATUS_NOT_STARTED
    assert is_onboarding_satisfied(session, tenant_id) is False


def test_incomplete_blocks_protected_api(session: Session, settings: Settings) -> None:
    tenant = Tenant(name="Incomplete", slug=f"inc-{uuid.uuid4().hex[:8]}")
    session.add(tenant)
    session.flush()
    OnboardingRepository(session).ensure(tenant.id)
    client, _user = _admin_client(session, settings, tenant)
    try:
        res = client.get("/api/admin/organization/roles")
        assert res.status_code == 403
        assert res.json()["detail"]["code"] == "ONBOARDING_REQUIRED"
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_incomplete_allows_onboarding_and_business_profile_apis(
    session: Session, settings: Settings
) -> None:
    tenant = Tenant(name="Wizard", slug=f"wiz-{uuid.uuid4().hex[:8]}")
    session.add(tenant)
    session.flush()
    OnboardingRepository(session).ensure(tenant.id)
    client, _user = _admin_client(session, settings, tenant)
    try:
        ob = client.get("/api/admin/organization/onboarding")
        assert ob.status_code == 200
        assert ob.json()["onboarding"]["status"] == STATUS_NOT_STARTED

        bp = client.get("/api/admin/organization/business-profile")
        assert bp.status_code == 200

        me = client.get("/auth/me")
        assert me.status_code == 200
        body = me.json()["user"]
        assert body["onboarding_complete"] is False
        assert body["onboarding_status"] == STATUS_NOT_STARTED
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_completed_allows_protected_api_with_rbac(
    session: Session, settings: Settings
) -> None:
    from callbot_platform.domain.enums import TenantStatus
    from helpers import make_phone

    tenant = Tenant(
        name="Done",
        slug=f"done-{uuid.uuid4().hex[:8]}",
        status=TenantStatus.ACTIVE.value,
    )
    session.add(tenant)
    session.flush()
    mark_legacy_tenant_onboarding_complete(session, tenant.id)
    make_phone(session, tenant, e164=f"+1555{uuid.uuid4().hex[:7]}")
    client, _user = _admin_client(session, settings, tenant)
    try:
        # Legacy active tenant with no subscription row remains entitled.
        res = client.get("/api/admin/organization/roles")
        assert res.status_code == 200
        me = client.get("/auth/me")
        body = me.json()["user"]
        assert body["onboarding_complete"] is True
        assert body["business_onboarding_complete"] is True
        assert body["phone_ready"] is True
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_legacy_completed_without_phone_is_blocked(
    session: Session, settings: Settings
) -> None:
    """Historical COMPLETED without an eligible DID cannot access the app."""
    from callbot_platform.domain.enums import TenantStatus

    tenant = Tenant(
        name="Legacy No Phone",
        slug=f"legph-{uuid.uuid4().hex[:8]}",
        status=TenantStatus.ACTIVE.value,
    )
    session.add(tenant)
    session.flush()
    mark_legacy_tenant_onboarding_complete(session, tenant.id)
    assert is_onboarding_satisfied(session, tenant.id) is False

    client, _user = _admin_client(session, settings, tenant)
    try:
        res = client.get("/api/admin/organization/roles")
        assert res.status_code == 403
        detail = res.json()["detail"]
        assert detail["code"] == "ONBOARDING_REQUIRED"
        assert detail["reason"] == "phone_required"

        me = client.get("/auth/me")
        body = me.json()["user"]
        assert body["business_onboarding_complete"] is True
        assert body["phone_ready"] is False
        assert body["onboarding_complete"] is False

        # Phone recovery stays available (no onboarding or wallet entitlement gate).
        phones = client.get("/api/admin/phone-numbers")
        assert phones.status_code == 200
        assert "items" in phones.json()
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_losing_last_eligible_phone_blocks_access(
    session: Session, settings: Settings
) -> None:
    from callbot_platform.domain.enums import ConnectionStatus, TenantStatus
    from helpers import make_phone

    tenant = Tenant(
        name="Lost DID",
        slug=f"lost-{uuid.uuid4().hex[:8]}",
        status=TenantStatus.ACTIVE.value,
    )
    session.add(tenant)
    session.flush()
    mark_legacy_tenant_onboarding_complete(session, tenant.id)
    phone = make_phone(session, tenant, e164=f"+1555{uuid.uuid4().hex[:7]}")
    assert is_onboarding_satisfied(session, tenant.id) is True

    client, _user = _admin_client(session, settings, tenant)
    try:
        assert client.get("/api/admin/organization/roles").status_code == 200
        phone.connection_status = ConnectionStatus.RELEASED.value
        session.flush()
        blocked = client.get("/api/admin/organization/roles")
        assert blocked.status_code == 403
        assert blocked.json()["detail"]["reason"] == "phone_required"
        # Onboarding status stays COMPLETED — access is modeled separately.
        from callbot_platform.onboarding.access import is_business_onboarding_complete

        assert is_business_onboarding_complete(session, tenant.id) is True
        assert is_onboarding_satisfied(session, tenant.id) is False

        # Regaining eligibility restores access without rewriting onboarding.
        phone.connection_status = ConnectionStatus.ACTIVE.value
        session.flush()
        assert is_onboarding_satisfied(session, tenant.id) is True
        assert client.get("/api/admin/organization/roles").status_code == 200
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_failed_completion_does_not_mark_complete(session: Session) -> None:
    from callbot_platform.onboarding import OnboardingError
    from helpers import make_phone

    tenant = Tenant(name="Fail Complete", slug=f"fail-{uuid.uuid4().hex[:8]}")
    session.add(tenant)
    session.flush()
    make_phone(session, tenant, e164=f"+1555{uuid.uuid4().hex[:7]}")
    svc = OnboardingService(session)
    for step in sorted(REQUIRED_STEPS - {"review"}):
        svc.complete_step(tenant.id, step, actor="a@t.test")
    with pytest.raises(OnboardingError) as exc:
        svc.complete_step(tenant.id, "review", actor="a@t.test")
    assert exc.value.code == "profile_incomplete"
    assert svc.get(tenant.id)["status"] == STATUS_IN_PROGRESS
    assert is_onboarding_satisfied(session, tenant.id) is False


def test_mark_completed_idempotent(session: Session, tenant: Tenant) -> None:
    # conftest tenant is already COMPLETED
    first = OnboardingService(session).mark_completed(tenant.id, actor="a@t.test")
    second = OnboardingService(session).mark_completed(tenant.id, actor="a@t.test")
    assert first["status"] == STATUS_COMPLETED
    assert second["status"] == STATUS_COMPLETED


def test_phone_apis_allowed_while_incomplete(
    session: Session, settings: Settings
) -> None:
    from callbot_platform.domain.enums import TenantStatus

    tenant = Tenant(
        name="Phone Inc",
        slug=f"phinc-{uuid.uuid4().hex[:8]}",
        status=TenantStatus.ACTIVE.value,
    )
    session.add(tenant)
    session.flush()
    OnboardingRepository(session).ensure(tenant.id)
    client, _user = _admin_client(session, settings, tenant)
    try:
        res = client.get("/api/admin/phone-numbers")
        assert res.status_code == 200
        assert res.json()["items"] == []
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_billing_allowed_while_incomplete(session: Session, settings: Settings) -> None:
    tenant = Tenant(name="Bill", slug=f"bill-{uuid.uuid4().hex[:8]}")
    session.add(tenant)
    session.flush()
    OnboardingRepository(session).ensure(tenant.id)
    client, _user = _admin_client(session, settings, tenant)
    try:
        # May 404/empty subscription but must not be ONBOARDING_REQUIRED
        res = client.get("/billing/subscription")
        detail = (
            res.json().get("detail")
            if res.headers.get("content-type", "").startswith("application/json")
            else None
        )
        code = detail.get("code") if isinstance(detail, dict) else None
        assert code != "ONBOARDING_REQUIRED"
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_team_routes_blocked_while_incomplete(
    session: Session, settings: Settings
) -> None:
    """Org profile is exempt; team membership mutations stay gated."""
    tenant = Tenant(name="Team Gate", slug=f"teamg-{uuid.uuid4().hex[:8]}")
    session.add(tenant)
    session.flush()
    OnboardingRepository(session).ensure(tenant.id)
    client, _user = _admin_client(session, settings, tenant)
    try:
        members = client.get("/api/admin/organization/members")
        assert members.status_code == 403
        assert members.json()["detail"]["code"] == "ONBOARDING_REQUIRED"
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_signup_queues_billing_without_completing_onboarding(
    session: Session, settings: Settings
) -> None:
    """Signup may queue Stripe provisioning; onboarding stays NOT_STARTED."""
    svc = BillingService(session, settings)
    with (
        patch.object(svc, "_require_stripe"),
        patch(
            "callbot_platform.async_jobs.service.AsyncJobService.enqueue",
            return_value=MagicMock(id=uuid.uuid4()),
        ),
    ):
        result = svc.signup(
            business_name="Checkout Co",
            slug=f"chk-{uuid.uuid4().hex[:8]}",
            timezone="UTC",
            name="Owner",
            email=f"owner-{uuid.uuid4().hex[:8]}@chk.test",
            password="password12345",
            plan_key="starter",
        )
    assert result.get("checkout_url") is None
    assert result.get("provisioning") == "queued"
    tenant_id = uuid.UUID(str(result["tenant_id"]))
    row = OnboardingRepository(session).get(tenant_id)
    assert row is not None
    assert row.status == STATUS_NOT_STARTED
    assert is_onboarding_satisfied(session, tenant_id) is False


def test_signup_allocates_unique_slug_when_base_taken(
    session: Session, settings: Settings
) -> None:
    """Workspace IDs are auto-generated; collisions get a unique suffix."""
    from callbot_platform.domain.enums import TenantStatus

    base_name = f"Dup Co {uuid.uuid4().hex[:6]}"
    existing = Tenant(
        name=base_name,
        slug=BillingService.slugify_business_name(base_name),
        status=TenantStatus.ACTIVE.value,
    )
    session.add(existing)
    session.flush()

    svc = BillingService(session, settings)
    with patch.object(svc, "_require_stripe"):
        result = svc.signup(
            business_name=base_name,
            timezone="UTC",
            name="Owner",
            email="dup@test.com",
            password="password12345",
            plan_key="starter",
        )
    assert result["slug"] != existing.slug
    assert result["slug"].startswith(existing.slug[:12])
    created = session.get(Tenant, uuid.UUID(str(result["tenant_id"])))
    assert created is not None
    assert created.slug == result["slug"]


def test_setup_path_persists_without_completing(
    session: Session, settings: Settings
) -> None:
    """Choosing AI/manual is draft state only — never completes onboarding."""
    tenant = Tenant(name="Path Co", slug=f"path-{uuid.uuid4().hex[:8]}")
    session.add(tenant)
    session.flush()
    OnboardingRepository(session).ensure(tenant.id)
    client, _user = _admin_client(session, settings, tenant)
    try:
        patched = client.patch(
            "/api/admin/organization/onboarding",
            json={
                "state_data": {"setup_path": "ai"},
                "current_step": "ai_configuration",
            },
        )
        assert patched.status_code == 200
        body = patched.json()["onboarding"]
        assert body["state_data"]["setup_path"] == "ai"
        assert body["status"] in {STATUS_NOT_STARTED, STATUS_IN_PROGRESS}
        assert body["status"] != STATUS_COMPLETED

        me = client.get("/auth/me")
        assert me.json()["user"]["onboarding_complete"] is False

        roles = client.get("/api/admin/organization/roles")
        assert roles.status_code == 403
        assert roles.json()["detail"]["code"] == "ONBOARDING_REQUIRED"
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_skipped_does_not_satisfy_gate(session: Session, settings: Settings) -> None:
    tenant = Tenant(name="Skipped Co", slug=f"skip-{uuid.uuid4().hex[:8]}")
    session.add(tenant)
    session.flush()
    row = OnboardingRepository(session).ensure(tenant.id)
    row.status = STATUS_SKIPPED
    OnboardingRepository(session).touch(row)
    assert is_onboarding_satisfied(session, tenant.id) is False

    client, _user = _admin_client(session, settings, tenant)
    try:
        res = client.get("/api/admin/organization/roles")
        assert res.status_code == 403
        assert res.json()["detail"]["code"] == "ONBOARDING_REQUIRED"
        me = client.get("/auth/me")
        assert me.json()["user"]["onboarding_complete"] is False
        assert me.json()["user"]["onboarding_status"] == STATUS_SKIPPED

        skip = client.post("/api/admin/organization/onboarding/skip")
        assert skip.status_code == 409
        assert skip.json()["detail"]["code"] == "mandatory_onboarding"
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_client_cannot_patch_status_to_completed(
    session: Session, settings: Settings
) -> None:
    tenant = Tenant(name="Hack Co", slug=f"hack-{uuid.uuid4().hex[:8]}")
    session.add(tenant)
    session.flush()
    OnboardingRepository(session).ensure(tenant.id)
    client, _user = _admin_client(session, settings, tenant)
    try:
        # Patch schema forbids status; extra fields rejected.
        res = client.patch(
            "/api/admin/organization/onboarding",
            json={"status": "COMPLETED", "state_data": {"setup_path": "manual"}},
        )
        assert res.status_code == 422
        assert is_onboarding_satisfied(session, tenant.id) is False
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_invalid_setup_path_rejected(session: Session, tenant: Tenant) -> None:
    # Use incomplete tenant via local row (conftest tenant is COMPLETED).
    incomplete = Tenant(name="Bad Path", slug=f"badpath-{uuid.uuid4().hex[:8]}")
    session.add(incomplete)
    session.flush()
    OnboardingRepository(session).ensure(incomplete.id)
    with pytest.raises(OnboardingError) as exc:
        OnboardingService(session).patch(
            incomplete.id,
            actor="a@t.test",
            state_data={"setup_path": "magic"},
        )
    assert exc.value.code == "invalid_setup_path"


def test_0057_backfill_sql_targets_missing_rows_only() -> None:
    """Static check: migration only INSERT … WHERE NOT EXISTS onboarding row."""
    from pathlib import Path

    sql = (
        Path(__file__).resolve().parents[1]
        / "src/alembic/versions/0057_onboarding_mandatory_backfill.py"
    ).read_text(encoding="utf-8")
    assert "INSERT INTO organization_onboarding" in sql
    assert "WHERE NOT EXISTS" in sql
    assert "'COMPLETED'" in sql
    assert "UPDATE organization_onboarding" not in sql

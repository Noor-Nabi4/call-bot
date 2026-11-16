"""Business profile, model, industry templates, and CRM setup tests."""

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
from callbot_platform.crm_config import CrmSetupService
from callbot_platform.crm_templates import TEMPLATES, resolve_template
from callbot_platform.db.models import (
    OrganizationCrmModule,
    OrganizationCrmStatus,
    Tenant,
)
from callbot_platform.main import app
from callbot_platform.onboarding import STATUS_COMPLETED, OnboardingService
from callbot_platform.onboarding.steps import REQUIRED_STEPS
from callbot_platform.organization import OrganizationError, OrganizationService
from callbot_platform.security.session import create_session_token


@pytest.fixture()
def session_settings() -> Settings:
    return Settings(
        session_secret="test-session-secret-business-cfg-ok32",
        internal_service_token="internal-test-token",
        session_cookie_name="callbot_ops_session",
    )


@pytest.fixture()
def tenant_b(session: Session) -> Tenant:
    row = Tenant(name="Beta Biz", slug=f"beta-biz-{uuid.uuid4().hex[:8]}")
    session.add(row)
    session.flush()
    return row


def _override_db(session: Session):
    def _db() -> Generator[Session, None, None]:
        yield session

    return _db


def _client(session: Session, settings: Settings, token: str) -> TestClient:
    app.dependency_overrides[db_dep] = _override_db(session)
    app.dependency_overrides[settings_dep] = lambda: settings
    get_settings.cache_clear()
    client = TestClient(app)
    client.cookies.set(settings.session_cookie_name, token)
    return client


def _token(settings: Settings, user: dict, tenant: Tenant) -> str:
    return create_session_token(
        settings=settings,
        user_id=uuid.UUID(user["id"]),
        tenant_id=tenant.id,
        role=user["role"],
        email=user["email"],
    )


def _seed_profile(session: Session, tenant: Tenant) -> None:
    OrganizationService(session).update(
        tenant.id,
        actor="seed",
        name="ABC HVAC",
        industry="hvac",
        business_type="services",
        timezone="America/Chicago",
        currency="USD",
        country="US",
        state="TX",
        business_size="small",
    )


def test_business_profile_validation(session: Session, tenant: Tenant) -> None:
    svc = OrganizationService(session)
    with pytest.raises(OrganizationError) as bad_tz:
        svc.update(tenant.id, actor="a", timezone="Not/AZone")
    assert bad_tz.value.code == "invalid_timezone"
    with pytest.raises(OrganizationError) as bad_cur:
        svc.update(tenant.id, actor="a", currency="ZZZ")
    assert bad_cur.value.code == "invalid_currency"
    with pytest.raises(OrganizationError) as bad_ind:
        svc.update(tenant.id, actor="a", industry="not_a_real_industry")
    assert bad_ind.value.code == "invalid_industry"
    with pytest.raises(OrganizationError) as bad_size:
        svc.update(tenant.id, actor="a", business_size="huge")
    assert bad_size.value.code == "invalid_business_size"

    saved = svc.update(
        tenant.id,
        actor="a",
        name="Acme",
        industry="HVAC",
        business_size="SMALL",
        business_type="services",
    )
    assert saved["industry_key"] == "hvac"
    assert saved["business_size"] == "small"


def test_business_profile_api_and_step_completion(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    _clear_onboarding(session, tenant.id)
    admin = AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email="admin@biz.test",
        password="password123",
        name="Admin",
    )
    client = _client(session, session_settings, _token(session_settings, admin, tenant))
    try:
        got = client.get("/api/admin/organization/business-profile")
        assert got.status_code == 200
        assert "industries" in got.json()["catalogs"]

        patched = client.patch(
            "/api/admin/organization/business-profile",
            json={
                "business_name": "ABC HVAC",
                "industry": "hvac",
                "timezone": "America/Chicago",
                "currency": "USD",
                "business_size": "small",
                "complete_steps": ["business_profile", "industry"],
            },
        )
        assert patched.status_code == 200
        assert patched.json()["profile"]["business_name"] == "ABC HVAC"
        assert "business_profile" in patched.json()["onboarding"]["completed_steps"]

        model = client.put(
            "/api/admin/organization/business-model",
            json={"business_model": "services"},
        )
        assert model.status_code == 200
        assert model.json()["business_model"] == "services"
        assert "business_model" in model.json()["onboarding"]["completed_steps"]
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_all_industry_templates_valid() -> None:
    keys = {t.key for t in TEMPLATES}
    expected = {
        "hvac",
        "plumbing",
        "electrical",
        "cleaning",
        "automotive",
        "dental",
        "medical",
        "real_estate",
        "ecommerce",
        "consulting",
        "beauty_salon",
        "fitness",
        "custom",
    }
    assert expected.issubset(keys)
    for tmpl in TEMPLATES:
        assert tmpl.modules
        assert len(tmpl.modules) == len(set(tmpl.modules))
        assert "CUSTOMERS" in tmpl.modules or tmpl.key == "custom"


def test_template_resolution() -> None:
    hvac = resolve_template(industry_key="hvac", business_model="services")
    assert hvac.key == "hvac"
    assert "JOBS" in hvac.modules
    ecommerce = resolve_template(industry_key="ecommerce", business_model="products")
    assert ecommerce.key == "ecommerce"
    assert "PRODUCTS" in ecommerce.modules
    custom = resolve_template(industry_key="unknown", business_model="services")
    assert custom.key == "custom"


def test_crm_setup_idempotent_and_preserves_custom(
    session: Session, tenant: Tenant
) -> None:
    _seed_profile(session, tenant)
    svc = CrmSetupService(session)
    first = svc.setup(tenant.id, actor="a@t.test")
    assert first["setup_completed"] is True
    assert any(m["key"] == "JOBS" for m in first["modules"])

    # Customize: disable JOBS and add a custom module row source
    job = session.scalar(
        select(OrganizationCrmModule).where(
            OrganizationCrmModule.tenant_id == tenant.id,
            OrganizationCrmModule.module_key == "JOBS",
        )
    )
    assert job is not None
    job.enabled = False
    job.source = "custom"
    session.flush()

    second = svc.setup(tenant.id, actor="a@t.test")
    mods = {m["key"]: m for m in second["modules"]}
    assert mods["JOBS"]["enabled"] is False
    assert mods["JOBS"]["source"] == "custom"

    status_count = len(
        list(
            session.scalars(
                select(OrganizationCrmStatus).where(
                    OrganizationCrmStatus.tenant_id == tenant.id
                )
            )
        )
    )
    svc.setup(tenant.id, actor="a@t.test")
    status_count_2 = len(
        list(
            session.scalars(
                select(OrganizationCrmStatus).where(
                    OrganizationCrmStatus.tenant_id == tenant.id
                )
            )
        )
    )
    assert status_count_2 == status_count


def test_crm_setup_tenant_isolation(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    _seed_profile(session, tenant)
    OrganizationService(session).update(
        tenant_b.id,
        actor="b",
        name="Shop",
        industry="ecommerce",
        business_type="products",
    )
    CrmSetupService(session).setup(tenant.id, actor="a")
    CrmSetupService(session).setup(tenant_b.id, actor="b")
    a = CrmSetupService(session).get(tenant.id)
    b = CrmSetupService(session).get(tenant_b.id)
    assert a is not None and b is not None
    assert a["tenant_id"] != b["tenant_id"]
    assert a["template_key"] == "hvac"
    assert b["template_key"] == "ecommerce"


def _clear_onboarding(session: Session, tenant_id: uuid.UUID) -> None:
    from callbot_platform.db.models import OrganizationOnboarding

    row = session.scalar(
        select(OrganizationOnboarding).where(
            OrganizationOnboarding.tenant_id == tenant_id
        )
    )
    if row is not None:
        session.delete(row)
        session.flush()


def test_onboarding_complete_runs_crm_setup(session: Session, tenant: Tenant) -> None:
    from helpers import make_phone

    _clear_onboarding(session, tenant.id)
    _seed_profile(session, tenant)
    make_phone(session, tenant, e164=f"+1555{uuid.uuid4().hex[:7]}")
    svc = OnboardingService(session)
    for step in sorted(REQUIRED_STEPS - {"review"}):
        svc.complete_step(tenant.id, step, actor="a")
    state = svc.complete_step(tenant.id, "review", actor="a")
    assert state["status"] == STATUS_COMPLETED
    cfg = CrmSetupService(session).get(tenant.id)
    assert cfg is not None
    assert cfg["setup_completed"] is True
    assert svc.mark_completed(tenant.id, actor="a")["status"] == STATUS_COMPLETED


def test_onboarding_complete_fails_without_industry(
    session: Session, tenant: Tenant
) -> None:
    from callbot_platform.onboarding import OnboardingError
    from helpers import make_phone

    _clear_onboarding(session, tenant.id)
    make_phone(session, tenant, e164=f"+1555{uuid.uuid4().hex[:7]}")
    svc = OnboardingService(session)
    for step in sorted(REQUIRED_STEPS - {"review"}):
        svc.complete_step(tenant.id, step, actor="a")
    with pytest.raises(OnboardingError) as exc:
        svc.complete_step(tenant.id, "review", actor="a")
    assert exc.value.code == "profile_incomplete"
    assert svc.get(tenant.id)["status"] != STATUS_COMPLETED


def test_cross_tenant_business_profile_api(
    session: Session, tenant: Tenant, tenant_b: Tenant, session_settings: Settings
) -> None:
    admin_a = AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email="a@iso.test",
        password="password123",
        name="A",
    )
    admin_b = AuthRepository(session).bootstrap_admin(
        tenant_id=tenant_b.id,
        email="b@iso.test",
        password="password123",
        name="B",
    )
    OrganizationService(session).update(
        tenant_b.id, actor="b", name="Secret Co", industry="dental"
    )
    client = _client(
        session, session_settings, _token(session_settings, admin_a, tenant)
    )
    try:
        got = client.get("/api/admin/organization/business-profile")
        assert got.status_code == 200
        assert got.json()["profile"]["business_name"] != "Secret Co"

        client.cookies.set(
            session_settings.session_cookie_name,
            _token(session_settings, admin_b, tenant_b),
        )
        b_got = client.get("/api/admin/organization/business-profile")
        assert b_got.json()["profile"]["business_name"] == "Secret Co"
        assert b_got.json()["profile"]["industry"] == "dental"
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_business_config_rbac_denied(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email="admin@rbac.test",
        password="password123",
        name="Admin",
    )
    dispatcher = AuthRepository(session).create_user(
        tenant.id,
        email="disp@rbac.test",
        password="password123",
        name="Disp",
        role="dispatcher",
    )
    client = _client(
        session, session_settings, _token(session_settings, dispatcher, tenant)
    )
    try:
        assert (
            client.patch(
                "/api/admin/organization/business-profile",
                json={"business_name": "Nope"},
            ).status_code
            == 403
        )
        assert (
            client.put(
                "/api/admin/organization/business-model",
                json={"business_model": "services"},
            ).status_code
            == 403
        )
        assert (
            client.post("/api/admin/organization/crm-configuration/setup").status_code
            == 403
        )
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()

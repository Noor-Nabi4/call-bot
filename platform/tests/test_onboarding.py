"""Organization onboarding state tests (Task 2.1)."""

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
from callbot_platform.onboarding import (
    STATUS_COMPLETED,
    STATUS_IN_PROGRESS,
    STATUS_NOT_STARTED,
    STATUS_SKIPPED,
    OnboardingError,
    OnboardingService,
)
from callbot_platform.onboarding.steps import REQUIRED_STEPS, STEP_ORDER
from callbot_platform.security.session import create_session_token


@pytest.fixture()
def session_settings() -> Settings:
    return Settings(
        session_secret="test-session-secret-onboarding-ok32",
        internal_service_token="internal-test-token",
        session_cookie_name="callbot_ops_session",
    )


@pytest.fixture()
def tenant_b(session: Session) -> Tenant:
    row = Tenant(name="Beta Onboard", slug=f"beta-ob-{uuid.uuid4().hex[:8]}")
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


def _token_for(settings: Settings, user: dict, tenant: Tenant) -> str:
    return create_session_token(
        settings=settings,
        user_id=uuid.UUID(user["id"]),
        tenant_id=tenant.id,
        role=user["role"],
        email=user["email"],
    )


def test_lazy_not_started(session: Session, tenant: Tenant) -> None:
    state = OnboardingService(session).get(tenant.id)
    assert state["status"] == STATUS_NOT_STARTED
    assert state["progress_percent"] == 0
    assert state["completed_count"] == 0
    assert state["total_count"] == len(STEP_ORDER)
    assert state["can_resume"] is False
    assert state["completed_steps"] == []
    assert state["skipped_steps"] == []


def test_progress_and_optional_skip(session: Session, tenant: Tenant) -> None:
    svc = OnboardingService(session)
    svc.complete_step(tenant.id, "business_profile", actor="a@t.test")
    state = svc.get(tenant.id)
    assert state["status"] == STATUS_IN_PROGRESS
    assert state["completed_steps"] == ["business_profile"]
    assert state["progress_percent"] == round(100 * 1 / len(STEP_ORDER))

    svc.skip_step(tenant.id, "knowledge", actor="a@t.test")
    state = svc.get(tenant.id)
    assert "knowledge" in state["skipped_steps"]
    assert "knowledge" not in state["completed_steps"]
    assert state["completed_count"] == 2

    with pytest.raises(OnboardingError) as exc:
        svc.skip_step(tenant.id, "business_profile", actor="a@t.test")
    assert exc.value.code == "step_required"


def test_idempotent_complete_and_skip(session: Session, tenant: Tenant) -> None:
    svc = OnboardingService(session)
    for _ in range(3):
        svc.complete_step(tenant.id, "industry", actor="a@t.test")
        svc.skip_step(tenant.id, "catalog", actor="a@t.test")
    state = svc.get(tenant.id)
    assert state["completed_steps"].count("industry") == 1
    assert state["skipped_steps"].count("catalog") == 1


def test_resume_and_partial_state_data(session: Session, tenant: Tenant) -> None:
    svc = OnboardingService(session)
    svc.patch(
        tenant.id,
        actor="a@t.test",
        current_step="business_model",
        state_data={"draft_note": "partial"},
    )
    state = svc.get(tenant.id)
    assert state["status"] == STATUS_IN_PROGRESS
    assert state["current_step"] == "business_model"
    assert state["resume_step"] == "business_model"
    assert state["can_resume"] is True
    assert state["state_data"]["draft_note"] == "partial"

    # Stale current_step is repaired on serialize
    row_id = state["id"]
    from callbot_platform.db.models import OrganizationOnboarding

    row = session.get(OrganizationOnboarding, uuid.UUID(row_id))
    assert row is not None
    row.current_step = "not_a_real_step"
    session.flush()
    repaired = svc.get(tenant.id)
    assert repaired["resume_step"] in STEP_ORDER
    assert repaired["resume_step"] != "not_a_real_step"


def test_completion_requires_mandatory_steps(session: Session, tenant: Tenant) -> None:
    svc = OnboardingService(session)
    with pytest.raises(OnboardingError) as exc:
        svc.mark_completed(tenant.id, actor="a@t.test")
    assert exc.value.code in {"incomplete", "invalid_transition"}

    svc.patch(tenant.id, actor="a@t.test", current_step="business_profile")
    with pytest.raises(OnboardingError) as incomplete:
        svc.mark_completed(tenant.id, actor="a@t.test")
    assert incomplete.value.code == "incomplete"

    from callbot_platform.organization import OrganizationService

    OrganizationService(session).update(
        tenant.id,
        actor="a@t.test",
        name="Ready Co",
        industry="hvac",
        business_type="services",
    )
    for step in REQUIRED_STEPS:
        svc.complete_step(tenant.id, step, actor="a@t.test")
    state = svc.get(tenant.id)
    assert state["status"] == STATUS_COMPLETED
    again = svc.mark_completed(tenant.id, actor="a@t.test")
    assert again["status"] == STATUS_COMPLETED


def test_skip_entire_onboarding(session: Session, tenant: Tenant) -> None:
    svc = OnboardingService(session)
    state = svc.mark_skipped(tenant.id, actor="a@t.test")
    assert state["status"] == STATUS_SKIPPED
    with pytest.raises(OnboardingError) as exc:
        svc.complete_step(tenant.id, "industry", actor="a@t.test")
    assert exc.value.code == "onboarding_closed"


def test_api_session_scoped_and_rbac(
    session: Session, tenant: Tenant, tenant_b: Tenant, session_settings: Settings
) -> None:
    admin_a = AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email="admin-a@t.test",
        password="password123",
        name="Admin A",
    )
    admin_b = AuthRepository(session).bootstrap_admin(
        tenant_id=tenant_b.id,
        email="admin-b@t.test",
        password="password123",
        name="Admin B",
    )
    dispatcher = AuthRepository(session).create_user(
        tenant.id,
        email="disp@t.test",
        password="password123",
        name="Disp",
        role="dispatcher",
    )

    OnboardingService(session).complete_step(
        tenant_b.id, "business_profile", actor="admin-b@t.test"
    )

    token_a = _token_for(session_settings, admin_a, tenant)
    token_b = _token_for(session_settings, admin_b, tenant_b)
    token_disp = _token_for(session_settings, dispatcher, tenant)
    client = _client_for(session, session_settings, token=token_a)
    try:
        got = client.get("/api/admin/organization/onboarding")
        assert got.status_code == 200
        body = got.json()["onboarding"]
        assert body["status"] == STATUS_NOT_STARTED
        assert "business_profile" not in body["completed_steps"]

        patched = client.patch(
            "/api/admin/organization/onboarding",
            json={"current_step": "industry", "state_data": {"x": 1}},
        )
        assert patched.status_code == 200
        assert patched.json()["onboarding"]["current_step"] == "industry"

        done = client.post(
            "/api/admin/organization/onboarding/steps/business_profile/complete"
        )
        assert done.status_code == 200
        assert "business_profile" in done.json()["onboarding"]["completed_steps"]

        # Tenant A state must not include Tenant B's completed step from earlier
        assert done.json()["onboarding"]["tenant_id"] == str(tenant.id)

        # Dispatcher lacks organization.update
        client.cookies.set(session_settings.session_cookie_name, token_disp)
        denied = client.post(
            "/api/admin/organization/onboarding/steps/industry/complete"
        )
        assert denied.status_code == 403

        # Tenant B cannot see A's progress row
        client.cookies.set(session_settings.session_cookie_name, token_b)
        b_got = client.get("/api/admin/organization/onboarding")
        assert b_got.status_code == 200
        b_body = b_got.json()["onboarding"]
        assert b_body["tenant_id"] == str(tenant_b.id)
        assert b_body["id"] != done.json()["onboarding"]["id"]
        assert "business_profile" in b_body["completed_steps"]
        # B never patched current_step to industry
        assert (
            b_body.get("current_step") != "industry"
            or b_body["state_data"].get("x") != 1
        )
        assert b_body["state_data"].get("x") != 1
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_cross_tenant_service_isolation(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    svc = OnboardingService(session)
    svc.complete_step(tenant.id, "business_profile", actor="a")
    a = svc.get(tenant.id)
    b = svc.get(tenant_b.id)
    assert a["tenant_id"] != b["tenant_id"]
    assert "business_profile" in a["completed_steps"]
    assert "business_profile" not in b["completed_steps"]

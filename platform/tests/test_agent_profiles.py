"""Tests for multi agent profiles, templates, and phone assignment."""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from callbot_platform.api.deps import db_dep, settings_dep
from callbot_platform.auth.repos import AuthRepository
from callbot_platform.config import Settings, get_settings
from callbot_platform.crm.repos import AgentProfileRepository, AgentSettingsRepository
from callbot_platform.db.models import Tenant, TenantPhoneNumber
from callbot_platform.domain.enums import ConnectionStatus, VerificationStatus
from callbot_platform.main import app
from callbot_platform.security.session import create_session_token
from callbot_platform.telephony.interfaces import ResolveRequest
from callbot_platform.telephony.services.resolver import DbTenantDidResolver


@pytest.fixture()
def session_settings() -> Settings:
    return Settings(
        session_secret="test-session-secret-agent-profiles-ok32",
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


def test_create_multiple_profiles_and_default(session: Session, tenant: Tenant) -> None:
    repo = AgentProfileRepository(session)
    main = repo.create(
        tenant.id,
        name="Main Receptionist",
        agent_type="receptionist",
        is_default=True,
        greeting="Hello main",
    )
    sales = repo.create(
        tenant.id,
        name="Sales Agent",
        agent_type="sales",
        greeting="Hello sales",
    )
    assert main["is_default"] is True
    assert sales["is_default"] is False
    assert tenant.default_agent_profile_id == uuid.UUID(main["id"])

    repo.set_default(tenant.id, uuid.UUID(sales["id"]))
    session.refresh(tenant)
    assert tenant.default_agent_profile_id == uuid.UUID(sales["id"])
    listed = repo.list(tenant.id)
    defaults = [p for p in listed if p["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["id"] == sales["id"]


def test_apply_template_seeds_knowledge(session: Session, tenant: Tenant) -> None:
    repo = AgentProfileRepository(session)
    profile = repo.create(tenant.id, name="HVAC Desk", is_default=True)
    updated = repo.apply_template(
        tenant.id, uuid.UUID(profile["id"]), industry_key="hvac"
    )
    assert updated["industry_key"] == "hvac"
    assert updated["agent_type"] == "receptionist"
    from callbot_platform.knowledge.repos import KnowledgeRepository

    articles = KnowledgeRepository(session).list(tenant.id)
    assert any(a["title"] == "Service area" for a in articles)
    assert all(
        a["agent_profile_id"] == profile["id"]
        for a in articles
        if a["title"] == "Service area"
    )


def test_legacy_settings_maps_to_default(session: Session, tenant: Tenant) -> None:
    settings_repo = AgentSettingsRepository(session)
    saved = settings_repo.upsert(
        tenant.id,
        greeting="Legacy hello",
        assistant_name="Ada",
        voice="marin",
    )
    assert saved["greeting"] == "Legacy hello"
    assert saved["agent_profile_id"]
    profile = AgentProfileRepository(session).get_default(tenant.id)
    assert profile is not None
    assert profile["greeting"] == "Legacy hello"
    voice = settings_repo.get_profile(tenant.id, business_name=tenant.name)
    assert voice is not None
    assert voice["business_name"] == tenant.name
    assert voice["greeting"] == "Legacy hello"


def test_resolve_includes_phone_agent_profile(
    session: Session, tenant: Tenant, signer
) -> None:
    repo = AgentProfileRepository(session)
    after_hours = repo.create(
        tenant.id, name="After Hours", agent_type="receptionist", is_default=True
    )
    sales = repo.create(tenant.id, name="Sales", agent_type="sales")
    phone = TenantPhoneNumber(
        tenant_id=tenant.id,
        e164="+15551234567",
        onboarding_path="platform_purchase",
        connection_status=ConnectionStatus.ACTIVE.value,
        verification_status=VerificationStatus.VERIFIED.value,
        agent_profile_id=uuid.UUID(sales["id"]),
        provider="twilio",
    )
    session.add(phone)
    session.flush()

    result = DbTenantDidResolver(session, signer).resolve(
        ResolveRequest(called_number="+15551234567", is_sip=True)
    )
    assert result.tenant_id == tenant.id
    assert result.agent_profile_id == uuid.UUID(sales["id"])

    phone.agent_profile_id = None
    session.flush()
    result2 = DbTenantDidResolver(session, signer).resolve(
        ResolveRequest(called_number="+15551234567", is_sip=True)
    )
    assert result2.agent_profile_id == uuid.UUID(after_hours["id"])


def test_sip_resolve_fails_without_profile(
    session: Session, tenant: Tenant, signer
) -> None:
    phone = TenantPhoneNumber(
        tenant_id=tenant.id,
        e164="+15557654321",
        onboarding_path="platform_purchase",
        connection_status=ConnectionStatus.ACTIVE.value,
        verification_status=VerificationStatus.VERIFIED.value,
        provider="twilio",
    )
    session.add(phone)
    session.flush()
    from callbot_platform.telephony.services.resolver import TenantResolveError

    with pytest.raises(TenantResolveError) as exc:
        DbTenantDidResolver(session, signer).resolve(
            ResolveRequest(called_number="+15557654321", is_sip=True)
        )
    assert exc.value.code == "agent_profile_missing"


def test_admin_agent_profile_apis(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    admin = AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email="admin@t.test",
        password="password123",
        name="Admin",
    )
    token = create_session_token(
        settings=session_settings,
        user_id=uuid.UUID(admin["id"]),
        tenant_id=tenant.id,
        role=admin["role"],
        email=admin["email"],
    )
    client = _client_for(session, session_settings, token=token)
    try:
        templates = client.get("/api/admin/industry-templates")
        assert templates.status_code == 200
        assert any(t["key"] == "hvac" for t in templates.json()["templates"])

        created = client.post(
            "/api/admin/agent-profiles",
            json={
                "name": "Support Desk",
                "agent_type": "support",
                "industry_key": "support",
                "is_default": True,
            },
        )
        assert created.status_code == 200, created.text
        profile_id = created.json()["profile"]["id"]

        listed = client.get("/api/admin/agent-profiles")
        assert listed.status_code == 200
        assert len(listed.json()["profiles"]) >= 1

        updated = client.put(
            f"/api/admin/agent-profiles/{profile_id}",
            json={"greeting": "Support hello"},
        )
        assert updated.status_code == 200
        assert updated.json()["profile"]["greeting"] == "Support hello"

        flow_updated = client.put(
            f"/api/admin/agent-profiles/{profile_id}",
            json={
                "call_flow": {
                    "version": 1,
                    "steps": [
                        {
                            "id": "g1",
                            "type": "greeting",
                            "label": "Warm open",
                            "instruction": "Greet briefly",
                            "enabled": True,
                        }
                    ],
                }
            },
        )
        assert flow_updated.status_code == 200, flow_updated.text
        assert (
            flow_updated.json()["profile"]["call_flow"]["steps"][0]["label"]
            == "Warm open"
        )

        catalog = client.get("/api/admin/marketplace")
        assert catalog.status_code == 200
        assert "categories" in catalog.json()
        assert any(t["key"] == "hvac" for t in catalog.json()["templates"])
        assert any(t.get("featured") for t in catalog.json()["templates"])

        installed = client.post(
            "/api/admin/marketplace/install",
            json={
                "industry_key": "hvac",
                "name": "HVAC Front Desk",
                "seed_knowledge": True,
                "set_as_default": False,
            },
        )
        assert installed.status_code == 200, installed.text
        assert installed.json()["profile"]["industry_key"] == "hvac"
        assert installed.json()["profile"]["name"] == "HVAC Front Desk"
        assert (
            "heating or cooling"
            in (installed.json()["profile"].get("greeting") or "").lower()
        )
    finally:
        app.dependency_overrides.clear()

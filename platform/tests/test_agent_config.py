"""Phase 30 — AI Agent Configuration: profile, capabilities, enforcement."""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from callbot_platform.agent_config.capabilities import (
    TOOL_TO_CAPABILITY,
    normalize_capabilities,
)
from callbot_platform.agent_config.enforcement import assert_tool_capability
from callbot_platform.agent_config.errors import AgentConfigError
from callbot_platform.agent_config.service import AgentConfigService
from callbot_platform.agent_config.voices import assert_voice, list_voices
from callbot_platform.ai_tools.executor import AIToolExecutor
from callbot_platform.api.deps import db_dep, settings_dep
from callbot_platform.auth.repos import AuthRepository
from callbot_platform.config import Settings, get_settings
from callbot_platform.crm.repos.agent_profile_repo import AgentProfileRepository
from callbot_platform.db.models import Tenant
from callbot_platform.main import app
from callbot_platform.security.session import create_session_token


@pytest.fixture()
def session_settings() -> Settings:
    return Settings(
        session_secret="test-session-secret-agent-config30ok",
        internal_service_token="internal-test-token",
        session_cookie_name="callbot_ops_session",
        credentials_encryption_key="test-credentials-encryption-key-a30xx",
        metadata_hmac_secret="test-metadata-hmac-secret-agent-cfg30",
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


def _profile(session: Session, tenant: Tenant) -> dict:
    return AgentProfileRepository(session).create(
        tenant.id,
        name="Front Desk",
        assistant_name="Alex",
        greeting="Thanks for calling. This is Alex. How can I help?",
        voice="marin",
        language="en",
        tone="professional",
        is_default=True,
        actor="test",
    )


def test_voice_catalog_controlled() -> None:
    voices = list_voices()
    assert any(v["key"] == "marin" for v in voices)
    assert assert_voice("alloy") == "alloy"
    with pytest.raises(ValueError):
        assert_voice("not-a-real-voice")


def test_capability_tool_mapping() -> None:
    assert TOOL_TO_CAPABILITY["create_booking"] == "APPOINTMENT_BOOK"
    assert TOOL_TO_CAPABILITY["send_sms"] == "SMS_SEND"
    assert TOOL_TO_CAPABILITY["create_payment_link"] == "PAYMENT_LINK"
    assert TOOL_TO_CAPABILITY["request_human"] == "HUMAN_TRANSFER"


def test_profile_update_and_activate(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    profile = _profile(session, tenant)
    svc = AgentConfigService(session)
    updated = svc.update_config(
        tenant.id,
        uuid.UUID(profile["id"]),
        actor="owner@test",
        voice="coral",
        language="en",
        tone="friendly",
        greeting="Hi, this is Alex at Test Co.",
        capabilities={
            "CALL_ANSWERING": True,
            "APPOINTMENT_BOOK": False,
            "APPOINTMENT_CANCEL": False,
            "PAYMENT_LINK": False,
            "SMS_SEND": True,
            "HUMAN_TRANSFER": True,
            "LEAD_CREATE": False,
            "LEAD_QUALIFY": False,
            "PRODUCT_SEARCH": False,
            "INVENTORY_LOOKUP": False,
            "PRICING_LOOKUP": True,
            "ORDER_LOOKUP": False,
            "APPOINTMENT_RESCHEDULE": False,
        },
        transfer_rules={"customer_requests_human": True},
        after_hours_behavior="take_message",
        status="draft",
    )
    assert updated["voice"] == "coral"
    assert updated["status"] == "draft"
    assert updated["capabilities"]["SMS_SEND"] is True
    assert updated["capabilities"]["PAYMENT_LINK"] is False

    # Draft must not resolve for voice runtime
    voice = AgentProfileRepository(session).get_voice_profile(
        tenant.id, business_name=tenant.name
    )
    assert voice is None

    activated = svc.activate(tenant.id, uuid.UUID(profile["id"]), actor="owner@test")
    assert activated["status"] == "active"
    voice2 = AgentProfileRepository(session).get_voice_profile(
        tenant.id, business_name=tenant.name
    )
    assert voice2 is not None
    assert voice2["voice"] == "coral"


def test_invalid_voice_rejected(session: Session, tenant: Tenant) -> None:
    profile = _profile(session, tenant)
    with pytest.raises(AgentConfigError) as exc:
        AgentConfigService(session).update_config(
            tenant.id,
            uuid.UUID(profile["id"]),
            actor="owner@test",
            voice="robot-9000",
        )
    assert exc.value.code == "invalid_voice"


def test_capability_unavailable_without_module(
    session: Session, tenant: Tenant
) -> None:
    profile = _profile(session, tenant)
    with pytest.raises(AgentConfigError) as exc:
        AgentConfigService(session).update_config(
            tenant.id,
            uuid.UUID(profile["id"]),
            actor="owner@test",
            capabilities={"PAYMENT_LINK": True},
        )
    assert exc.value.code == "CAPABILITY_UNAVAILABLE"


def test_executor_blocks_disabled_capability(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    profile = _profile(session, tenant)
    AgentConfigService(session).update_config(
        tenant.id,
        uuid.UUID(profile["id"]),
        actor="owner@test",
        capabilities={
            "CALL_ANSWERING": True,
            "APPOINTMENT_BOOK": False,
            "APPOINTMENT_RESCHEDULE": False,
            "APPOINTMENT_CANCEL": False,
            "SMS_SEND": False,
            "HUMAN_TRANSFER": True,
            "PAYMENT_LINK": False,
            "PRODUCT_SEARCH": False,
            "INVENTORY_LOOKUP": False,
            "PRICING_LOOKUP": True,
            "LEAD_CREATE": False,
            "LEAD_QUALIFY": False,
            "ORDER_LOOKUP": False,
        },
        status="active",
    )
    with pytest.raises(AgentConfigError) as exc:
        assert_tool_capability(session, tenant.id, "create_booking")
    assert exc.value.code == "CAPABILITY_DISABLED"

    executor = AIToolExecutor(
        session, hmac_secret=session_settings.metadata_hmac_secret
    )
    result = executor.execute(
        "create_booking",
        tenant_id=tenant.id,
        call_id=None,
        args={
            "customerId": str(uuid.uuid4()),
            "serviceId": str(uuid.uuid4()),
            "startsAt": "2030-01-01T10:00:00+00:00",
            "endsAt": "2030-01-01T11:00:00+00:00",
            "timezone": "UTC",
        },
        operation_id=uuid.uuid4(),
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "capability_disabled"


def test_cross_tenant_config_isolation(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    other = Tenant(name="Other", slug=f"other-{uuid.uuid4().hex[:8]}")
    session.add(other)
    session.flush()
    profile_a = _profile(session, tenant)
    admin_b = AuthRepository(session).bootstrap_admin(
        tenant_id=other.id,
        email="b@agent30.test",
        password="password123",
        name="B",
    )
    client = _client_for(
        session,
        session_settings,
        token=_token_for(session_settings, admin_b, other),
    )
    try:
        res = client.get(f"/api/admin/agent-config/profiles/{profile_a['id']}")
        assert res.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_api_catalog_and_update(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    profile = _profile(session, tenant)
    admin = AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email="owner@agent30.test",
        password="password123",
        name="Owner",
    )
    client = _client_for(
        session,
        session_settings,
        token=_token_for(session_settings, admin, tenant),
    )
    try:
        catalog = client.get("/api/admin/agent-config/catalog")
        assert catalog.status_code == 200
        assert "voices" in catalog.json()["catalog"]

        updated = client.put(
            f"/api/admin/agent-config/profiles/{profile['id']}",
            json={
                "assistant_name": "Jordan",
                "voice": "sage",
                "tone": "warm",
                "greeting": "Thanks for calling — Jordan here.",
                "capabilities": {
                    "CALL_ANSWERING": True,
                    "HUMAN_TRANSFER": True,
                    "SMS_SEND": True,
                    "APPOINTMENT_BOOK": False,
                    "APPOINTMENT_RESCHEDULE": False,
                    "APPOINTMENT_CANCEL": False,
                    "PAYMENT_LINK": False,
                    "PRODUCT_SEARCH": False,
                    "INVENTORY_LOOKUP": False,
                    "PRICING_LOOKUP": True,
                    "LEAD_CREATE": False,
                    "LEAD_QUALIFY": False,
                    "ORDER_LOOKUP": False,
                },
            },
        )
        assert updated.status_code == 200, updated.text
        body = updated.json()["config"]
        assert body["assistant_name"] == "Jordan"
        assert body["voice"] == "sage"

        act = client.post(
            f"/api/admin/agent-config/profiles/{profile['id']}/activate",
            json={},
        )
        assert act.status_code == 200
        assert act.json()["config"]["status"] == "active"
    finally:
        app.dependency_overrides.clear()


def test_normalize_capabilities_unknown_ignored() -> None:
    caps = normalize_capabilities({"CALL_ANSWERING": True, "HACK_THE_PLANET": True})
    assert caps["CALL_ANSWERING"] is True
    assert "HACK_THE_PLANET" not in caps


def _set_caps(session: Session, tenant: Tenant, profile_id: str, **caps: bool) -> None:
    base = {
        "CALL_ANSWERING": True,
        "HUMAN_TRANSFER": False,
        "SMS_SEND": False,
        "APPOINTMENT_BOOK": False,
        "APPOINTMENT_RESCHEDULE": False,
        "APPOINTMENT_CANCEL": False,
        "PAYMENT_LINK": False,
        "PRODUCT_SEARCH": False,
        "INVENTORY_LOOKUP": False,
        "PRICING_LOOKUP": False,
        "LEAD_CREATE": False,
        "LEAD_QUALIFY": False,
        "ORDER_LOOKUP": False,
    }
    base.update(caps)
    AgentConfigService(session).update_config(
        tenant.id,
        uuid.UUID(profile_id),
        actor="owner@test",
        capabilities=base,
        status="active",
    )


def test_runtime_path_draft_not_served_to_voice(
    session: Session, tenant: Tenant
) -> None:
    profile = _profile(session, tenant)
    AgentConfigService(session).update_config(
        tenant.id,
        uuid.UUID(profile["id"]),
        actor="owner@test",
        status="draft",
    )
    assert (
        AgentProfileRepository(session).get_voice_profile(
            tenant.id, business_name=tenant.name
        )
        is None
    )
    assert AgentProfileRepository(session).get_default(tenant.id) is None


def test_runtime_path_disabled_capability_matrix(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    """Verify checklist: disabled capability → tool rejected (no mutation)."""
    profile = _profile(session, tenant)
    _set_caps(session, tenant, profile["id"])  # all sensitive caps off
    executor = AIToolExecutor(
        session, hmac_secret=session_settings.metadata_hmac_secret
    )
    cases = [
        ("create_booking", "APPOINTMENT_BOOK"),
        ("check_inventory", "INVENTORY_LOOKUP"),
        ("send_sms", "SMS_SEND"),
        ("create_payment_link", "PAYMENT_LINK"),
        ("request_human", "HUMAN_TRANSFER"),
    ]
    for tool_name, _cap in cases:
        with pytest.raises(AgentConfigError) as exc:
            assert_tool_capability(session, tenant.id, tool_name)
        assert exc.value.code == "CAPABILITY_DISABLED"
        result = executor.execute(
            tool_name,
            tenant_id=tenant.id,
            call_id=None,
            args={},
            operation_id=uuid.uuid4(),
            confirmed=False,
        )
        # invalid args or capability_disabled — never ok
        assert result["ok"] is False
        code = result["error"]["code"]
        assert code in {"capability_disabled", "invalid_arguments"}


def test_capability_enable_does_not_bypass_confirmation(
    session: Session, tenant: Tenant, session_settings: Settings
) -> None:
    profile = _profile(session, tenant)
    _set_caps(session, tenant, profile["id"], SMS_SEND=True)
    executor = AIToolExecutor(
        session, hmac_secret=session_settings.metadata_hmac_secret
    )
    result = executor.execute(
        "send_sms",
        tenant_id=tenant.id,
        call_id=None,
        args={
            "customerId": str(uuid.uuid4()),
            "message": "Hello",
            "purpose": "booking_reminder",
        },
        operation_id=uuid.uuid4(),
        confirmed=False,
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "confirmation_required"
    assert "confirmationToken" in result


def test_cross_tenant_capability_cannot_authorize_other_tenant(
    session: Session, tenant: Tenant
) -> None:
    other = Tenant(name="Other Cap", slug=f"other-cap-{uuid.uuid4().hex[:8]}")
    session.add(other)
    session.flush()
    profile_a = _profile(session, tenant)
    # SMS has no CRM-module dependency — safe for isolation matrix.
    _set_caps(session, tenant, profile_a["id"], SMS_SEND=True)
    profile_b = AgentProfileRepository(session).create(
        other.id,
        name="B Desk",
        assistant_name="Bea",
        greeting="Hi",
        is_default=True,
        actor="test",
    )
    _set_caps(session, other, profile_b["id"], SMS_SEND=False)
    with pytest.raises(AgentConfigError) as exc:
        assert_tool_capability(session, other.id, "send_sms")
    assert exc.value.code == "CAPABILITY_DISABLED"
    # Tenant A remains independently enabled
    assert_tool_capability(session, tenant.id, "send_sms")

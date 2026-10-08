"""Phase 31 — AI Guardrails: authoritative data, confirmation, fail-closed."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from callbot_platform.agent_config.capabilities import (
    CAPABILITY_BY_KEY,
    list_capabilities,
)
from callbot_platform.agent_config.enforcement import assert_tool_capability
from callbot_platform.agent_config.errors import AgentConfigError
from callbot_platform.agent_config.service import AgentConfigService
from callbot_platform.ai_guardrails import (
    AUTHORITATIVE_INJECTION_KEYS,
    AuthoritativeData,
    FactProvenance,
    assert_minimum_confirmation_coverage,
    classify_operational_claim,
    confirmation_required_for_tool,
    list_authoritative_categories,
    list_confirmation_required_tools,
    may_state_as_fact,
    unavailable_message,
)
from callbot_platform.ai_guardrails.confirmation_ops import OPERATION_BY_TOOL
from callbot_platform.ai_tools import AIToolExecutor
from callbot_platform.ai_tools.confirmation import issue_confirmation_token
from callbot_platform.ai_tools.registry import TOOL_SPECS
from callbot_platform.ai_tools.types import FORBIDDEN_ARG_KEYS
from callbot_platform.crm.repos.agent_profile_repo import AgentProfileRepository
from callbot_platform.db.models import Tenant
from callbot_platform.rbac.seed import ensure_system_roles_for_tenant

HMAC = "test-metadata-hmac-secret-ai-guardrails"
REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def ai_tenant(session: Session, tenant: Tenant) -> Tenant:
    ensure_system_roles_for_tenant(session, tenant.id)
    session.commit()
    return tenant


def _executor(session: Session) -> AIToolExecutor:
    return AIToolExecutor(session, hmac_secret=HMAC)


def _profile(session: Session, tenant: Tenant) -> dict:
    return AgentProfileRepository(session).create(
        tenant.id,
        name="Front Desk Guardrails",
        assistant_name="Alex",
        greeting="Thanks for calling.",
        voice="marin",
        language="en",
        tone="professional",
        is_default=True,
        actor="test",
    )


# --- Authoritative data / hallucination guards ---------------------------------


def test_authoritative_categories_complete() -> None:
    keys = {c["key"] for c in list_authoritative_categories()}
    assert keys == {item.value for item in AuthoritativeData}
    for required in (
        "PRICE",
        "INVENTORY",
        "AVAILABILITY",
        "TECHNICIAN",
        "CUSTOMER_HISTORY",
        "ORDER_STATUS",
        "PAYMENT_STATUS",
    ):
        assert required in keys


def test_authoritative_tools_exist_in_registry() -> None:
    for cat in list_authoritative_categories():
        assert cat["tools"], f"{cat['key']} must map to tools"
        for tool in cat["tools"]:
            assert tool in TOOL_SPECS, f"{tool} missing from TOOL_SPECS"


def test_authoritative_injection_keys_subset_of_forbidden() -> None:
    missing = AUTHORITATIVE_INJECTION_KEYS - FORBIDDEN_ARG_KEYS
    assert not missing, f"Forbidden args missing injection keys: {missing}"


@pytest.mark.parametrize(
    "key,value",
    [
        ("price", 99),
        ("inventory", 12),
        ("paymentStatus", "paid"),
        ("orderStatus", "shipped"),
        ("technicianName", "Bob"),
        ("assignedTechnicianId", str(uuid.uuid4())),
        ("quantityAvailable", 5),
        ("unitPrice", 1),
    ],
)
def test_cannot_inject_authoritative_values(
    session: Session, ai_tenant: Tenant, key: str, value: object
) -> None:
    result = _executor(session).execute(
        "find_customer",
        tenant_id=ai_tenant.id,
        call_id=None,
        args={"phone": "+15550001111", key: value},
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_arguments"


def test_provenance_fail_closed_without_tool() -> None:
    for cat in AuthoritativeData:
        prov = classify_operational_claim(
            category=cat, tool_ok=False, tool_payload=None
        )
        assert prov == FactProvenance.UNKNOWN
        assert may_state_as_fact(prov) is False
    assert "don't have" in unavailable_message().lower()


def test_provenance_authoritative_on_tool_ok() -> None:
    prov = classify_operational_claim(
        category=AuthoritativeData.PRICE,
        tool_ok=True,
        tool_payload={"amount": "49.00"},
    )
    assert prov == FactProvenance.AUTHORITATIVE_TOOL
    assert may_state_as_fact(prov) is True


def test_prompt_anti_hallucination_rules() -> None:
    safety = (REPO_ROOT / "voice-agent/src/prompts/safety.py").read_text()
    tools = (REPO_ROOT / "voice-agent/src/prompts/tool_rules.py").read_text()
    combined = (safety + tools).lower()
    for phrase in (
        "price",
        "inventory",
        "availability",
        "technician",
        "customer history",
        "order status",
        "payment status",
    ):
        assert phrase in combined
    assert "don't have that information" in combined or "unavailable" in combined


# --- Confirmation ----------------------------------------------------------------


def test_minimum_confirmation_coverage() -> None:
    assert_minimum_confirmation_coverage()


def test_confirmation_registry_matches_tool_specs() -> None:
    for item in list_confirmation_required_tools():
        spec = TOOL_SPECS[item["tool"]]
        assert spec.confirmation_required is True
        assert confirmation_required_for_tool(item["tool"]) is True


@pytest.mark.parametrize(
    "tool,args",
    [
        (
            "create_booking",
            {
                "customerId": str(uuid.uuid4()),
                "serviceId": str(uuid.uuid4()),
                "startsAt": "2030-01-01T10:00:00+00:00",
                "endsAt": "2030-01-01T11:00:00+00:00",
                "timezone": "UTC",
            },
        ),
        (
            "cancel_appointment",
            {"appointmentId": str(uuid.uuid4()), "reason": "test"},
        ),
        (
            "reschedule_appointment",
            {
                "appointmentId": str(uuid.uuid4()),
                "startsAt": "2030-01-02T10:00:00+00:00",
                "endsAt": "2030-01-02T11:00:00+00:00",
                "timezone": "UTC",
            },
        ),
        (
            "create_order",
            {
                "customerId": str(uuid.uuid4()),
                "items": [{"variantId": str(uuid.uuid4()), "quantity": 1}],
            },
        ),
        (
            "create_payment_link",
            {"invoiceId": str(uuid.uuid4())},
        ),
        (
            "cancel_membership",
            {"membershipId": str(uuid.uuid4())},
        ),
    ],
)
def test_mutation_without_confirmation_rejected(
    session: Session, ai_tenant: Tenant, tool: str, args: dict
) -> None:
    assert TOOL_SPECS[tool].confirmation_required
    result = _executor(session).execute(
        tool,
        tenant_id=ai_tenant.id,
        call_id=None,
        args=args,
        confirmed=False,
        operation_id=uuid.uuid4(),
    )
    assert result["ok"] is False
    # No active profile → capability gate skipped; confirmation must fire.
    assert result["error"]["code"] == "confirmation_required"
    assert result.get("confirmationToken")


def test_confirmation_bound_to_operation_not_cross_tool(
    session: Session, ai_tenant: Tenant
) -> None:
    """Token for create_customer must not authorize update_customer."""
    ex = _executor(session)
    op = uuid.uuid4()
    args_a = {
        "phone": "+15558880001",
        "firstName": "Ada",
        "lastName": "Lovelace",
    }
    prep = ex.execute(
        "create_customer",
        tenant_id=ai_tenant.id,
        call_id=None,
        args=args_a,
        confirmed=False,
        operation_id=op,
    )
    assert prep["error"]["code"] == "confirmation_required"
    token = prep["confirmationToken"]

    other = ex.execute(
        "update_customer",
        tenant_id=ai_tenant.id,
        call_id=None,
        args={
            "customerId": str(uuid.uuid4()),
            "firstName": "Hacked",
        },
        confirmed=True,
        confirmation_token=token,
        operation_id=op,
    )
    assert other["ok"] is False
    assert other["error"]["code"] == "confirmation_required"


def test_confirmation_expired_rejected(
    session: Session, ai_tenant: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    from callbot_platform.ai_tools import executor as executor_mod

    ex = _executor(session)
    op = uuid.uuid4()
    wire = {
        "phone": "+15558880002",
        "firstName": "Grace",
        "lastName": "Hopper",
    }
    prep = ex.execute(
        "create_customer",
        tenant_id=ai_tenant.id,
        call_id=None,
        args=wire,
        confirmed=False,
        operation_id=op,
    )
    assert prep["error"]["code"] == "confirmation_required"
    token = prep["confirmationToken"]

    monkeypatch.setattr(
        executor_mod, "verify_confirmation_status", lambda **_k: "expired"
    )
    result = ex.execute(
        "create_customer",
        tenant_id=ai_tenant.id,
        call_id=None,
        args=wire,
        confirmed=True,
        confirmation_token=token,
        operation_id=op,
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "expired"


def test_confirmation_replay_different_args_rejected(
    session: Session, ai_tenant: Tenant
) -> None:
    ex = _executor(session)
    op = uuid.uuid4()
    args = {
        "phone": "+15558880003",
        "firstName": "Alan",
        "lastName": "Turing",
    }
    prep = ex.execute(
        "create_customer",
        tenant_id=ai_tenant.id,
        call_id=None,
        args=args,
        confirmed=False,
        operation_id=op,
    )
    token = prep["confirmationToken"]
    tampered = ex.execute(
        "create_customer",
        tenant_id=ai_tenant.id,
        call_id=None,
        args={**args, "firstName": "Eve"},
        confirmed=True,
        confirmation_token=token,
        operation_id=op,
    )
    assert tampered["ok"] is False
    assert tampered["error"]["code"] == "confirmation_required"


def test_operation_classes_cover_critical_tools() -> None:
    for tool, op in (
        ("create_booking", "BOOKING"),
        ("cancel_appointment", "CANCELLATION"),
        ("reschedule_appointment", "RESCHEDULE"),
        ("create_order", "ORDER_PLACEMENT"),
        ("create_payment_link", "PAYMENT_ACTION"),
        ("cancel_membership", "DESTRUCTIVE_CHANGE"),
    ):
        assert OPERATION_BY_TOOL[tool].value == op


# --- Authorization / fail-closed -------------------------------------------------


def test_unknown_tool_rejected(session: Session, ai_tenant: Tenant) -> None:
    result = _executor(session).execute(
        "invent_price_from_thin_air",
        tenant_id=ai_tenant.id,
        call_id=None,
        args={},
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "not_found"


def test_malformed_args_rejected(session: Session, ai_tenant: Tenant) -> None:
    result = _executor(session).execute(
        "create_order",
        tenant_id=ai_tenant.id,
        call_id=None,
        args={
            "customerId": str(uuid.uuid4()),
            "items": [{"variantId": str(uuid.uuid4()), "quantity": 0}],
        },
        operation_id=uuid.uuid4(),
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_arguments"


def test_disabled_capability_blocks_before_mutation(
    session: Session, ai_tenant: Tenant
) -> None:
    profile = _profile(session, ai_tenant)
    AgentConfigService(session).update_config(
        ai_tenant.id,
        uuid.UUID(profile["id"]),
        actor="owner@guard31.test",
        capabilities={
            **dict.fromkeys(CAPABILITY_BY_KEY, False),
            "CALL_ANSWERING": True,
            "APPOINTMENT_BOOK": False,
        },
        status="active",
    )
    with pytest.raises(AgentConfigError) as exc:
        assert_tool_capability(session, ai_tenant.id, "create_booking")
    assert exc.value.code == "CAPABILITY_DISABLED"

    result = _executor(session).execute(
        "create_booking",
        tenant_id=ai_tenant.id,
        call_id=None,
        args={
            "customerId": str(uuid.uuid4()),
            "serviceId": str(uuid.uuid4()),
            "startsAt": "2030-01-01T10:00:00+00:00",
            "endsAt": "2030-01-01T11:00:00+00:00",
            "timezone": "UTC",
        },
        operation_id=uuid.uuid4(),
        confirmed=False,
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "capability_disabled"


def test_catalog_exposes_guardrails(session: Session, ai_tenant: Tenant) -> None:
    _profile(session, ai_tenant)
    catalog = AgentConfigService(session).catalog()
    assert "guardrails" in catalog
    assert catalog["guardrails"]["authoritative_data"]
    assert catalog["guardrails"]["confirmation_required_tools"]
    assert "does not bypass" in catalog["guardrails"]["note"].lower()
    caps = list_capabilities()
    booking = next(c for c in caps if c["key"] == "APPOINTMENT_BOOK")
    assert booking["confirmation_required"] is True


def test_confirmation_required_unknown_tool_fail_closed() -> None:
    assert confirmation_required_for_tool("totally_unknown_tool") is True


def test_issue_confirmation_token_binds_fingerprint() -> None:
    op = uuid.uuid4()
    tenant = uuid.uuid4()
    args = {"phone": "+15550001111", "firstName": "A"}
    token = issue_confirmation_token(
        secret=HMAC,
        tenant_id=tenant,
        call_id=None,
        tool_name="create_customer",
        operation_id=op,
        args=args,
    )
    assert token

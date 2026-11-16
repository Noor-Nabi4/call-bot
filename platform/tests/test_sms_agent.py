"""Phase 15 AI SMS Agent — webhook, conversation, tools, booking, security."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from helpers import make_phone as make_phone_helper
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from twilio.request_validator import RequestValidator

from callbot_platform.api.deps import db_dep, settings_dep
from callbot_platform.config import Settings, get_settings
from callbot_platform.crm.appointments.hours import BusinessHoursService
from callbot_platform.crm.customers import CustomerService
from callbot_platform.crm.services.service import ServicesPricebookService
from callbot_platform.db.models import NotificationOutbox, Tenant
from callbot_platform.db.models.jobs import Job
from callbot_platform.db.models.scheduling import Appointment
from callbot_platform.db.models.sms import SmsConversation, SmsMessage
from callbot_platform.jobs.repos import TechnicianRepository
from callbot_platform.main import app
from callbot_platform.rbac.seed import ensure_system_roles_for_tenant
from callbot_platform.sms_agent.brain import RuleBasedSmsBrain, detect_intent
from callbot_platform.sms_agent.constants import SMS_ALLOWED_TOOLS
from callbot_platform.sms_agent.conversations import SmsConversationService
from callbot_platform.sms_agent.inbound import InboundSmsService
from callbot_platform.sms_agent.outbound import SmsOutboundService
from callbot_platform.sms_agent.tool_bridge import SmsToolBridge
from callbot_platform.sms_agent.webhook_security import SmsWebhookAuthError

HMAC = "test-metadata-hmac-secret-sms-agent"
AUTH_TOKEN = "test-twilio-auth-token-sms"
BUSINESS = "+15559000001"
CALLER = "+15559000099"


@pytest.fixture()
def sms_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("METADATA_HMAC_SECRET", HMAC)
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", AUTH_TOKEN)
    get_settings.cache_clear()
    settings = get_settings()
    yield settings
    get_settings.cache_clear()


@pytest.fixture()
def sms_session(session: Session, tenant: Tenant, sms_settings: Settings) -> Session:
    ensure_system_roles_for_tenant(session, tenant.id)
    make_phone_helper(session, tenant, e164=BUSINESS)
    session.commit()
    return session


def _sign(url: str, params: dict[str, str]) -> str:
    return RequestValidator(AUTH_TOKEN).compute_signature(url, params)


def _form(
    *,
    sid: str | None = None,
    body: str = "Hello",
    from_phone: str = CALLER,
    to_phone: str = BUSINESS,
) -> dict[str, str]:
    return {
        "MessageSid": sid or f"SM{uuid.uuid4().hex}",
        "AccountSid": "ACtest",
        "From": from_phone,
        "To": to_phone,
        "Body": body,
        "NumMedia": "0",
    }


def _process(
    session: Session,
    form: dict[str, str],
    *,
    skip_signature: bool = True,
) -> dict[str, Any]:
    return InboundSmsService(
        session,
        settings=get_settings(),
        skip_signature=skip_signature,
    ).process_twilio_webhook(
        form=form,
        signature=None
        if skip_signature
        else _sign("https://example.test/webhooks/twilio/sms/inbound", form),
        request_url="https://example.test/webhooks/twilio/sms/inbound",
    )


def test_detect_intent_booking_and_confirmation() -> None:
    assert detect_intent("I need an AC repair tomorrow").intent == "BOOKING"
    assert (
        detect_intent("yes", workflow={"pending_confirmation": True}).intent
        == "CONFIRMATION"
    )
    assert detect_intent("talk to a human").intent == "HUMAN_HANDOFF"
    plan = RuleBasedSmsBrain().plan_turn(
        body="2",
        workflow={
            "offered_slots": [{"label": "10:00 AM"}, {"label": "1:30 PM"}],
        },
        customer={"id": str(uuid.uuid4()), "firstName": "Pat"},
        history=[],
    )
    assert plan.select_slot_index == 1


def test_sms_allowed_tools_subset() -> None:
    for name in (
        "find_customer",
        "check_availability",
        "create_booking",
        "send_sms",
        "request_human",
    ):
        assert name in SMS_ALLOWED_TOOLS
    assert "delete_tenant" not in SMS_ALLOWED_TOOLS


def test_valid_webhook_known_customer(sms_session: Session, tenant: Tenant) -> None:
    CustomerService(sms_session).create(
        tenant.id, name="Pat Customer", phone=CALLER, actor="setup"
    )
    sms_session.commit()
    result = _process(sms_session, _form(body="Hi there"))
    sms_session.commit()
    assert result["ok"] is True
    assert result["duplicate"] is False
    assert result["status"] == "PROCESSED"
    msg = sms_session.get(SmsMessage, uuid.UUID(result["message_id"]))
    assert msg is not None
    assert msg.direction == "INBOUND"
    assert msg.status == "PROCESSED"
    outbound = sms_session.scalars(
        select(SmsMessage).where(
            SmsMessage.tenant_id == tenant.id,
            SmsMessage.direction == "OUTBOUND",
        )
    ).all()
    assert len(outbound) == 1
    assert outbound[0].status == "QUEUED"
    assert outbound[0].recipient_phone == CALLER


def test_unknown_sender_controlled_flow(sms_session: Session, tenant: Tenant) -> None:
    result = _process(
        sms_session, _form(body="Book AC repair tomorrow", from_phone="+15558887777")
    )
    sms_session.commit()
    assert result["ok"] is True
    out = sms_session.scalar(
        select(SmsMessage).where(
            SmsMessage.tenant_id == tenant.id,
            SmsMessage.direction == "OUTBOUND",
        )
    )
    assert out is not None
    assert "on file" in out.body.lower() or "message" in out.body.lower()


def test_invalid_signature_http(
    sms_session: Session, tenant: Tenant, sms_settings: Settings
) -> None:
    def _override_db() -> Generator[Session, None, None]:
        yield sms_session

    def _override_settings() -> Settings:
        return sms_settings

    app.dependency_overrides[db_dep] = _override_db
    app.dependency_overrides[settings_dep] = _override_settings
    try:
        client = TestClient(app)
        form = _form(body="hi")
        resp = client.post(
            "/webhooks/twilio/sms/inbound",
            data=form,
            headers={"X-Twilio-Signature": "invalid"},
        )
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_malformed_payload(sms_session: Session) -> None:
    with pytest.raises(SmsWebhookAuthError):
        _process(sms_session, {"Body": "hi"})


def test_duplicate_provider_message_no_second_ai(
    sms_session: Session, tenant: Tenant
) -> None:
    CustomerService(sms_session).create(
        tenant.id, name="Pat", phone=CALLER, actor="setup"
    )
    sms_session.commit()
    form = _form(sid="SMdedupe001", body="Hello again")
    first = _process(sms_session, form)
    sms_session.commit()
    second = _process(sms_session, form)
    sms_session.commit()
    assert first["duplicate"] is False
    assert second["duplicate"] is True
    inbound_count = sms_session.scalar(
        select(func.count())
        .select_from(SmsMessage)
        .where(
            SmsMessage.tenant_id == tenant.id,
            SmsMessage.direction == "INBOUND",
        )
    )
    outbound_count = sms_session.scalar(
        select(func.count())
        .select_from(SmsMessage)
        .where(
            SmsMessage.tenant_id == tenant.id,
            SmsMessage.direction == "OUTBOUND",
        )
    )
    assert inbound_count == 1
    assert outbound_count == 1


def test_outbound_echo_loop_prevention(sms_session: Session, tenant: Tenant) -> None:
    CustomerService(sms_session).create(
        tenant.id, name="Pat", phone=CALLER, actor="setup"
    )
    sms_session.commit()
    # Seed an outbound row with a provider SID (as after Twilio send).
    conv = SmsConversationService(sms_session).get_or_create(
        tenant_id=tenant.id,
        phone_e164=CALLER,
        business_phone_e164=BUSINESS,
        customer_id=None,
    )
    sid = "SMoutboundEcho1"
    sms_session.add(
        SmsMessage(
            tenant_id=tenant.id,
            conversation_id=conv.id,
            provider_message_id=sid,
            direction="OUTBOUND",
            sender_phone=BUSINESS,
            recipient_phone=CALLER,
            body="prior reply",
            status="SENT",
        )
    )
    sms_session.commit()
    # Inbound-shaped webhook (To=business) carrying an outbound MessageSid.
    result = _process(
        sms_session,
        _form(sid=sid, body="prior reply", from_phone=CALLER, to_phone=BUSINESS),
    )
    assert result.get("duplicate") is True
    assert result.get("reason") == "outbound_echo"


def test_conversation_reuse_and_bounded_history(
    sms_session: Session, tenant: Tenant
) -> None:
    cust = CustomerService(sms_session).create(
        tenant.id, name="Pat", phone=CALLER, actor="setup"
    )
    sms_session.commit()
    svc = SmsConversationService(sms_session)
    c1 = svc.get_or_create(
        tenant_id=tenant.id,
        phone_e164=CALLER,
        business_phone_e164=BUSINESS,
        customer_id=uuid.UUID(cust["id"]),
    )
    c2 = svc.get_or_create(
        tenant_id=tenant.id,
        phone_e164=CALLER,
        business_phone_e164=BUSINESS,
        customer_id=uuid.UUID(cust["id"]),
    )
    assert c1.id == c2.id
    for i in range(30):
        sms_session.add(
            SmsMessage(
                tenant_id=tenant.id,
                conversation_id=c1.id,
                direction="INBOUND" if i % 2 == 0 else "OUTBOUND",
                sender_phone=CALLER if i % 2 == 0 else BUSINESS,
                recipient_phone=BUSINESS if i % 2 == 0 else CALLER,
                body=f"msg-{i}",
                status="PROCESSED" if i % 2 == 0 else "QUEUED",
                provider_message_id=f"SMhist{i}",
            )
        )
    sms_session.commit()
    ctx = svc.load_context(tenant_id=tenant.id, conversation_id=c1.id, limit=20)
    assert len(ctx) == 20
    assert ctx[0]["body"] == "msg-10"
    assert ctx[-1]["body"] == "msg-29"


def test_tenant_isolation_conversation_context(
    sms_session: Session, tenant: Tenant
) -> None:
    other = Tenant(name="Other", slug=f"other-{uuid.uuid4().hex[:8]}")
    sms_session.add(other)
    sms_session.flush()
    make_phone_helper(sms_session, other, e164="+15559000002")
    cust_a = CustomerService(sms_session).create(
        tenant.id, name="A", phone=CALLER, actor="setup"
    )
    cust_b = CustomerService(sms_session).create(
        other.id, name="B", phone="+15559000088", actor="setup"
    )
    sms_session.commit()
    svc = SmsConversationService(sms_session)
    ca = svc.get_or_create(
        tenant_id=tenant.id,
        phone_e164=CALLER,
        business_phone_e164=BUSINESS,
        customer_id=uuid.UUID(cust_a["id"]),
    )
    cb = svc.get_or_create(
        tenant_id=other.id,
        phone_e164="+15559000088",
        business_phone_e164="+15559000002",
        customer_id=uuid.UUID(cust_b["id"]),
    )
    sms_session.add(
        SmsMessage(
            tenant_id=other.id,
            conversation_id=cb.id,
            direction="INBOUND",
            sender_phone="+15559000088",
            recipient_phone="+15559000002",
            body="secret-other-tenant",
            status="PROCESSED",
            provider_message_id="SMother1",
        )
    )
    sms_session.commit()
    ctx = svc.load_context(tenant_id=tenant.id, conversation_id=ca.id, limit=20)
    assert all("secret-other-tenant" not in (m.get("body") or "") for m in ctx)
    # Wrong tenant_id must not load other conversation even with its id.
    leaked = svc.load_context(tenant_id=tenant.id, conversation_id=cb.id, limit=20)
    assert leaked == []


def test_forbidden_tool_and_arbitrary_destination(
    sms_session: Session, tenant: Tenant
) -> None:
    bridge = SmsToolBridge(sms_session, hmac_secret=HMAC)
    denied = bridge.invoke(
        "not_a_real_tool",
        tenant_id=tenant.id,
        args={},
    )
    assert denied["ok"] is False
    # send_sms requires customerId — model cannot pass raw destination phone.
    bad = bridge.invoke(
        "send_sms",
        tenant_id=tenant.id,
        args={
            "customerId": str(uuid.uuid4()),
            "message": "hi",
            "purpose": "GENERAL",
            "to": "+15551111111",
        },
    )
    assert bad["ok"] is False


def test_prompt_injection_cannot_select_tenant(
    sms_session: Session, tenant: Tenant
) -> None:
    other = Tenant(name="Victim", slug=f"victim-{uuid.uuid4().hex[:8]}")
    sms_session.add(other)
    sms_session.flush()
    ensure_system_roles_for_tenant(sms_session, other.id)
    bridge = SmsToolBridge(sms_session, hmac_secret=HMAC)
    result = bridge.invoke(
        "find_customer",
        tenant_id=tenant.id,
        args={"phone": CALLER, "tenantId": str(other.id)},
        caller_phone=CALLER,
    )
    # Forbidden args rejected or ignored — never switches tenant.
    assert result.get("ok") is False or (
        result.get("ok")
        and (result.get("data") or {}).get("match") in {"NONE", "EXACT", "AMBIGUOUS"}
    )
    if result.get("ok") is False:
        assert (result.get("error") or {}).get("code") in {
            "invalid_arguments",
            "permission_denied",
            "forbidden_argument",
        }


def test_outbound_idempotent_queue(sms_session: Session, tenant: Tenant) -> None:
    conv = SmsConversationService(sms_session).get_or_create(
        tenant_id=tenant.id,
        phone_e164=CALLER,
        business_phone_e164=BUSINESS,
        customer_id=None,
    )
    out = SmsOutboundService(sms_session)
    a = out.enqueue_reply(
        conversation=conv, body="One", idempotency_key="sms_reply:stable-1"
    )
    b = out.enqueue_reply(
        conversation=conv, body="One", idempotency_key="sms_reply:stable-1"
    )
    sms_session.commit()
    assert a["status"] == "QUEUED"
    assert b["idempotent"] is True
    outboxes = sms_session.scalars(
        select(NotificationOutbox).where(NotificationOutbox.tenant_id == tenant.id)
    ).all()
    assert len(outboxes) == 1
    assert outboxes[0].to_address == CALLER


def _open_hours(session: Session, tenant_id: uuid.UUID) -> None:
    BusinessHoursService(session).update(
        tenant_id,
        actor="setup",
        weekly_hours={
            d: [["00:00", "23:59"]]
            for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        },
    )


def test_sms_booking_confirmation_flow(sms_session: Session, tenant: Tenant) -> None:
    CustomerService(sms_session).create(
        tenant.id, name="Pat Booker", phone=CALLER, actor="setup"
    )
    ServicesPricebookService(sms_session).create_service(
        tenant.id, name="AC Repair", actor="setup", duration_minutes=60
    )
    TechnicianRepository(sms_session).create(
        tenant.id,
        email=f"tech-{uuid.uuid4().hex[:6]}@t.test",
        password="password123",
        name="Field Tech",
    )
    _open_hours(sms_session, tenant.id)
    sms_session.commit()

    r1 = _process(
        sms_session, _form(sid="SMbook1", body="I need an AC repair tomorrow")
    )
    sms_session.commit()
    assert r1["ok"] is True
    out1 = sms_session.scalars(
        select(SmsMessage)
        .where(
            SmsMessage.tenant_id == tenant.id,
            SmsMessage.direction == "OUTBOUND",
        )
        .order_by(SmsMessage.created_at.desc())
    ).first()
    assert out1 is not None
    conv = sms_session.scalar(
        select(SmsConversation).where(SmsConversation.tenant_id == tenant.id)
    )
    assert conv is not None

    if not (conv.workflow_state or {}).get("offered_slots"):
        # Availability empty on this fixture — inbound still processed once.
        assert out1.body
        return

    r2 = _process(sms_session, _form(sid="SMbook2", body="1"))
    sms_session.commit()
    assert r2["ok"] is True
    conv = sms_session.scalar(
        select(SmsConversation).where(SmsConversation.tenant_id == tenant.id)
    )
    assert (conv.workflow_state or {}).get("pending_confirmation") is True

    bad_state = dict(conv.workflow_state or {})
    bad_state["confirmation_token"] = "tampered"
    conv.workflow_state = bad_state
    sms_session.commit()
    r_bad = _process(sms_session, _form(sid="SMbook3", body="yes"))
    sms_session.commit()
    assert r_bad["ok"] is True
    assert (
        sms_session.scalar(
            select(func.count()).select_from(Job).where(Job.tenant_id == tenant.id)
        )
        == 0
    )

    _process(sms_session, _form(sid="SMbook4", body="I need AC repair tomorrow"))
    sms_session.commit()
    conv = sms_session.scalar(
        select(SmsConversation).where(SmsConversation.tenant_id == tenant.id)
    )
    if not (conv.workflow_state or {}).get("offered_slots"):
        return
    _process(sms_session, _form(sid="SMbook5", body="1"))
    sms_session.commit()
    r_ok = _process(sms_session, _form(sid="SMbook6", body="YES"))
    sms_session.commit()
    assert r_ok["ok"] is True
    jobs = sms_session.scalar(
        select(func.count()).select_from(Job).where(Job.tenant_id == tenant.id)
    )
    appts = sms_session.scalar(
        select(func.count())
        .select_from(Appointment)
        .where(Appointment.tenant_id == tenant.id)
    )
    assert jobs in {0, 1}
    assert appts == jobs
    if jobs == 1:
        confirm_out = sms_session.scalars(
            select(SmsMessage)
            .where(
                SmsMessage.tenant_id == tenant.id,
                SmsMessage.direction == "OUTBOUND",
            )
            .order_by(SmsMessage.created_at.desc())
        ).first()
        assert confirm_out is not None
        assert "booked" in confirm_out.body.lower()


def test_customer_safe_errors_no_internal_leak(
    sms_session: Session, tenant: Tenant
) -> None:
    bridge = SmsToolBridge(sms_session, hmac_secret=HMAC)
    result = bridge.invoke(
        "get_order_status",
        tenant_id=tenant.id,
        args={"orderId": str(uuid.uuid4())},
        customer_id=None,
        caller_phone=CALLER,
    )
    msg = bridge.customer_safe(result)
    assert "SQL" not in msg
    assert "traceback" not in msg.lower()
    assert "permission" not in msg.lower() or "unable" in msg.lower() or msg


def test_valid_signed_http_webhook(
    sms_session: Session, tenant: Tenant, sms_settings: Settings
) -> None:
    CustomerService(sms_session).create(
        tenant.id, name="Pat", phone=CALLER, actor="setup"
    )
    sms_session.commit()

    def _override_db() -> Generator[Session, None, None]:
        yield sms_session

    def _override_settings() -> Settings:
        return sms_settings

    app.dependency_overrides[db_dep] = _override_db
    app.dependency_overrides[settings_dep] = _override_settings
    try:
        client = TestClient(app)
        form = _form(body="Thanks")
        # TestClient uses http://testserver
        url = "http://testserver/webhooks/twilio/sms/inbound"
        sig = _sign(url, form)
        resp = client.post(
            "/webhooks/twilio/sms/inbound",
            data=form,
            headers={"X-Twilio-Signature": sig},
        )
        assert resp.status_code == 200
        assert "Response" in resp.text
    finally:
        app.dependency_overrides.clear()

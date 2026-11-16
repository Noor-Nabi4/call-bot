"""Phase 25 Communication Templates: render, validate, enqueue, isolation."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.automations.actions import validate_action_config
from callbot_platform.communication_templates.constants import SmsTemplateKey
from callbot_platform.communication_templates.errors import CommunicationTemplateError
from callbot_platform.communication_templates.renderer import (
    render,
    validate_template_text,
)
from callbot_platform.communication_templates.service import (
    CommunicationTemplateService,
)
from callbot_platform.db.models import (
    Customer,
    CustomerPhone,
    NotificationOutbox,
    Tenant,
)


@pytest.fixture()
def tenant_b(session: Session) -> Tenant:
    row = Tenant(name="CT Other", slug=f"ct-{uuid.uuid4().hex[:8]}")
    session.add(row)
    session.flush()
    return row


def _customer_with_phone(session: Session, tenant_id: uuid.UUID) -> Customer:
    cust = Customer(
        tenant_id=tenant_id,
        name="Alex Rivera",
        first_name="Alex",
        last_name="Rivera",
        email="alex@example.com",
        status="ACTIVE",
    )
    session.add(cust)
    session.flush()
    session.add(
        CustomerPhone(
            tenant_id=tenant_id,
            customer_id=cust.id,
            e164="+15551234567",
        )
    )
    session.flush()
    return cust


def test_validate_rejects_unknown_and_forbidden() -> None:
    errs = validate_template_text(
        channel="SMS",
        template_key="BOOKING_CONFIRMATION",
        body="Hi {{appointment.foo}}",
    )
    assert any("Unknown template variable" in e for e in errs)

    errs2 = validate_template_text(
        channel="SMS",
        template_key="BOOKING_CONFIRMATION",
        body='{{__import__("os")}}',
    )
    assert any("forbidden" in e.lower() for e in errs2)

    errs3 = validate_template_text(
        channel="SMS",
        template_key="BOOKING_CONFIRMATION",
        body="Pay {{invoice.payment_url}}",
    )
    assert any("not available" in e for e in errs3)

    for bad in (
        "{{__class__}}",
        "{{constructor}}",
        "{{customer.__class__}}",
        "{{env.SECRET}}",
        "{{settings.SECRET_KEY}}",
        "{{config.secret}}",
        "{{request.headers}}",
        "{{customer.password}}",
    ):
        bad_errs = validate_template_text(
            channel="SMS",
            template_key="BOOKING_CONFIRMATION",
            body=f"Hi {bad}",
        )
        assert bad_errs, f"expected rejection for {bad}"
        with pytest.raises(CommunicationTemplateError):
            render(
                f"Hi {bad}",
                {"customer.first_name": "Alex"},
                channel="SMS",
                template_key="BOOKING_CONFIRMATION",
            )


def test_render_sms_and_email_ok() -> None:
    ctx = {
        "customer.first_name": "Alex",
        "appointment.service": "HVAC",
        "appointment.date": "Mon",
        "appointment.time": "10am",
        "business.name": "Acme",
    }
    out = render(
        "Hi {{customer.first_name}}, {{appointment.service}} with {{business.name}} "
        "on {{appointment.date}} at {{appointment.time}}.",
        ctx,
        channel="SMS",
        template_key="BOOKING_CONFIRMATION",
    )
    assert "Alex" in out["body"]
    assert "{{" not in out["body"]

    email = render(
        "Hello {{customer.first_name}}",
        ctx,
        channel="EMAIL",
        template_key="BOOKING",
        subject="Confirmed with {{business.name}}",
    )
    assert email["subject"] == "Confirmed with Acme"


def test_seed_list_preview_enqueue(session: Session, tenant: Tenant) -> None:
    cust = _customer_with_phone(session, tenant.id)
    svc = CommunicationTemplateService(session)
    items = svc.list(tenant.id, channel="SMS")
    keys = {i["template_key"] for i in items}
    assert SmsTemplateKey.BOOKING_CONFIRMATION.value in keys
    assert len(items) >= 8

    tmpl = next(
        i
        for i in items
        if i["template_key"] == SmsTemplateKey.BOOKING_CONFIRMATION.value
    )
    preview = svc.preview(tenant.id, uuid.UUID(tmpl["id"]))
    assert preview["channel"] == "SMS"
    assert "rendered" in preview
    assert "{{" not in preview["rendered"]

    queued = svc.render_and_enqueue(
        tenant_id=tenant.id,
        channel="SMS",
        template_key="BOOKING_CONFIRMATION",
        payload={
            "customer_id": str(cust.id),
            "service": "HVAC",
            "starts_at": "2026-10-12T15:00:00+00:00",
        },
        idempotency_key=f"ct-test-{uuid.uuid4().hex}",
        customer_id=cust.id,
    )
    assert queued["status"] == "pending"
    outbox = session.get(NotificationOutbox, uuid.UUID(queued["outbox_id"]))
    assert outbox is not None
    assert outbox.channel == "sms"
    assert outbox.payload.get("template_key") == "BOOKING_CONFIRMATION"
    assert outbox.payload.get("template_version") == 1

    # Idempotent re-enqueue with same key
    third = svc.render_and_enqueue(
        tenant_id=tenant.id,
        channel="SMS",
        template_key="BOOKING_CONFIRMATION",
        payload={"customer_id": str(cust.id)},
        idempotency_key=outbox.idempotency_key,
        customer_id=cust.id,
    )
    assert third.get("idempotent") is True


def test_marketing_opt_out(session: Session, tenant: Tenant) -> None:
    cust = _customer_with_phone(session, tenant.id)
    cust.marketing_sms_allowed = False
    session.flush()
    svc = CommunicationTemplateService(session)
    svc.ensure_defaults(tenant.id)
    result = svc.render_and_enqueue(
        tenant_id=tenant.id,
        channel="SMS",
        template_key="REVIEW_REQUEST",
        payload={"customer_id": str(cust.id), "review_url": "https://example.com/r"},
        idempotency_key=f"review-{uuid.uuid4().hex}",
        customer_id=cust.id,
        review_url="https://example.com/r",
    )
    assert result["status"] == "skipped"
    assert result["reason"] == "marketing_sms_opted_out"


def test_tenant_isolation(session: Session, tenant: Tenant, tenant_b: Tenant) -> None:
    svc = CommunicationTemplateService(session)
    items = svc.list(tenant.id)
    tid = uuid.UUID(items[0]["id"])
    with pytest.raises(CommunicationTemplateError) as exc:
        svc.get(tenant_b.id, tid)
    assert exc.value.code == "template_not_found"


def test_publish_versioning(session: Session, tenant: Tenant) -> None:
    svc = CommunicationTemplateService(session)
    items = svc.list(tenant.id, channel="SMS")
    tid = uuid.UUID(items[0]["id"])
    updated = svc.update(
        tenant.id,
        tid,
        actor="admin",
        body_template=(
            "Hi {{customer.first_name}}, your {{appointment.service}} appointment with "
            "{{business.name}} is confirmed for {{appointment.date}} at "
            "{{appointment.time}}."
        ),
        publish=True,
    )
    assert updated["active_version"] == 2


def test_automation_send_sms_template_key(session: Session, tenant: Tenant) -> None:
    from callbot_platform.automations.constants import AutomationEventType
    from callbot_platform.automations.engine import AutomationEngine
    from callbot_platform.automations.events import emit_automation_event
    from callbot_platform.automations.service import AutomationWorkflowService

    cust = _customer_with_phone(session, tenant.id)
    CommunicationTemplateService(session).ensure_defaults(tenant.id)
    cfg = validate_action_config("SEND_SMS", {"template_key": "BOOKING_CONFIRMATION"})
    assert cfg["template_key"] == "BOOKING_CONFIRMATION"

    svc = AutomationWorkflowService(session)
    wf = svc.create(
        tenant.id,
        name=f"Booking SMS {uuid.uuid4().hex[:6]}",
        trigger_event=AutomationEventType.APPOINTMENT_CREATED.value,
        actor="t",
        definition={
            "actions": [
                {
                    "type": "SEND_SMS",
                    "config": {"template_key": "BOOKING_CONFIRMATION"},
                }
            ]
        },
    )
    svc.publish(tenant.id, uuid.UUID(wf["id"]), actor="t")
    svc.activate(tenant.id, uuid.UUID(wf["id"]), actor="t")

    event = emit_automation_event(
        session,
        tenant_id=tenant.id,
        event_type="APPOINTMENT_CREATED",
        source="test",
        entity_type="appointment",
        entity_id=uuid.uuid4(),
        payload={
            "customer_id": str(cust.id),
            "service": "Plumbing",
            "starts_at": "2026-10-12T15:00:00+00:00",
        },
        idempotency_key=f"test-appt:{uuid.uuid4().hex}",
    )
    assert event is not None
    AutomationEngine(session).process_event(event)
    session.flush()
    rows = list(
        session.scalars(
            select(NotificationOutbox).where(
                NotificationOutbox.tenant_id == tenant.id,
                NotificationOutbox.channel == "sms",
            )
        ).all()
    )
    assert len(rows) >= 1
    assert any(
        (r.payload or {}).get("template_key") == "BOOKING_CONFIRMATION" for r in rows
    )


def test_channel_mismatch_rejected() -> None:
    from callbot_platform.automations.actions import ActionError

    with pytest.raises(ActionError):
        validate_action_config("SEND_SMS", {"template_key": "BOOKING"})  # email key


def test_seed_covers_all_required_keys(session: Session, tenant: Tenant) -> None:
    from callbot_platform.communication_templates.constants import (
        EMAIL_TEMPLATE_KEYS,
        SMS_TEMPLATE_KEYS,
    )

    svc = CommunicationTemplateService(session)
    sms = {i["template_key"] for i in svc.list(tenant.id, channel="SMS")}
    email = {i["template_key"] for i in svc.list(tenant.id, channel="EMAIL")}
    assert sms >= SMS_TEMPLATE_KEYS
    assert email >= EMAIL_TEMPLATE_KEYS


def test_recipient_not_controlled_by_template_body(
    session: Session, tenant: Tenant
) -> None:
    """Template copy cannot redirect delivery — recipient comes from customer record."""
    cust = _customer_with_phone(session, tenant.id)
    svc = CommunicationTemplateService(session)
    svc.ensure_defaults(tenant.id)
    # Even if body mentions another number, outbox.to_address stays the customer phone.
    queued = svc.render_and_enqueue(
        tenant_id=tenant.id,
        channel="SMS",
        template_key="BOOKING_CONFIRMATION",
        payload={
            "customer_id": str(cust.id),
            "service": "HVAC",
            "starts_at": "2026-10-12T15:00:00+00:00",
        },
        idempotency_key=f"recip-{uuid.uuid4().hex}",
        customer_id=cust.id,
    )
    outbox = session.get(NotificationOutbox, uuid.UUID(queued["outbox_id"]))
    assert outbox is not None
    assert outbox.to_address == "+15551234567"

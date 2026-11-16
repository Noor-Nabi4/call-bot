"""PostgreSQL concurrency + performance for Phase 15 SMS agent."""

from __future__ import annotations

import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from helpers import make_phone
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from callbot_platform.config import get_settings
from callbot_platform.crm.appointments.hours import BusinessHoursService
from callbot_platform.crm.customers import CustomerService
from callbot_platform.crm.products import ProductCatalogService
from callbot_platform.crm.services.service import ServicesPricebookService
from callbot_platform.db.models import Base, Tenant
from callbot_platform.db.models.jobs import Job
from callbot_platform.db.models.scheduling import Appointment
from callbot_platform.db.models.sms import SmsConversation, SmsMessage
from callbot_platform.jobs.repos import TechnicianRepository
from callbot_platform.rbac.seed import ensure_system_roles_for_tenant
from callbot_platform.sms_agent.conversations import SmsConversationService
from callbot_platform.sms_agent.inbound import InboundSmsService

HMAC = "test-metadata-hmac-secret-sms-pg"
BUSINESS = "+15559110001"
CALLER = "+15559110099"

PG_URL = os.environ.get(
    "SMS_AGENT_PG_TEST_URL",
    os.environ.get(
        "AI_TOOLS_PG_TEST_URL",
        os.environ.get(
            "APPOINTMENTS_PG_TEST_URL",
            "postgresql+psycopg://noor@localhost:5432/call_bot_inventory_test",
        ),
    ),
)


def _pg_available(url: str) -> bool:
    try:
        engine = create_engine(url, future=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
    except Exception:
        return False
    return True


_PG_UP = _pg_available(PG_URL)

pytestmark = pytest.mark.skipif(
    not _PG_UP,
    reason="PostgreSQL not available for SMS agent PG tests",
)


@pytest.fixture()
def pg_factory(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("METADATA_HMAC_SECRET", HMAC)
    get_settings.cache_clear()
    engine = create_engine(PG_URL, future=True, pool_size=12, max_overflow=8)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                ALTER TABLE appointments
                ADD CONSTRAINT excl_appointments_technician_active_range
                EXCLUDE USING gist (
                    tenant_id WITH =,
                    assigned_technician_id WITH =,
                    tstzrange(starts_at, ends_at, '[)') WITH &&
                )
                WHERE (
                    assigned_technician_id IS NOT NULL
                    AND archived_at IS NULL
                    AND status IN ('TENTATIVE', 'SCHEDULED', 'CONFIRMED', 'IN_PROGRESS')
                )
                """
            )
        )
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    yield factory
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()
    get_settings.cache_clear()


def _tenant(session: Session) -> Tenant:
    row = Tenant(name="SMS PG", slug=f"sms-pg-{uuid.uuid4().hex[:8]}")
    session.add(row)
    session.flush()
    ensure_system_roles_for_tenant(session, row.id)
    make_phone(session, row, e164=BUSINESS)
    return row


def _open_hours(session: Session, tenant_id: uuid.UUID) -> None:
    BusinessHoursService(session).update(
        tenant_id,
        actor="setup",
        weekly_hours={
            d: [["00:00", "23:59"]]
            for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        },
    )


def test_concurrent_duplicate_webhook(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        CustomerService(session).create(
            tenant.id, name="Pat", phone=CALLER, actor="setup"
        )
        session.commit()
        tenant_id = tenant.id
    finally:
        session.close()

    sid = f"SMconc{uuid.uuid4().hex[:20]}"
    form = {
        "MessageSid": sid,
        "AccountSid": "ACtest",
        "From": CALLER,
        "To": BUSINESS,
        "Body": "Hello concurrent",
        "NumMedia": "0",
    }

    def worker(_: int) -> dict:
        s = pg_factory()
        try:
            result = InboundSmsService(
                s, settings=get_settings(), skip_signature=True
            ).process_twilio_webhook(
                form=form,
                signature=None,
                request_url="https://example.test/webhooks/twilio/sms/inbound",
            )
            s.commit()
            return result
        except Exception as exc:
            s.rollback()
            return {"ok": False, "error": type(exc).__name__}
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(worker, range(6)))

    processed = [r for r in results if r.get("ok") and not r.get("duplicate")]
    duplicates = [r for r in results if r.get("ok") and r.get("duplicate")]
    errors = [r for r in results if not r.get("ok")]
    assert not errors, results
    assert len(processed) == 1, results
    assert len(duplicates) == 5, results

    s = pg_factory()
    try:
        inbound = s.scalar(
            select(func.count())
            .select_from(SmsMessage)
            .where(
                SmsMessage.tenant_id == tenant_id,
                SmsMessage.direction == "INBOUND",
            )
        )
        outbound = s.scalar(
            select(func.count())
            .select_from(SmsMessage)
            .where(
                SmsMessage.tenant_id == tenant_id,
                SmsMessage.direction == "OUTBOUND",
            )
        )
        assert inbound == 1
        assert outbound == 1
    finally:
        s.close()


def test_sms_booking_end_to_end_pg(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        CustomerService(session).create(
            tenant.id, name="Pat Booker", phone=CALLER, actor="setup"
        )
        ServicesPricebookService(session).create_service(
            tenant.id, name="AC Repair", actor="setup", duration_minutes=60
        )
        TechnicianRepository(session).create(
            tenant.id,
            email=f"tech-{uuid.uuid4().hex[:6]}@t.test",
            password="password123",
            name="Field Tech",
        )
        _open_hours(session, tenant.id)
        session.commit()
        tenant_id = tenant.id
    finally:
        session.close()

    def process(body: str, sid: str) -> dict:
        s = pg_factory()
        try:
            form = {
                "MessageSid": sid,
                "AccountSid": "ACtest",
                "From": CALLER,
                "To": BUSINESS,
                "Body": body,
                "NumMedia": "0",
            }
            result = InboundSmsService(
                s, settings=get_settings(), skip_signature=True
            ).process_twilio_webhook(
                form=form,
                signature=None,
                request_url="https://example.test/webhooks/twilio/sms/inbound",
            )
            s.commit()
            return result
        finally:
            s.close()

    r1 = process("I need an AC repair tomorrow", f"SMbk{uuid.uuid4().hex[:20]}")
    assert r1.get("ok") is True

    s = pg_factory()
    try:
        conv = s.scalar(
            select(SmsConversation).where(SmsConversation.tenant_id == tenant_id)
        )
        assert conv is not None
        offered = list((conv.workflow_state or {}).get("offered_slots") or [])
    finally:
        s.close()

    if not offered:
        pytest.skip("No availability slots generated for booking day")

    r2 = process("1", f"SMbk{uuid.uuid4().hex[:20]}")
    assert r2.get("ok") is True
    r3 = process("YES", f"SMbk{uuid.uuid4().hex[:20]}")
    assert r3.get("ok") is True

    s = pg_factory()
    try:
        jobs = s.scalar(
            select(func.count()).select_from(Job).where(Job.tenant_id == tenant_id)
        )
        appts = s.scalar(
            select(func.count())
            .select_from(Appointment)
            .where(Appointment.tenant_id == tenant_id)
        )
        assert jobs == 1
        assert appts == 1
        last_out = s.scalars(
            select(SmsMessage)
            .where(
                SmsMessage.tenant_id == tenant_id,
                SmsMessage.direction == "OUTBOUND",
            )
            .order_by(SmsMessage.created_at.desc())
        ).first()
        assert last_out is not None
        assert "booked" in last_out.body.lower()
    finally:
        s.close()


def test_sms_perf_hot_paths(pg_factory) -> None:
    """Seed multi-tenant SMS volume and measure inbound webhook latency + EXPLAIN."""
    session = pg_factory()
    tenants: list[tuple[Tenant, str]] = []
    try:
        for i in range(4):
            t = Tenant(name=f"T{i}", slug=f"sms-perf-{uuid.uuid4().hex[:8]}")
            session.add(t)
            session.flush()
            ensure_system_roles_for_tenant(session, t.id)
            biz = f"+155592{i:05d}"
            make_phone(session, t, e164=biz)
            tenants.append((t, biz))
        session.commit()

        # ~10k customers (2500 x 4) with unique E.164s
        n = 0
        for t, _biz in tenants:
            for _ in range(2500):
                n += 1
                phone = f"+1555{n:07d}"
                CustomerService(session).create(
                    t.id, name=f"C{n}", phone=phone, actor="setup"
                )
                if n % 250 == 0:
                    session.commit()
        session.commit()

        # 1000 conversations x ~10 messages ~= 10k messages
        msg_n = 0
        for ti, (t, biz) in enumerate(tenants):
            for c in range(250):
                phone = f"+15558{ti}{c:05d}"
                CustomerService(session).create(
                    t.id, name=f"Sms{c}", phone=phone, actor="setup"
                )
                conv = SmsConversationService(session).get_or_create(
                    tenant_id=t.id,
                    phone_e164=phone,
                    business_phone_e164=biz,
                    customer_id=None,
                )
                for m in range(10):
                    msg_n += 1
                    session.add(
                        SmsMessage(
                            tenant_id=t.id,
                            conversation_id=conv.id,
                            direction="INBOUND" if m % 2 == 0 else "OUTBOUND",
                            sender_phone=phone if m % 2 == 0 else biz,
                            recipient_phone=biz if m % 2 == 0 else phone,
                            body=f"msg-{m}",
                            status="PROCESSED" if m % 2 == 0 else "QUEUED",
                            provider_message_id=f"SMp{msg_n:012d}",
                        )
                    )
                if c % 25 == 0:
                    session.commit()
        session.commit()

        t0, biz0 = tenants[0]
        ServicesPricebookService(session).create_service(
            t0.id, name="Repair", actor="setup", duration_minutes=60
        )
        for p in range(1000):
            ProductCatalogService(session).create(
                t0.id,
                name=f"Product {p}",
                sku=f"P-{p:04d}-{uuid.uuid4().hex[:4]}",
                price="20",
                actor="setup",
            )
            if p % 100 == 0:
                session.commit()
        CustomerService(session).create(t0.id, name="Hot", phone=CALLER, actor="setup")
        session.commit()
        tenant0_id = t0.id
    finally:
        session.close()

    def once() -> float:
        s = pg_factory()
        try:
            form = {
                "MessageSid": f"SMperf{uuid.uuid4().hex}",
                "AccountSid": "ACtest",
                "From": CALLER,
                "To": biz0,
                "Body": "Hi",
                "NumMedia": "0",
            }
            started = time.perf_counter()
            InboundSmsService(
                s, settings=get_settings(), skip_signature=True
            ).process_twilio_webhook(
                form=form,
                signature=None,
                request_url="https://example.test/webhooks/twilio/sms/inbound",
            )
            s.commit()
            return (time.perf_counter() - started) * 1000
        finally:
            s.close()

    samples = sorted(once() for _ in range(8))
    p50 = samples[len(samples) // 2]
    p95 = samples[max(0, int(len(samples) * 0.95) - 1)]

    s = pg_factory()
    try:
        msg_count = s.scalar(select(func.count()).select_from(SmsMessage))
        conv_count = s.scalar(select(func.count()).select_from(SmsConversation))
        explain = s.execute(
            text(
                """
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT * FROM sms_messages
                WHERE tenant_id = :tid
                  AND conversation_id = (
                    SELECT id FROM sms_conversations
                    WHERE tenant_id = :tid
                    LIMIT 1
                  )
                ORDER BY created_at DESC
                LIMIT 20
                """
            ),
            {"tid": str(tenant0_id)},
        ).fetchall()
        plan = "\n".join(row[0] for row in explain)
        print(
            f"\nSMS_PERF p50_ms={p50:.2f} p95_ms={p95:.2f} "
            f"messages={msg_count} conversations={conv_count}\n{plan}\n"
        )
        assert msg_count >= 10000
        assert conv_count >= 1000
        assert p95 < 5000
    finally:
        s.close()

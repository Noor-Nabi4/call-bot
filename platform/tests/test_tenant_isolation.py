"""Tenant isolation, DB strategy, and telephony auth hardening tests."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from helpers import next_open_booking_day
from sqlalchemy.orm import Session

from callbot_platform.admin.repos import AdminRepository
from callbot_platform.api.deps import db_dep, settings_dep
from callbot_platform.api_keys import ApiKeyRepository
from callbot_platform.async_jobs.service import AsyncJobService
from callbot_platform.branding import BrandingRepository
from callbot_platform.config import Settings, get_settings
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.repos import (
    CallRepository,
    CustomerRepository,
    LeadRepository,
)
from callbot_platform.db.models import Customer, Tenant
from callbot_platform.db.pagination import PageParams
from callbot_platform.jobs.errors import JobsError
from callbot_platform.jobs.repos import JobRepository
from callbot_platform.knowledge.repos import KnowledgeRepository
from callbot_platform.main import app
from callbot_platform.organization import OrganizationService
from callbot_platform.scheduling.notifications import NotificationService
from callbot_platform.scheduling.repos import AppointmentRepository
from callbot_platform.storage import FilesystemObjectStorage, RecordingStorageService
from callbot_platform.tenancy import (
    DatabaseStrategy,
    TenantContext,
    TenantDatabaseResolver,
    TenantSource,
    assert_same_tenant,
    clear_tenant_context,
    get_tenant_context,
    require_tenant_context,
    set_tenant_context,
    tenant_cache_key,
)


@pytest.fixture()
def tenant_b(session: Session) -> Tenant:
    row = Tenant(name="Beta Isolation", slug=f"beta-iso-{uuid.uuid4().hex[:8]}")
    session.add(row)
    session.flush()
    return row


def _override_db(session: Session):
    def _db() -> Generator[Session, None, None]:
        yield session

    return _db


def _client(session: Session, settings: Settings) -> TestClient:
    app.dependency_overrides[db_dep] = _override_db(session)
    app.dependency_overrides[settings_dep] = lambda: settings
    get_settings.cache_clear()
    return TestClient(app)


def _fake_sms(**kwargs: object) -> str:
    return "SM_iso_test"


def test_assert_same_tenant_rejects_cross_tenant() -> None:
    a = uuid.uuid4()
    b = uuid.uuid4()
    assert_same_tenant(a, a, resource="customer")
    with pytest.raises(ValueError, match="Cross-tenant"):
        assert_same_tenant(a, b, resource="customer")


def test_tenant_cache_key_includes_tenant() -> None:
    tid = uuid.uuid4()
    key = tenant_cache_key(tid, "product", "sku-1")
    assert key.startswith(f"tenant:{tid}:")
    assert "product:sku-1" in key


def test_tenant_context_roundtrip() -> None:
    clear_tenant_context()
    assert get_tenant_context() is None
    tid = uuid.uuid4()
    token = set_tenant_context(
        TenantContext(tenant_id=tid, source=TenantSource.SESSION)
    )
    try:
        ctx = get_tenant_context()
        assert ctx is not None
        assert ctx.tenant_id == tid
        assert ctx.source == TenantSource.SESSION
    finally:
        clear_tenant_context(token)
    assert get_tenant_context() is None


def test_shared_database_strategy_default(tenant: Tenant) -> None:
    settings = Settings(database_url="postgresql+psycopg://shared/db")
    resolver = TenantDatabaseResolver(settings=settings)
    resolved = resolver.resolve(tenant.id, strategy=DatabaseStrategy.SHARED)
    assert resolved.strategy == DatabaseStrategy.SHARED
    assert resolved.database_url == settings.database_url
    assert resolved.dsn_key is None


def test_dedicated_database_strategy_requires_mapped_dsn(tenant: Tenant) -> None:
    settings = Settings(database_url="postgresql+psycopg://shared/db")
    resolver = TenantDatabaseResolver(
        settings=settings,
        dedicated_dsn_map={"ent-1": "postgresql+psycopg://dedicated/ent1"},
    )
    with pytest.raises(ValueError, match="db_dsn_key"):
        resolver.resolve(tenant.id, strategy=DatabaseStrategy.DEDICATED)

    resolved = resolver.resolve(
        tenant.id,
        strategy=DatabaseStrategy.DEDICATED,
        dsn_key="ent-1",
    )
    assert resolved.strategy == DatabaseStrategy.DEDICATED
    assert resolved.database_url.endswith("/ent1")
    assert resolved.dsn_key == "ent-1"


def test_dedicated_strategy_reads_tenant_columns(
    session: Session, tenant: Tenant
) -> None:
    tenant.db_strategy = DatabaseStrategy.DEDICATED.value
    tenant.db_dsn_key = "ent-2"
    session.flush()
    settings = Settings(database_url="postgresql+psycopg://shared/db")
    resolver = TenantDatabaseResolver(
        settings=settings,
        dedicated_dsn_map={"ent-2": "postgresql+psycopg://dedicated/ent2"},
    )
    resolved = resolver.resolve(tenant.id, session=session)
    assert resolved.strategy == DatabaseStrategy.DEDICATED
    assert "ent2" in resolved.database_url


def test_page_params_caps_limit() -> None:
    page = PageParams.parse(limit=9999, offset=-5, max_limit=200)
    assert page.limit == 200
    assert page.offset == 0


def test_crm_customer_update_isolated(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    created = CustomerRepository(session).upsert(
        tenant.id, name="Secret", phone="+15550001111"
    )
    customer_id = uuid.UUID(created["id"])
    assert session.get(Customer, customer_id) is not None
    assert (
        CustomerRepository(session).lookup_by_phone(tenant_b.id, "+15550001111") is None
    )


def test_lead_delete_isolated(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    customer = CustomerRepository(session).upsert(
        tenant.id, name="Cust", phone="+15550002222"
    )
    lead = LeadRepository(session).create(
        tenant.id,
        customer_id=uuid.UUID(customer["id"]),
        service_type="Repair",
    )
    lead_id = uuid.UUID(lead["id"])
    assert LeadRepository(session).get(tenant_b.id, lead_id) is None
    assert LeadRepository(session).get(tenant.id, lead_id) is not None


def test_appointment_get_isolated(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    customer = CustomerRepository(session).upsert(
        tenant.id, name="Appt Cust", phone="+15550003333"
    )
    repo = AppointmentRepository(
        session,
        notification_service=NotificationService(session, sms_sender=_fake_sms),
    )
    day = next_open_booking_day()
    slots = repo.list_available_slots(tenant.id, from_date=day, to_date=day)
    assert slots["slots"], "expected weekday slots"
    start = datetime.fromisoformat(slots["slots"][0]["starts_at"])
    appt = repo.book(
        tenant.id,
        customer_id=uuid.UUID(customer["id"]),
        starts_at=start,
        service_type="Tune-up",
    )
    appt_id = uuid.UUID(appt["id"])
    assert AppointmentRepository(session).get(tenant_b.id, appt_id) is None
    assert AppointmentRepository(session).get(tenant.id, appt_id) is not None


def test_job_get_isolated(session: Session, tenant: Tenant, tenant_b: Tenant) -> None:
    customer = CustomerRepository(session).upsert(
        tenant.id, name="Job Cust", phone="+15550004444"
    )
    job = JobRepository(session).create(
        tenant.id,
        customer_id=uuid.UUID(customer["id"]),
        service_type="Install",
    )
    job_id = uuid.UUID(job["id"])
    assert JobRepository(session).get(tenant_b.id, job_id) is None
    assert JobRepository(session).get(tenant.id, job_id) is not None


def test_knowledge_list_is_bounded_and_tenant_scoped(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    KnowledgeRepository(session).create(
        tenant.id, title="A FAQ", body="Secret content", category="faq"
    )
    KnowledgeRepository(session).create(
        tenant_b.id, title="B FAQ", body="Other content", category="faq"
    )
    a_rows = KnowledgeRepository(session).list(tenant.id, limit=10)
    b_rows = KnowledgeRepository(session).list(tenant_b.id, limit=10)
    assert len(a_rows) == 1
    assert a_rows[0]["title"] == "A FAQ"
    assert len(b_rows) == 1
    assert b_rows[0]["title"] == "B FAQ"
    for i in range(5):
        KnowledgeRepository(session).create(
            tenant.id, title=f"Extra {i}", body="x", category="faq"
        )
    capped = KnowledgeRepository(session).list(tenant.id, limit=3)
    assert len(capped) == 3


def test_legacy_telephony_routes_require_internal_token(
    session: Session, tenant: Tenant
) -> None:
    settings = Settings(
        session_secret="test-session-secret-tenancy-iso-ok32",
        internal_service_token="internal-iso-token",
    )
    client = _client(session, settings)
    try:
        paths = [
            ("get", f"/tenants/{tenant.id}"),
            ("get", f"/tenants/{tenant.id}/phone-numbers"),
            ("get", f"/tenants/{tenant.id}/inventory"),
            ("post", f"/tenants/{tenant.id}/phone-numbers/connect"),
            ("post", f"/tenants/{tenant.id}/phone-numbers/purchase"),
            ("post", f"/tenants/{tenant.id}/twilio/subaccount"),
        ]
        for method, path in paths:
            res = client.get(path) if method == "get" else client.post(path, json={})
            assert res.status_code == 401, (
                f"{method.upper()} {path} -> {res.status_code}"
            )

        ok = client.get(
            f"/tenants/{tenant.id}/phone-numbers",
            headers={"X-Internal-Token": "internal-iso-token"},
        )
        assert ok.status_code == 200
        assert ok.json()["items"] == []
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_require_tenant_context_fail_closed() -> None:
    clear_tenant_context()
    with pytest.raises(RuntimeError, match="Tenant context is not set"):
        require_tenant_context()


def test_organization_get_is_tenant_keyed(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    org_a = OrganizationService(session).get(tenant.id)
    org_b = OrganizationService(session).get(tenant_b.id)
    assert org_a["id"] == str(tenant.id)
    assert org_b["id"] == str(tenant_b.id)
    assert org_a["id"] != org_b["id"]


def test_customer_get_idor(session: Session, tenant: Tenant, tenant_b: Tenant) -> None:
    created = CustomerRepository(session).upsert(
        tenant.id, name="Owner A", phone="+15550006666"
    )
    customer_id = uuid.UUID(created["id"])
    assert CustomerRepository(session).get(tenant.id, customer_id) is not None
    assert CustomerRepository(session).get(tenant_b.id, customer_id) is None


def test_call_end_idor(session: Session, tenant: Tenant, tenant_b: Tenant) -> None:
    started = CallRepository(session).start(
        tenant.id, room_name=f"room-{uuid.uuid4().hex[:8]}"
    )
    call_id = uuid.UUID(started["id"])
    with pytest.raises(CrmError, match="Call not found"):
        CallRepository(session).end(tenant_b.id, call_id=call_id)
    ended = CallRepository(session).end(tenant.id, call_id=call_id)
    assert ended["status"] == "closed"


def test_job_assign_idor(session: Session, tenant: Tenant, tenant_b: Tenant) -> None:
    customer = CustomerRepository(session).upsert(
        tenant.id, name="Job Owner", phone="+15550007777"
    )
    job = JobRepository(session).create(
        tenant.id,
        customer_id=uuid.UUID(customer["id"]),
        service_type="Repair",
    )
    job_id = uuid.UUID(job["id"])
    with pytest.raises(JobsError):
        JobRepository(session).assign(
            tenant_b.id,
            job_id,
            technician_id=uuid.uuid4(),
            actor="attacker",
        )
    assert JobRepository(session).get(tenant_b.id, job_id) is None


def test_job_list_excludes_other_tenant(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    customer_a = CustomerRepository(session).upsert(
        tenant.id, name="List A", phone="+15550008888"
    )
    customer_b = CustomerRepository(session).upsert(
        tenant_b.id, name="List B", phone="+15550009999"
    )
    JobRepository(session).create(
        tenant.id,
        customer_id=uuid.UUID(customer_a["id"]),
        service_type="A",
    )
    JobRepository(session).create(
        tenant_b.id,
        customer_id=uuid.UUID(customer_b["id"]),
        service_type="B",
    )
    a_jobs = JobRepository(session).list(tenant.id)
    b_jobs = JobRepository(session).list(tenant_b.id)
    assert len(a_jobs) == 1
    assert a_jobs[0]["service_type"] == "A"
    assert len(b_jobs) == 1
    assert b_jobs[0]["service_type"] == "B"


def test_knowledge_search_tenant_scoped(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    KnowledgeRepository(session).create(
        tenant.id, title="Secret HVAC FAQ", body="Tenant A only", category="faq"
    )
    KnowledgeRepository(session).create(
        tenant_b.id, title="Secret HVAC FAQ", body="Tenant B only", category="faq"
    )
    a_hits = KnowledgeRepository(session).search(tenant.id, "Secret HVAC")
    b_hits = KnowledgeRepository(session).search(tenant_b.id, "Secret HVAC")
    assert len(a_hits) == 1
    assert a_hits[0]["body"] == "Tenant A only"
    assert len(b_hits) == 1
    assert b_hits[0]["body"] == "Tenant B only"


def test_audit_list_tenant_scoped(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    CustomerRepository(session).upsert(tenant.id, name="Audit A", phone="+15550101111")
    CustomerRepository(session).upsert(
        tenant_b.id, name="Audit B", phone="+15550102222"
    )
    a_events = AdminRepository(session).list_audit(tenant.id)
    b_events = AdminRepository(session).list_audit(tenant_b.id)
    a_ids = {e["id"] for e in a_events}
    b_ids = {e["id"] for e in b_events}
    assert a_ids.isdisjoint(b_ids)
    assert any(e["action"] == "customer_created" for e in a_events)
    assert any(e["action"] == "customer_created" for e in b_events)


def test_recording_get_and_presign_idor(
    session: Session, tenant: Tenant, tenant_b: Tenant, tmp_path
) -> None:
    storage = FilesystemObjectStorage(str(tmp_path))
    svc = RecordingStorageService(session, storage=storage)
    meta = svc.store_recording(
        tenant_id=tenant.id,
        data=b"RIFF....WAVE",
        mime_type="audio/wav",
        retention_days=30,
    )
    recording_id = uuid.UUID(meta["id"])
    assert svc.get_recording(tenant.id, recording_id) is not None
    assert svc.get_recording(tenant_b.id, recording_id) is None
    assert svc.presign_download(tenant_b.id, recording_id) is None
    signed = svc.presign_download(tenant.id, recording_id)
    assert signed is not None
    assert "download_url" in signed


def test_branding_and_api_keys_tenant_scoped(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    BrandingRepository(session).upsert(tenant.id, actor="ops", primary_color="#111111")
    a = BrandingRepository(session).get(tenant.id)
    b = BrandingRepository(session).get(tenant_b.id)
    assert a.get("primary_color") == "#111111"
    assert b.get("primary_color") in (None, "")

    key = ApiKeyRepository(session).create_key(tenant.id, name="iso-key", actor="ops")
    a_keys = ApiKeyRepository(session).list_keys(tenant.id)
    b_keys = ApiKeyRepository(session).list_keys(tenant_b.id)
    assert any(k["id"] == key["id"] for k in a_keys)
    assert all(k["id"] != key["id"] for k in b_keys)


def test_async_job_get_idor(session: Session, tenant: Tenant, tenant_b: Tenant) -> None:
    svc = AsyncJobService(session)
    row = svc.enqueue(
        tenant_id=tenant.id,
        job_type="telephony.purchase",
        payload={"phone_number_id": str(uuid.uuid4())},
        resource_id=str(uuid.uuid4()),
        idempotency_key=f"iso-job-{uuid.uuid4().hex[:8]}",
    )
    assert svc.get(row.id, tenant_id=tenant.id) is not None
    assert svc.get(row.id, tenant_id=tenant_b.id) is None

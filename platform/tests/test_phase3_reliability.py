"""Phase 3: async jobs, leases, call-scope, storage, health."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from callbot_platform.api.deps import db_dep, settings_dep
from callbot_platform.async_jobs.service import AsyncJobService
from callbot_platform.async_jobs.types import JobStatus, JobType
from callbot_platform.async_jobs.worker import AsyncJobWorker
from callbot_platform.config import Settings, get_settings
from callbot_platform.db.models import AsyncJob, Tenant
from callbot_platform.db.models.async_job import AsyncJob as AsyncJobModel
from callbot_platform.main import app
from callbot_platform.security.call_scope import CallScopeSigner
from callbot_platform.storage import FilesystemObjectStorage, RecordingStorageService


@pytest.fixture()
def settings_p3(monkeypatch: pytest.MonkeyPatch) -> Settings:
    get_settings.cache_clear()
    monkeypatch.setenv("METADATA_HMAC_SECRET", "test-metadata-hmac-secret")
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "internal-token")
    monkeypatch.setenv("REQUIRE_CALL_SCOPE", "true")
    monkeypatch.setenv("JOB_LEASE_SECONDS", "10")
    get_settings.cache_clear()
    return get_settings()


def _override_db(session: Session):
    def _db() -> Generator[Session, None, None]:
        yield session

    return _db


def test_async_job_enqueue_idempotent(session: Session, tenant: Tenant) -> None:
    svc = AsyncJobService(session)
    a = svc.enqueue(
        tenant_id=tenant.id,
        job_type=JobType.TELEPHONY_PROVISION_PURCHASE,
        idempotency_key=f"tenant:{tenant.id}:phone:x:provision",
        resource_id="x",
        payload={"phone_number_id": str(uuid.uuid4())},
    )
    b = svc.enqueue(
        tenant_id=tenant.id,
        job_type=JobType.TELEPHONY_PROVISION_PURCHASE,
        idempotency_key=f"tenant:{tenant.id}:phone:x:provision",
        resource_id="x",
        payload={"phone_number_id": str(uuid.uuid4())},
    )
    assert a.id == b.id


def test_job_lease_reclaim(session: Session, tenant: Tenant) -> None:
    from callbot_platform.db import get_session_factory

    job = AsyncJobService(session).enqueue(
        tenant_id=tenant.id,
        job_type="test.noop",
        idempotency_key=f"lease-{uuid.uuid4().hex}",
        payload={},
    )
    now = datetime.now(UTC)
    job.status = JobStatus.RUNNING
    job.claimed_by = "dead-worker"
    job.lease_expires_at = now - timedelta(seconds=5)
    session.commit()

    worker = AsyncJobWorker(get_session_factory())

    def _noop(sess: Session, row: AsyncJobModel) -> dict:
        return {"ok": True}

    worker.register("test.noop", _noop)
    reclaimed = worker._reclaim_expired_leases()
    assert reclaimed >= 1
    session.expire_all()
    refreshed = session.get(AsyncJob, job.id)
    assert refreshed is not None
    assert refreshed.status == JobStatus.PENDING


def test_call_scope_required_on_scheduling(
    session: Session, tenant: Tenant, settings_p3: Settings
) -> None:
    app.dependency_overrides[db_dep] = _override_db(session)
    app.dependency_overrides[settings_dep] = lambda: settings_p3
    client = TestClient(app)
    resp = client.post(
        "/internal/scheduling/slots",
        headers={"X-Internal-Token": "internal-token"},
        json={"tenant_id": str(tenant.id), "limit": 5},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "missing_claim"

    scope = CallScopeSigner(settings_p3.metadata_hmac_secret).issue(tenant_id=tenant.id)
    resp2 = client.post(
        "/internal/scheduling/slots",
        headers={
            "X-Internal-Token": "internal-token",
            "X-Call-Scope": scope,
        },
        json={"tenant_id": str(tenant.id), "limit": 5},
    )
    assert resp2.status_code == 200
    app.dependency_overrides.clear()


def test_call_scope_tenant_mismatch(
    session: Session, tenant: Tenant, settings_p3: Settings
) -> None:
    other = Tenant(name="Other", slug=f"other-{uuid.uuid4().hex[:6]}")
    session.add(other)
    session.flush()
    app.dependency_overrides[db_dep] = _override_db(session)
    app.dependency_overrides[settings_dep] = lambda: settings_p3
    client = TestClient(app)
    scope = CallScopeSigner(settings_p3.metadata_hmac_secret).issue(tenant_id=other.id)
    resp = client.post(
        "/internal/crm/customers/lookup",
        headers={
            "X-Internal-Token": "internal-token",
            "X-Call-Scope": scope,
        },
        json={"tenant_id": str(tenant.id), "phone": "+15551234567"},
    )
    assert resp.status_code == 403
    app.dependency_overrides.clear()


def test_liveness_and_readiness(session: Session) -> None:
    app.dependency_overrides[db_dep] = _override_db(session)
    client = TestClient(app)
    assert client.get("/liveness").json()["status"] == "alive"
    ready = client.get("/readiness")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    app.dependency_overrides.clear()


def test_storage_path_traversal_blocked(tmp_path) -> None:
    store = FilesystemObjectStorage(str(tmp_path), max_upload_bytes=1024)
    tid = uuid.uuid4()
    with pytest.raises(ValueError):
        store.put(
            tenant_id=tid,
            object_key="../escape.txt",
            data=b"x",
            mime_type="text/plain",
        )


def test_recording_retention_missing_object(
    session: Session, tenant: Tenant, tmp_path
) -> None:
    store = FilesystemObjectStorage(str(tmp_path))
    svc = RecordingStorageService(session, store)
    meta = svc.store_recording(tenant_id=tenant.id, data=b"wav", retention_days=0)
    # Force expired
    from callbot_platform.db.models import RecordingObject

    row = session.get(RecordingObject, uuid.UUID(meta["id"]))
    assert row is not None
    row.retention_until = datetime.now(UTC) - timedelta(days=1)
    # Delete object out of band
    store.delete(tenant_id=tenant.id, object_key=row.object_key)
    deleted = svc.delete_expired(limit=10)
    assert deleted == 1
    session.refresh(row)
    assert row.status == "deleted"


def test_dlq_retry(session: Session, tenant: Tenant) -> None:
    svc = AsyncJobService(session)
    job = svc.enqueue(
        tenant_id=tenant.id,
        job_type="test.fail",
        idempotency_key=f"dlq-{uuid.uuid4().hex}",
        payload={},
    )
    job.status = JobStatus.DEAD_LETTER
    job.last_error = "boom"
    session.flush()
    replayed = svc.retry(job.id, tenant_id=tenant.id)
    assert replayed["status"] == JobStatus.PENDING

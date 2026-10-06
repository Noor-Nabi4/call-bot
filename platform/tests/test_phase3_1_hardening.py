"""Phase 3.1: release saga, inventory decoupling, S3 gated tests, security."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from helpers import make_phone
from provisioning_helpers import session_factory_for
from sqlalchemy.orm import Session
from test_telephony_services import (
    FakeInventory,
    FakeLiveKit,
    FakeProvisioning,
    FakeTwilioSip,
    _settings,
)

from callbot_platform.async_jobs.handlers.telephony import TelephonyProvisionHandler
from callbot_platform.async_jobs.runner import run_async_job
from callbot_platform.async_jobs.types import JobStatus
from callbot_platform.config import Settings
from callbot_platform.db.models import Tenant, TenantPhoneNumber
from callbot_platform.domain.enums import (
    ConnectionStatus,
    OnboardingPath,
)
from callbot_platform.security.call_scope import CallScopeError, CallScopeSigner
from callbot_platform.security.crypto import CredentialCipher
from callbot_platform.security.metadata import MetadataSigner
from callbot_platform.storage import FilesystemObjectStorage, RecordingStorageService
from callbot_platform.storage.base import validate_object_mime_type
from callbot_platform.telephony.services.purchase import (
    PlatformPurchaseService,
    PurchaseError,
)


def test_mime_type_validation() -> None:
    assert validate_object_mime_type("audio/wav") == "audio/wav"
    with pytest.raises(ValueError, match="unsupported_content_type"):
        validate_object_mime_type("application/x-msdownload")


def test_inventory_requires_subaccount(
    session: Session, tenant: Tenant, signer: MetadataSigner, cipher: CredentialCipher
) -> None:
    service = PlatformPurchaseService(
        session,
        _settings(),
        cipher=cipher,
        signer=signer,
        inventory=FakeInventory(),  # type: ignore[arg-type]
        provisioning=FakeProvisioning(),  # type: ignore[arg-type]
        twilio_sip=FakeTwilioSip(),  # type: ignore[arg-type]
        livekit=FakeLiveKit(),  # type: ignore[arg-type]
    )
    with pytest.raises(PurchaseError) as exc:
        service.search_inventory(tenant_id=tenant.id, country="US")
    assert exc.value.code == "subaccount_required"


def test_release_saga_idempotent(
    session: Session, tenant: Tenant, signer: MetadataSigner, cipher: CredentialCipher
) -> None:
    settings = _settings()
    provisioning = FakeProvisioning()
    livekit = FakeLiveKit()
    service = PlatformPurchaseService(
        session,
        settings,
        cipher=cipher,
        signer=signer,
        inventory=FakeInventory(),  # type: ignore[arg-type]
        provisioning=provisioning,  # type: ignore[arg-type]
        twilio_sip=FakeTwilioSip(),  # type: ignore[arg-type]
        livekit=livekit,  # type: ignore[arg-type]
    )
    phone = make_phone(
        session,
        tenant,
        e164="+15550001111",
        connection_status=ConnectionStatus.ACTIVE.value,
    )
    phone.onboarding_path = OnboardingPath.PLATFORM_PURCHASE.value
    phone.provisioning_details = {"phone_number_sid": "PN_rel_1"}
    phone.livekit_inbound_trunk_id = "ST_1"
    phone.livekit_dispatch_rule_id = "SDR_1"
    service.ensure_subaccount(tenant_id=tenant.id)
    session.flush()

    queued = service.release(
        tenant_id=tenant.id,
        phone_number_id=phone.id,
        phone_number_sid="PN_rel_1",
    )
    assert queued["provisioning"] == "queued"
    assert phone.connection_status == ConnectionStatus.RELEASING.value
    session.commit()

    handler = TelephonyProvisionHandler(
        settings=settings,
        cipher=cipher,
        signer=signer,
        provisioning=provisioning,
        livekit=livekit,
    )
    job = run_async_job(
        session_factory_for(session),
        uuid.UUID(str(queued["job_id"])),
        settings=settings,
        telephony_handler=handler,
    )
    assert job is not None
    assert job.status == JobStatus.SUCCEEDED
    session.expire_all()
    refreshed = session.get(TenantPhoneNumber, phone.id)
    assert refreshed is not None
    assert refreshed.connection_status == ConnectionStatus.RELEASED.value
    assert "PN_rel_1" in provisioning.releases

    # Second release while released is a no-op success path.
    again = service.release(tenant_id=tenant.id, phone_number_id=phone.id)
    assert again["provisioning"] == "released"


def test_call_scope_tampered_rejected() -> None:
    signer = CallScopeSigner("test-metadata-hmac-secret")
    token = signer.issue(tenant_id=uuid.uuid4())
    bad = token.replace("sig", "sig")[:-4] + "dead"
    with pytest.raises(CallScopeError) as exc:
        signer.verify(bad)
    assert exc.value.code in {"tampered_claim", "invalid_claim"}


def test_call_scope_expired_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    signer = CallScopeSigner("test-metadata-hmac-secret")
    monkeypatch.setattr(
        "callbot_platform.security.call_scope.time.time", lambda: 1_700_000_000.0
    )
    token = signer.issue(tenant_id=uuid.uuid4(), ttl_seconds=1)
    # Advance to exactly exp — must fail closed (exp <= now).
    monkeypatch.setattr(
        "callbot_platform.security.call_scope.time.time", lambda: 1_700_000_001.0
    )
    with pytest.raises(CallScopeError) as exc:
        signer.verify(token)
    assert exc.value.code == "expired_claim"


@pytest.mark.skipif(
    not os.getenv("S3_INTEGRATION_TEST", "").strip()
    or not os.getenv("S3_BUCKET", "").strip(),
    reason="S3_INTEGRATION_TEST and S3_BUCKET required for live S3/R2/MinIO verification",
)
def test_s3_object_storage_roundtrip() -> None:
    """NOT RUN unless S3 credentials are configured in the environment."""
    from callbot_platform.storage.s3 import S3ObjectStorage

    settings = Settings(
        OBJECT_STORAGE_BACKEND="s3",
        S3_BUCKET=os.environ["S3_BUCKET"],
        S3_REGION=os.getenv("S3_REGION", "us-east-1"),
        S3_ENDPOINT_URL=os.getenv("S3_ENDPOINT_URL", ""),
        S3_ACCESS_KEY_ID=os.environ.get("S3_ACCESS_KEY_ID", ""),
        S3_SECRET_ACCESS_KEY=os.environ.get("S3_SECRET_ACCESS_KEY", ""),
        S3_FORCE_PATH_STYLE=os.getenv("S3_FORCE_PATH_STYLE", "false").lower()
        in {"1", "true", "yes"},
    )
    store = S3ObjectStorage(settings)
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    key = f"recordings/{uuid.uuid4().hex}/probe.wav"
    stored = store.put(
        tenant_id=tenant_a, object_key=key, data=b"RIFF", mime_type="audio/wav"
    )
    assert stored.backend == "s3"
    assert store.exists(tenant_id=tenant_a, object_key=key)
    assert store.get(tenant_id=tenant_a, object_key=key) == b"RIFF"
    assert not store.exists(tenant_id=tenant_b, object_key=key)
    url = store.create_download_url(tenant_id=tenant_a, object_key=key, ttl_seconds=60)
    assert url.startswith("http")
    store.delete(tenant_id=tenant_a, object_key=key)
    assert not store.exists(tenant_id=tenant_a, object_key=key)


def test_filesystem_tenant_isolation(tmp_path) -> None:
    store = FilesystemObjectStorage(str(tmp_path))
    a = uuid.uuid4()
    b = uuid.uuid4()
    store.put(tenant_id=a, object_key="r/a.wav", data=b"aaa", mime_type="audio/wav")
    assert store.get(tenant_id=a, object_key="r/a.wav") == b"aaa"
    assert not store.exists(tenant_id=b, object_key="r/a.wav")


def test_retention_idempotent_missing_object(
    session: Session, tenant: Tenant, tmp_path
) -> None:
    store = FilesystemObjectStorage(str(tmp_path))
    svc = RecordingStorageService(session, store)
    meta = svc.store_recording(tenant_id=tenant.id, data=b"x", retention_days=0)
    from callbot_platform.db.models import RecordingObject

    row = session.get(RecordingObject, uuid.UUID(meta["id"]))
    assert row is not None
    row.retention_until = datetime.now(UTC) - timedelta(days=1)
    store.delete(tenant_id=tenant.id, object_key=row.object_key)
    assert svc.delete_expired(limit=5) == 1
    session.refresh(row)
    assert row.status == "deleted"
    # Second pass is a no-op (already deleted status).
    assert svc.delete_expired(limit=5) == 0

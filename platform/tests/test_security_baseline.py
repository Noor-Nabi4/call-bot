"""Phase 33 — application security baseline (no duplicate security stack)."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from callbot_platform.api import deps as api_deps
from callbot_platform.api.deps import _constant_time_token_eq
from callbot_platform.auth.repos import AuthRepository
from callbot_platform.billing.usage_ledger import UsageLedgerService
from callbot_platform.billing.usage_ledger.categories import (
    AccountingProvenance,
    BillingStatus,
    UsageType,
)
from callbot_platform.config import Settings
from callbot_platform.db.models import Tenant
from callbot_platform.integrations.http import redact_headers
from callbot_platform.main import app
from callbot_platform.origins import cors_allow_origins, session_cookie_params
from callbot_platform.security.crypto import CredentialCipher
from callbot_platform.security.rate_limit import (
    RateLimitExceeded,
    SlidingWindowRateLimiter,
)
from callbot_platform.storage import FilesystemObjectStorage
from callbot_platform.storage.base import sanitize_object_key


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        session_secret="phase33-session-secret-for-tests-only",
        internal_service_token="phase33-internal-token",
        credentials_encryption_key="phase33-credentials-encryption-key",
        metadata_hmac_secret="phase33-metadata-hmac",
        cookie_secure=False,
        environment="development",
    )


@pytest.fixture()
def client(session: Session, settings: Settings) -> Generator[TestClient, None, None]:
    def _db() -> Generator[Session, None, None]:
        yield session

    def _settings() -> Settings:
        return settings

    app.dependency_overrides[api_deps.db_dep] = _db
    app.dependency_overrides[api_deps.settings_dep] = _settings
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


def _seed_user(session: Session, tenant: Tenant, *, email: str, password: str) -> dict:
    return AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email=email,
        password=password,
        name="Security Tester",
    )


# --- Internal token / constant-time compare ---------------------------------


def test_internal_token_constant_time_rejects_wrong_and_empty() -> None:
    assert _constant_time_token_eq("phase33-internal-token", "phase33-internal-token")
    assert not _constant_time_token_eq(
        "wrong-token-value!!!!!", "phase33-internal-token"
    )
    assert not _constant_time_token_eq(None, "phase33-internal-token")
    assert not _constant_time_token_eq("", "phase33-internal-token")
    assert not _constant_time_token_eq("short", "phase33-internal-token")


def test_usage_cost_fleet_requires_internal_token(
    client: TestClient, settings: Settings
) -> None:
    denied = client.get("/api/admin/usage-cost/fleet")
    assert denied.status_code == 401

    wrong = client.get(
        "/api/admin/usage-cost/fleet",
        headers={"X-Internal-Token": "not-the-token"},
    )
    assert wrong.status_code == 401

    ok = client.get(
        "/api/admin/usage-cost/fleet",
        headers={"X-Internal-Token": settings.internal_service_token},
    )
    assert ok.status_code == 200
    body = ok.json()
    assert "fleet" in body
    assert body["fleet"].get("actual_revenue_aggregated") is False


def test_usage_cost_summary_requires_auth(client: TestClient) -> None:
    res = client.get("/api/admin/usage-cost/summary")
    assert res.status_code == 401


# --- Security headers / CORS / cookies --------------------------------------


def test_security_headers_on_health(client: TestClient) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "default-src 'none'" in (res.headers.get("Content-Security-Policy") or "")


def test_cors_production_rejects_wildcard_credentials() -> None:
    prod = Settings(
        environment="production",
        ops_cors_origins="https://evil.example,http://localhost:3002",
        session_secret="x" * 32,
        internal_service_token="t",
        credentials_encryption_key="k" * 32,
        metadata_hmac_secret="m" * 32,
    )
    origins = cors_allow_origins(prod)
    assert "*" not in origins
    assert all(o.startswith("https://") for o in origins)
    assert "http://localhost:3002" not in origins
    # Production always includes canonical Call & Flow web origins.
    assert "https://callandflow.com" in origins


def test_session_cookie_flags(settings: Settings) -> None:
    params = session_cookie_params(settings)
    assert params["httponly"] is True
    assert params["samesite"] == "lax"
    assert params["path"] == "/"


# --- Auth mass assignment + rate limit + enumeration ------------------------


def test_login_rejects_mass_assignment_fields(client: TestClient) -> None:
    res = client.post(
        "/auth/login",
        json={
            "email": "a@b.co",
            "password": "password123",
            "tenant_slug": "acme",
            "role": "Owner",
            "is_admin": True,
            "tenant_id": str(uuid.uuid4()),
        },
    )
    assert res.status_code == 422


def test_login_does_not_enumerate_missing_tenant(client: TestClient) -> None:
    res = client.post(
        "/auth/login",
        json={
            "email": "nobody@example.com",
            "password": "wrong-password",
            "tenant_slug": f"missing-{uuid.uuid4().hex[:8]}",
        },
    )
    assert res.status_code == 401
    assert res.json()["detail"]["code"] == "invalid_credentials"


def test_auth_login_rate_limit(
    client: TestClient, session: Session, tenant: Tenant
) -> None:
    email = f"rl-{uuid.uuid4().hex[:8]}@example.com"
    _seed_user(session, tenant, email=email, password="password12345")
    session.commit()

    limiter = SlidingWindowRateLimiter(max_requests=3, window_sec=60.0)
    key = f"test|{email}"
    for _ in range(3):
        limiter.check(key)
    with pytest.raises(RateLimitExceeded):
        limiter.check(key)

    # HTTP path uses shared AUTH_LOGIN_RATE_LIMITER — unique key avoids cross-test pollution.
    unique_email = f"http-rl-{uuid.uuid4().hex}@example.com"
    status_codes: list[int] = []
    for _ in range(25):
        r = client.post(
            "/auth/login",
            json={
                "email": unique_email,
                "password": "wrong",
                "tenant_slug": tenant.slug,
            },
        )
        status_codes.append(r.status_code)
    assert 429 in status_codes


# --- Path traversal / file security -----------------------------------------


@pytest.mark.parametrize(
    "bad_key",
    [
        "../etc/passwd",
        "..\\windows\\system32",
        "foo/../../secret",
        "%2e%2e/secret",
        "/absolute/path",
        "a\x00b",
        "",
        ".",
        "..",
    ],
)
def test_sanitize_object_key_rejects_traversal(bad_key: str) -> None:
    with pytest.raises(ValueError, match="invalid_object_key"):
        sanitize_object_key(bad_key)


def test_sanitize_object_key_accepts_safe_relative() -> None:
    assert sanitize_object_key("recordings/call-1.wav") == "recordings/call-1.wav"
    assert sanitize_object_key("nested/file.pdf") == "nested/file.pdf"


def test_filesystem_rejects_path_traversal(tmp_path: Path) -> None:
    store = FilesystemObjectStorage(str(tmp_path))
    tid = uuid.uuid4()
    with pytest.raises(ValueError, match="invalid_object_key"):
        store.put(
            tenant_id=tid,
            object_key="../escape.wav",
            data=b"RIFF",
            mime_type="audio/wav",
        )


def test_tenant_object_key_prefix_contract() -> None:
    tid = uuid.uuid4()
    safe = sanitize_object_key("docs/a.pdf")
    assert f"tenants/{tid}/{safe}" == f"tenants/{tid}/docs/a.pdf"
    with pytest.raises(ValueError, match="invalid_object_key"):
        sanitize_object_key("../../other-tenant/secret")


# --- Encryption / secret redaction ------------------------------------------


def test_credential_cipher_roundtrip_and_not_plaintext(
    cipher: CredentialCipher,
) -> None:
    secret = "sk_live_should_never_appear_in_api"
    enc = cipher.encrypt(secret)
    assert secret not in enc
    assert cipher.decrypt(enc) == secret


def test_redact_headers_masks_authorization() -> None:
    redacted = redact_headers(
        {
            "Authorization": "Bearer super-secret",
            "X-Api-Key": "key-123",
            "Content-Type": "application/json",
        }
    )
    assert redacted["Authorization"] == "[REDACTED]"
    assert redacted["X-Api-Key"] == "[REDACTED]"
    assert redacted["Content-Type"] == "application/json"


# --- Tenant isolation: usage ledger + billing fields ------------------------


def test_usage_ledger_cross_tenant_invisible(session: Session, tenant: Tenant) -> None:
    other = Tenant(name="Other Co", slug=f"other-{uuid.uuid4().hex[:8]}")
    session.add(other)
    session.flush()

    ledger = UsageLedgerService(session)
    ledger.record(
        tenant_id=tenant.id,
        usage_type=UsageType.VOICE_MINUTES,
        quantity=12,
        provider="internal",
        source_type="call",
        source_id=str(uuid.uuid4()),
        idempotency_key=f"sec-{uuid.uuid4()}",
        usage_provenance=AccountingProvenance.ACTUAL_INTERNAL,
        cost_provenance=AccountingProvenance.CONFIGURED_RATE,
        unit_cost_micros_override=1000,
        billing_status=BillingStatus.UNBILLED,
    )
    session.flush()

    from sqlalchemy import select

    from callbot_platform.db.models import UsageLedgerEntry

    rows_other = session.scalars(
        select(UsageLedgerEntry).where(UsageLedgerEntry.tenant_id == other.id)
    ).all()
    assert rows_other == []

    rows_own = session.scalars(
        select(UsageLedgerEntry).where(UsageLedgerEntry.tenant_id == tenant.id)
    ).all()
    assert len(rows_own) == 1


def test_usage_ledger_unavailable_cost_not_fabricated_zero(
    session: Session, tenant: Tenant
) -> None:
    """Unavailable cost provenance must not become a silent $0 COGS line."""
    ledger = UsageLedgerService(session)
    entry, created = ledger.record(
        tenant_id=tenant.id,
        usage_type=UsageType.SMS,
        quantity=1,
        provider="twilio",
        source_type="sms",
        source_id=str(uuid.uuid4()),
        idempotency_key=f"sms-sec-{uuid.uuid4()}",
        usage_provenance=AccountingProvenance.ACTUAL_PROVIDER,
        cost_provenance=AccountingProvenance.UNAVAILABLE,
        billing_status=BillingStatus.UNBILLED,
    )
    assert created is True
    assert entry.total_cost_micros is None


# --- CSRF applicability (documented behavior) -------------------------------


def test_csrf_mitigation_is_samesite_lax_not_token(settings: Settings) -> None:
    """Cookie auth uses SameSite=Lax + CORS allowlist; no CSRF token layer by design."""
    params = session_cookie_params(settings)
    assert params["samesite"] == "lax"
    assert params["httponly"] is True


# --- Rate limiter unit semantics --------------------------------------------


def test_sliding_window_rate_limiter_per_key_isolation() -> None:
    limiter = SlidingWindowRateLimiter(max_requests=2, window_sec=60.0)
    limiter.check("tenant-a")
    limiter.check("tenant-a")
    with pytest.raises(RateLimitExceeded):
        limiter.check("tenant-a")
    # Different key is independent.
    limiter.check("tenant-b")

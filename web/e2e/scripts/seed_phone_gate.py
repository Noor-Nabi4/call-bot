#!/usr/bin/env python3
"""Seed tenants for web Playwright phone-gate E2E.

Creates three orgs against the running platform DB:

* no_phone — COMPLETED business onboarding, no eligible DID (gate blocks)
* with_phone — COMPLETED + eligible DID (dashboard allowed)
* pending_phone — COMPLETED + pending number (gate still blocks)

Writes credentials to web/e2e/.auth/fixtures.json (gitignored).

Env:
  DATABASE_URL or E2E_DATABASE_URL — Postgres used by the platform API
  PLATFORM_API_URL — default http://127.0.0.1:8000
  INTERNAL_SERVICE_TOKEN — from platform/.env.local
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

# Allow `uv run` from web/e2e/scripts with platform on PYTHONPATH.
PLATFORM_SRC = Path(__file__).resolve().parents[3] / "platform" / "src"
sys.path.insert(0, str(PLATFORM_SRC))
TESTS_DIR = Path(__file__).resolve().parents[3] / "platform" / "tests"
sys.path.insert(0, str(TESTS_DIR))

from callbot_platform.db.models import Tenant, TenantPhoneNumber  # noqa: E402
from callbot_platform.domain.enums import (  # noqa: E402
    ConnectionStatus,
    VerificationStatus,
)
from callbot_platform.onboarding.access import (  # noqa: E402
    mark_legacy_tenant_onboarding_complete,
)
from helpers import make_phone  # noqa: E402

FIXTURES_PATH = Path(__file__).resolve().parents[1] / ".auth" / "fixtures.json"
PASSWORD = "E2ePhoneGate!9"


def _load_dotenv_local() -> dict[str, str]:
    """Load platform/.env.local. Explicit E2E_* vars still win in _db_url()."""
    env_path = Path(__file__).resolve().parents[3] / "platform" / ".env.local"
    loaded: dict[str, str] = {}
    if not env_path.is_file():
        return loaded
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        loaded[key] = value
        # Prefer file over stale shell exports so seed matches the local API DB.
        if key in {"DATABASE_URL", "INTERNAL_SERVICE_TOKEN"} or key not in os.environ:
            os.environ[key] = value
    return loaded


def _db_url() -> str:
    raw = (
        os.environ.get("E2E_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or ""
    ).strip()
    if not raw:
        raise SystemExit("DATABASE_URL or E2E_DATABASE_URL is required")
    return raw


def _api() -> str:
    return (
        os.environ.get("PLATFORM_API_URL")
        or os.environ.get("NEXT_PUBLIC_PLATFORM_API_URL")
        or "http://127.0.0.1:8000"
    ).rstrip("/")


def _token() -> str:
    token = (os.environ.get("INTERNAL_SERVICE_TOKEN") or "").strip()
    if not token:
        raise SystemExit("INTERNAL_SERVICE_TOKEN is required")
    return token


def _create_tenant_http(slug: str, name: str) -> dict:
    headers = {"X-Internal-Token": _token()}
    with httpx.Client(base_url=_api(), timeout=30.0) as client:
        res = client.post(
            "/tenants",
            headers=headers,
            json={
                "name": name,
                "slug": slug,
                "timezone": "America/New_York",
                "industry": "hvac",
                "country": "US",
            },
        )
        if res.status_code == 409:
            return {"id": None, "slug": slug, "name": name, "exists": True}
        if res.status_code >= 400:
            raise RuntimeError(
                f"POST /tenants failed ({res.status_code}): {res.text[:500]}"
            )
        body = res.json()
        body["exists"] = False
        return body


def _bootstrap_admin(tenant_id: str, email: str) -> None:
    headers = {"X-Internal-Token": _token()}
    with httpx.Client(base_url=_api(), timeout=30.0) as client:
        res = client.post(
            "/auth/bootstrap",
            headers=headers,
            json={
                "tenant_id": tenant_id,
                "email": email,
                "password": PASSWORD,
                "name": "E2E Owner",
            },
        )
        if res.status_code in {200, 201}:
            return
        # Already bootstrapped
        if res.status_code in {400, 409}:
            return
        res.raise_for_status()


def _tenant_by_slug(session: Session, slug: str) -> Tenant:
    row = session.scalar(select(Tenant).where(Tenant.slug == slug))
    if row is None:
        raise RuntimeError(f"tenant slug not found: {slug}")
    return row


def _clear_phones(session: Session, tenant_id: uuid.UUID) -> None:
    rows = session.scalars(
        select(TenantPhoneNumber).where(TenantPhoneNumber.tenant_id == tenant_id)
    ).all()
    for row in rows:
        session.delete(row)
    session.flush()


def _seed_scenario(
    session: Session,
    *,
    slug: str,
    name: str,
    email: str,
    mode: str,
) -> dict:
    created = _create_tenant_http(slug, name)
    # Expire so we see rows committed by the API process.
    session.expire_all()
    if created.get("id"):
        tenant = session.get(Tenant, uuid.UUID(str(created["id"])))
        if tenant is None:
            tenant = _tenant_by_slug(session, slug)
    else:
        tenant = _tenant_by_slug(session, slug)
    tenant_id = str(tenant.id)
    _bootstrap_admin(tenant_id, email)
    mark_legacy_tenant_onboarding_complete(session, tenant.id)
    _clear_phones(session, tenant.id)

    phone_e164: str | None = None
    if mode == "with_phone":
        phone = make_phone(
            session,
            tenant,
            e164=f"+1555{uuid.uuid4().hex[:7]}",
        )
        phone_e164 = phone.e164
    elif mode == "pending_phone":
        phone = make_phone(
            session,
            tenant,
            e164=f"+1555{uuid.uuid4().hex[:7]}",
            connection_status=ConnectionStatus.PENDING_VERIFICATION.value,
            verification_status=VerificationStatus.PENDING.value,
            trunk_id=None,
            dispatch_id=None,
        )
        phone_e164 = phone.e164
    elif mode == "no_phone":
        pass
    else:
        raise ValueError(mode)

    session.commit()
    return {
        "slug": slug,
        "name": name,
        "email": email,
        "password": PASSWORD,
        "tenant_id": tenant_id,
        "mode": mode,
        "phone_e164": phone_e164,
        "created_via_api": not created.get("exists"),
    }


def main() -> None:
    _load_dotenv_local()
    suffix = uuid.uuid4().hex[:8]
    engine = create_engine(_db_url(), pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        fixtures = {
            "api_url": _api(),
            "web_url": os.environ.get("PLAYWRIGHT_BASE_URL", "http://localhost:3002"),
            "tenants": {
                "no_phone": _seed_scenario(
                    session,
                    slug=f"e2e-nophone-{suffix}",
                    name=f"E2E No Phone {suffix}",
                    email=f"owner-nophone-{suffix}@e2e.test",
                    mode="no_phone",
                ),
                "with_phone": _seed_scenario(
                    session,
                    slug=f"e2e-ready-{suffix}",
                    name=f"E2E Ready Phone {suffix}",
                    email=f"owner-ready-{suffix}@e2e.test",
                    mode="with_phone",
                ),
                "pending_phone": _seed_scenario(
                    session,
                    slug=f"e2e-pending-{suffix}",
                    name=f"E2E Pending Phone {suffix}",
                    email=f"owner-pending-{suffix}@e2e.test",
                    mode="pending_phone",
                ),
            },
        }
    finally:
        session.close()
        engine.dispose()

    FIXTURES_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURES_PATH.write_text(json.dumps(fixtures, indent=2) + "\n")
    print(f"Wrote {FIXTURES_PATH}")
    for key, row in fixtures["tenants"].items():
        print(f"  {key}: slug={row['slug']} email={row['email']} mode={row['mode']}")


if __name__ == "__main__":
    main()

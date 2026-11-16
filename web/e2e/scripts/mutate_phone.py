#!/usr/bin/env python3
"""Mutate an E2E tenant's phone eligibility (lose / restore last eligible DID)."""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

PLATFORM_SRC = Path(__file__).resolve().parents[3] / "platform" / "src"
TESTS_DIR = Path(__file__).resolve().parents[3] / "platform" / "tests"
sys.path.insert(0, str(PLATFORM_SRC))
sys.path.insert(0, str(TESTS_DIR))

from callbot_platform.db.models import TenantPhoneNumber  # noqa: E402
from callbot_platform.domain.enums import (  # noqa: E402
    ConnectionStatus,
    VerificationStatus,
)
from helpers import make_phone  # noqa: E402
from callbot_platform.db.models import Tenant  # noqa: E402


def _load_dotenv_local() -> None:
    env_path = Path(__file__).resolve().parents[3] / "platform" / ".env.local"
    if not env_path.is_file():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key in {"DATABASE_URL", "INTERNAL_SERVICE_TOKEN"} or key not in os.environ:
            os.environ[key] = value


def main() -> None:
    _load_dotenv_local()
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--action", choices=("lose", "restore"), required=True)
    args = parser.parse_args()
    db = (
        os.environ.get("E2E_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or ""
    ).strip()
    if not db:
        raise SystemExit("DATABASE_URL required")

    engine = create_engine(db, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        tenant_id = uuid.UUID(args.tenant_id)
        tenant = session.get(Tenant, tenant_id)
        if tenant is None:
            raise SystemExit("tenant not found")
        rows = list(
            session.scalars(
                select(TenantPhoneNumber).where(
                    TenantPhoneNumber.tenant_id == tenant_id
                )
            )
        )
        if args.action == "lose":
            for row in rows:
                row.connection_status = ConnectionStatus.RELEASED.value
                row.livekit_inbound_trunk_id = None
                row.livekit_dispatch_rule_id = None
            session.commit()
            print("lost")
            return
        # restore
        eligible = [
            r
            for r in rows
            if r.connection_status == ConnectionStatus.ACTIVE.value
            and r.verification_status == VerificationStatus.VERIFIED.value
            and r.livekit_inbound_trunk_id
            and r.livekit_dispatch_rule_id
        ]
        if eligible:
            print("already_ready")
            return
        if rows:
            row = rows[0]
            row.connection_status = ConnectionStatus.ACTIVE.value
            row.verification_status = VerificationStatus.VERIFIED.value
            row.livekit_inbound_trunk_id = row.livekit_inbound_trunk_id or "ST_e2e"
            row.livekit_dispatch_rule_id = row.livekit_dispatch_rule_id or "SDR_e2e"
        else:
            make_phone(session, tenant, e164=f"+1555{uuid.uuid4().hex[:7]}")
        session.commit()
        print("restored")
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    main()

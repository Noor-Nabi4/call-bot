"""Shared test fixtures for platform telephony."""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from sqlalchemy.orm import Session

from callbot_platform.db import get_session_factory, init_db
from callbot_platform.db.models import Tenant
from callbot_platform.security.crypto import CredentialCipher
from callbot_platform.security.metadata import MetadataSigner

TEST_DB = "sqlite:///:memory:"
HMAC_SECRET = "test-metadata-hmac-secret"
CRYPTO_SECRET = "test-credentials-encryption-key"


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    init_db(TEST_DB)
    factory = get_session_factory()
    db = factory()
    try:
        yield db
        db.commit()
    finally:
        db.close()


@pytest.fixture()
def signer() -> MetadataSigner:
    return MetadataSigner(HMAC_SECRET)


@pytest.fixture()
def cipher() -> CredentialCipher:
    return CredentialCipher(CRYPTO_SECRET)


@pytest.fixture()
def tenant(session: Session) -> Tenant:
    row = Tenant(name="Acme HVAC", slug=f"acme-{uuid.uuid4().hex[:8]}")
    session.add(row)
    session.flush()
    return row

"""Tenant DID resolver fail-closed tests."""

from __future__ import annotations

import pytest
from helpers import make_phone
from sqlalchemy.orm import Session

from callbot_platform.crm.repos import AgentProfileRepository
from callbot_platform.db.models import Tenant
from callbot_platform.domain.enums import ConnectionStatus, VerificationStatus
from callbot_platform.security.metadata import MetadataSigner
from callbot_platform.telephony.interfaces import ResolveRequest
from callbot_platform.telephony.services.resolver import (
    DbTenantDidResolver,
    TenantResolveError,
)


def _default_profile(session: Session, tenant: Tenant) -> None:
    AgentProfileRepository(session).create(
        tenant.id,
        name="Main Receptionist",
        agent_type="receptionist",
        is_default=True,
        actor="test",
    )


def test_resolve_by_active_did(
    session: Session, tenant: Tenant, signer: MetadataSigner
) -> None:
    _default_profile(session, tenant)
    make_phone(session, tenant, e164="+15551234567")
    resolver = DbTenantDidResolver(session, signer)
    result = resolver.resolve(ResolveRequest(called_number="+15551234567", is_sip=True))
    assert result.tenant_id == tenant.id
    assert result.source == "did_mapping"
    assert result.agent_profile_id is not None


def test_unknown_did_rejected(session: Session, signer: MetadataSigner) -> None:
    resolver = DbTenantDidResolver(session, signer)
    with pytest.raises(TenantResolveError) as exc:
        resolver.resolve(ResolveRequest(called_number="+15550001111", is_sip=True))
    assert exc.value.code == "unknown_did"


def test_inactive_did_rejected(
    session: Session, tenant: Tenant, signer: MetadataSigner
) -> None:
    make_phone(
        session,
        tenant,
        connection_status=ConnectionStatus.PENDING_VERIFICATION.value,
        verification_status=VerificationStatus.PENDING.value,
    )
    resolver = DbTenantDidResolver(session, signer)
    with pytest.raises(TenantResolveError) as exc:
        resolver.resolve(ResolveRequest(called_number="+15551234567", is_sip=True))
    assert exc.value.code == "did_inactive"


def test_unverified_did_rejected(
    session: Session, tenant: Tenant, signer: MetadataSigner
) -> None:
    make_phone(
        session,
        tenant,
        connection_status=ConnectionStatus.ACTIVE.value,
        verification_status=VerificationStatus.UNVERIFIED.value,
    )
    resolver = DbTenantDidResolver(session, signer)
    with pytest.raises(TenantResolveError) as exc:
        resolver.resolve(ResolveRequest(called_number="+15551234567", is_sip=True))
    assert exc.value.code in {"did_unverified", "did_inactive"}


def test_metadata_conflict_with_did(
    session: Session, tenant: Tenant, signer: MetadataSigner
) -> None:
    other = Tenant(name="Other", slug="other-co")
    session.add(other)
    session.flush()
    make_phone(session, tenant, e164="+15551234567")
    meta = signer.sign_payload(
        {"tenant_id": str(other.id), "did": "+15551234567", "source": "sip"}
    )
    resolver = DbTenantDidResolver(session, signer)
    with pytest.raises(TenantResolveError) as exc:
        resolver.resolve(
            ResolveRequest(
                job_metadata_raw=meta,
                called_number="+15551234567",
                is_sip=True,
            )
        )
    assert exc.value.code == "metadata_conflict"


def test_signed_metadata_browser_ok(
    session: Session, tenant: Tenant, signer: MetadataSigner
) -> None:
    meta = signer.sign_payload({"tenant_id": str(tenant.id), "source": "playground"})
    resolver = DbTenantDidResolver(session, signer)
    result = resolver.resolve(ResolveRequest(job_metadata_raw=meta, is_sip=False))
    assert result.tenant_id == tenant.id
    assert result.source == "signed_metadata"


def test_resolve_by_trunk(
    session: Session, tenant: Tenant, signer: MetadataSigner
) -> None:
    _default_profile(session, tenant)
    make_phone(session, tenant, trunk_id="ST_abc")
    resolver = DbTenantDidResolver(session, signer)
    result = resolver.resolve(
        ResolveRequest(livekit_inbound_trunk_id="ST_abc", is_sip=True)
    )
    assert result.tenant_id == tenant.id
    assert result.source == "livekit_trunk"
    assert result.agent_profile_id is not None

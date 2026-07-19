"""Connect-existing, verification, and purchase service tests with fakes."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.config import Settings
from callbot_platform.db.models import Tenant, TenantPhoneNumber, TelephonyIdempotencyKey
from callbot_platform.domain.enums import ConnectionStatus, VerificationStatus
from callbot_platform.security.crypto import CredentialCipher
from callbot_platform.security.metadata import MetadataSigner
from callbot_platform.telephony.interfaces import (
    AvailableNumber,
    LiveKitDispatchRuleInfo,
    LiveKitInboundTrunkInfo,
    PurchasedNumber,
    TwilioTrunkInfo,
)
from callbot_platform.telephony.services.connect_existing import (
    ConnectExistingError,
    ConnectExistingService,
)
from callbot_platform.telephony.services.purchase import PlatformPurchaseService, PurchaseError
from callbot_platform.telephony.services.verification import DbNumberVerificationService
from helpers import make_phone


class FakeLiveKit:
    def __init__(self) -> None:
        self.trunks: list[str] = []
        self.rules: list[str] = []
        self.deleted_trunks: list[str] = []
        self.deleted_rules: list[str] = []

    def create_livekit_inbound_trunk(
        self, *, name: str, numbers: list[str], metadata: str | None = None
    ) -> LiveKitInboundTrunkInfo:
        trunk_id = f"ST_{len(self.trunks)+1}"
        self.trunks.append(trunk_id)
        return LiveKitInboundTrunkInfo(trunk_id=trunk_id, name=name, numbers=numbers)

    def delete_livekit_inbound_trunk(self, trunk_id: str) -> None:
        self.deleted_trunks.append(trunk_id)

    def create_individual_dispatch_rule(
        self,
        *,
        name: str,
        agent_name: str,
        metadata: str,
        trunk_ids: list[str],
        room_prefix: str = "call-",
    ) -> LiveKitDispatchRuleInfo:
        rule_id = f"SDR_{len(self.rules)+1}"
        self.rules.append(rule_id)
        return LiveKitDispatchRuleInfo(dispatch_rule_id=rule_id, name=name)

    def delete_dispatch_rule(self, dispatch_rule_id: str) -> None:
        self.deleted_rules.append(dispatch_rule_id)


class FakeInventory:
    def search(self, **kwargs: Any) -> list[AvailableNumber]:
        return [
            AvailableNumber(
                e164="+15559876543",
                friendly_name="(555) 987-6543",
                locality="San Francisco",
                region="CA",
                iso_country="US",
                capabilities={"voice": True, "sms": True, "mms": False},
                monthly_price="1.15",
                price_unit="USD",
            )
        ]


class FakeProvisioning:
    def __init__(self) -> None:
        self.purchases: list[str] = []
        self.releases: list[str] = []
        self.fail_next = False

    def purchase(self, **kwargs: Any) -> PurchasedNumber:
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("twilio purchase failed")
        e164 = kwargs["e164"]
        self.purchases.append(e164)
        return PurchasedNumber(
            e164=e164, phone_number_sid="PN123", account_sid=kwargs["account_sid"]
        )

    def release(self, **kwargs: Any) -> None:
        self.releases.append(kwargs["phone_number_sid"])


class FakeTwilioSip:
    def __init__(self) -> None:
        self.associations: list[tuple[str, str]] = []

    def create_subaccount(self, **kwargs: Any) -> tuple[str, str]:
        return "ACsub123", "sub-auth-token"

    def create_or_get_twilio_trunk(self, **kwargs: Any) -> TwilioTrunkInfo:
        return TwilioTrunkInfo(
            trunk_sid="TKtrunk",
            friendly_name=kwargs["friendly_name"],
            domain_name=kwargs["domain_name"],
        )

    def associate_number_with_twilio_trunk(self, **kwargs: Any) -> None:
        self.associations.append((kwargs["trunk_sid"], kwargs["phone_number_sid"]))


def _settings() -> Settings:
    return Settings(
        LIVEKIT_URL="wss://example.livekit.cloud",
        LIVEKIT_API_KEY="key",
        LIVEKIT_API_SECRET="secret",
        LIVEKIT_SIP_HOST="example.sip.livekit.cloud",
        TWILIO_ACCOUNT_SID="ACmaster",
        TWILIO_AUTH_TOKEN="master-token",
        CREDENTIALS_ENCRYPTION_KEY="test-credentials-encryption-key",
        METADATA_HMAC_SECRET="test-metadata-hmac-secret",
        INTERNAL_SERVICE_TOKEN="internal",
    )


def test_connect_existing_registers_and_creates_livekit(
    session: Session, tenant: Tenant, signer: MetadataSigner
) -> None:
    lk = FakeLiveKit()
    service = ConnectExistingService(session, _settings(), lk, signer)  # type: ignore[arg-type]
    result = service.start(tenant_id=tenant.id, phone_number="+1 555 111 2222")
    phone = result["phone_number"]
    assert phone["e164"] == "+15551112222"
    assert phone["livekit_inbound_trunk_id"]
    assert phone["livekit_dispatch_rule_id"]
    assert "twilio_setup" in result
    assert result["twilio_setup"]["steps"]


def test_duplicate_number_prevented(
    session: Session, tenant: Tenant, signer: MetadataSigner
) -> None:
    make_phone(session, tenant, e164="+15551112222")
    service = ConnectExistingService(session, _settings(), FakeLiveKit(), signer)  # type: ignore[arg-type]
    with pytest.raises(ConnectExistingError) as exc:
        service.start(tenant_id=tenant.id, phone_number="+15551112222")
    assert exc.value.code == "duplicate_number"


def test_verification_flow(
    session: Session, tenant: Tenant, signer: MetadataSigner
) -> None:
    lk = FakeLiveKit()
    connect = ConnectExistingService(session, _settings(), lk, signer)  # type: ignore[arg-type]
    started = connect.start(tenant_id=tenant.id, phone_number="+15553334444")
    phone_id = UUID(started["phone_number"]["id"])
    connect.confirm_trunk(
        tenant_id=tenant.id, phone_number_id=phone_id, twilio_trunk_sid="TKabc"
    )
    verification = DbNumberVerificationService(session)
    challenge = verification.start_verification(
        tenant_id=tenant.id, phone_number_id=phone_id
    )
    assert challenge["verification_status"] == VerificationStatus.PENDING.value
    observed = verification.observe_inbound(
        called_number="+15553334444",
        caller_number="+15550001111",
        livekit_inbound_trunk_id=started["phone_number"]["livekit_inbound_trunk_id"],
        livekit_room_name="call-+15550001111_xyz",
        provider_call_id="CA123",
    )
    assert observed["activated"] is True
    row = session.get(TenantPhoneNumber, phone_id)
    assert row is not None
    assert row.connection_status == ConnectionStatus.ACTIVE.value
    assert row.verification_status == VerificationStatus.VERIFIED.value


def test_purchase_requires_confirmation(
    session: Session,
    tenant: Tenant,
    signer: MetadataSigner,
    cipher: CredentialCipher,
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
        service.purchase(
            tenant_id=tenant.id,
            phone_number="+15559876543",
            confirm=False,
            idempotency_key="key-1",
        )
    assert exc.value.code == "confirmation_required"


def test_idempotent_purchase(
    session: Session,
    tenant: Tenant,
    signer: MetadataSigner,
    cipher: CredentialCipher,
) -> None:
    provisioning = FakeProvisioning()
    service = PlatformPurchaseService(
        session,
        _settings(),
        cipher=cipher,
        signer=signer,
        inventory=FakeInventory(),  # type: ignore[arg-type]
        provisioning=provisioning,  # type: ignore[arg-type]
        twilio_sip=FakeTwilioSip(),  # type: ignore[arg-type]
        livekit=FakeLiveKit(),  # type: ignore[arg-type]
    )
    first = service.purchase(
        tenant_id=tenant.id,
        phone_number="+15559876543",
        confirm=True,
        idempotency_key="same-key",
    )
    second = service.purchase(
        tenant_id=tenant.id,
        phone_number="+15559876543",
        confirm=True,
        idempotency_key="same-key",
    )
    assert first == second
    assert len(provisioning.purchases) == 1


def test_failed_purchase_not_blindly_retried(
    session: Session,
    tenant: Tenant,
    signer: MetadataSigner,
    cipher: CredentialCipher,
) -> None:
    provisioning = FakeProvisioning()
    provisioning.fail_next = True
    service = PlatformPurchaseService(
        session,
        _settings(),
        cipher=cipher,
        signer=signer,
        inventory=FakeInventory(),  # type: ignore[arg-type]
        provisioning=provisioning,  # type: ignore[arg-type]
        twilio_sip=FakeTwilioSip(),  # type: ignore[arg-type]
        livekit=FakeLiveKit(),  # type: ignore[arg-type]
    )
    with pytest.raises(PurchaseError) as exc:
        service.purchase(
            tenant_id=tenant.id,
            phone_number="+15557654321",
            confirm=True,
            idempotency_key="fail-key",
        )
    assert exc.value.code == "partial_provisioning"
    # Blind retry with same key refused
    with pytest.raises(PurchaseError) as exc2:
        service.purchase(
            tenant_id=tenant.id,
            phone_number="+15557654321",
            confirm=True,
            idempotency_key="fail-key",
        )
    assert exc2.value.code == "failed_purchase_not_retryable"
    row = session.scalar(
        select(TelephonyIdempotencyKey).where(
            TelephonyIdempotencyKey.key == "fail-key"
        )
    )
    assert row is not None
    assert row.status == "failed"


def test_inventory_mapping(
    session: Session,
    tenant: Tenant,
    signer: MetadataSigner,
    cipher: CredentialCipher,
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
    items = service.search_inventory(tenant_id=tenant.id, country="US")
    assert items[0]["e164"] == "+15559876543"
    assert items[0]["monthly_price"] == "1.15"


def test_release_authorization_path_a_denied(
    session: Session,
    tenant: Tenant,
    signer: MetadataSigner,
    cipher: CredentialCipher,
) -> None:
    phone = make_phone(session, tenant)
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
        service.release(
            tenant_id=tenant.id,
            phone_number_id=phone.id,
            phone_number_sid="PN123",
        )
    assert exc.value.code == "release_not_allowed"


def test_tenant_isolation_on_verification(
    session: Session, tenant: Tenant
) -> None:
    other = Tenant(name="Other", slug="other")
    session.add(other)
    session.flush()
    phone = make_phone(
        session,
        tenant,
        connection_status=ConnectionStatus.PENDING_VERIFICATION.value,
        verification_status=VerificationStatus.UNVERIFIED.value,
    )
    verification = DbNumberVerificationService(session)
    with pytest.raises(Exception):
        verification.start_verification(
            tenant_id=other.id, phone_number_id=phone.id
        )

"""Provider-neutral telephony interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

from callbot_platform.domain.enums import TelephonyProviderId


@dataclass(frozen=True)
class AvailableNumber:
    e164: str
    friendly_name: str | None
    locality: str | None
    region: str | None
    iso_country: str
    capabilities: dict[str, bool]
    monthly_price: str | None
    price_unit: str | None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PurchasedNumber:
    e164: str
    phone_number_sid: str
    account_sid: str


@dataclass(frozen=True)
class TwilioTrunkInfo:
    trunk_sid: str
    friendly_name: str
    domain_name: str | None = None


@dataclass(frozen=True)
class LiveKitInboundTrunkInfo:
    trunk_id: str
    name: str
    numbers: list[str]


@dataclass(frozen=True)
class LiveKitDispatchRuleInfo:
    dispatch_rule_id: str
    name: str


@dataclass(frozen=True)
class ResolveRequest:
    job_metadata_raw: str | None = None
    called_number: str | None = None
    livekit_inbound_trunk_id: str | None = None
    is_sip: bool = False


@dataclass(frozen=True)
class ResolveResult:
    tenant_id: UUID
    phone_number_id: UUID | None
    e164: str | None
    source: str
    livekit_inbound_trunk_id: str | None = None
    livekit_dispatch_rule_id: str | None = None


class TelephonyProvider(Protocol):
    @property
    def provider_id(self) -> TelephonyProviderId: ...

    @property
    def supports_inventory(self) -> bool: ...

    @property
    def supports_purchase(self) -> bool: ...


class NumberInventoryService(Protocol):
    def search(
        self,
        *,
        account_sid: str,
        auth_token: str,
        country: str,
        area_code: str | None = None,
        number_type: str = "local",
        voice_enabled: bool = True,
        sms_enabled: bool | None = None,
        limit: int = 20,
    ) -> list[AvailableNumber]: ...


class NumberProvisioningService(Protocol):
    def purchase(
        self,
        *,
        account_sid: str,
        auth_token: str,
        e164: str,
        idempotency_key: str | None = None,
    ) -> PurchasedNumber: ...

    def release(
        self,
        *,
        account_sid: str,
        auth_token: str,
        phone_number_sid: str,
    ) -> None: ...


class SipTrunkService(Protocol):
    def create_or_get_twilio_trunk(
        self,
        *,
        account_sid: str,
        auth_token: str,
        friendly_name: str,
        domain_name: str,
        livekit_origination_uri: str,
    ) -> TwilioTrunkInfo: ...

    def associate_number_with_twilio_trunk(
        self,
        *,
        account_sid: str,
        auth_token: str,
        trunk_sid: str,
        phone_number_sid: str,
    ) -> None: ...

    def create_livekit_inbound_trunk(
        self,
        *,
        name: str,
        numbers: list[str],
        metadata: str | None = None,
    ) -> LiveKitInboundTrunkInfo: ...

    def delete_livekit_inbound_trunk(self, trunk_id: str) -> None: ...


class DispatchRuleService(Protocol):
    def create_individual_dispatch_rule(
        self,
        *,
        name: str,
        agent_name: str,
        metadata: str,
        trunk_ids: list[str],
        room_prefix: str = "call-",
    ) -> LiveKitDispatchRuleInfo: ...

    def delete_dispatch_rule(self, dispatch_rule_id: str) -> None: ...


class TenantDidResolver(Protocol):
    def resolve(self, request: ResolveRequest) -> ResolveResult: ...


class NumberVerificationService(Protocol):
    def start_verification(self, *, tenant_id: UUID, phone_number_id: UUID) -> dict[str, Any]: ...

    def observe_inbound(
        self,
        *,
        called_number: str,
        caller_number: str | None,
        livekit_inbound_trunk_id: str | None,
        livekit_room_name: str | None,
        provider_call_id: str | None,
    ) -> dict[str, Any]: ...

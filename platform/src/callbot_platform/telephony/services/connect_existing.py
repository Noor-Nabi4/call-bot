"""Path A: connect an existing Twilio number (manual Elastic SIP setup)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.config import Settings
from callbot_platform.db.models import Tenant, TenantPhoneNumber
from callbot_platform.domain.enums import (
    AuthMethod,
    ConnectionStatus,
    OnboardingPath,
    ProvisioningState,
    TelephonyProviderId,
    VerificationStatus,
)
from callbot_platform.domain.phone import PhoneNumberError, normalize_e164
from callbot_platform.security.metadata import MetadataSigner
from callbot_platform.telephony.adapters.livekit_sip import LiveKitApiError, LiveKitSipService
from callbot_platform.telephony.audit import write_audit


class ConnectExistingError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ConnectExistingService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        livekit: LiveKitSipService,
        signer: MetadataSigner,
    ) -> None:
        self._session = session
        self._settings = settings
        self._livekit = livekit
        self._signer = signer

    def start(
        self,
        *,
        tenant_id: UUID,
        phone_number: str,
        twilio_account_sid: str | None = None,
        actor: str = "tenant_user",
    ) -> dict[str, Any]:
        tenant = self._session.get(Tenant, tenant_id)
        if tenant is None:
            raise ConnectExistingError("tenant_not_found", "Tenant not found")

        try:
            e164 = normalize_e164(phone_number)
        except PhoneNumberError as exc:
            raise ConnectExistingError("invalid_phone", str(exc)) from exc

        existing = self._session.scalar(
            select(TenantPhoneNumber).where(TenantPhoneNumber.e164 == e164)
        )
        if existing is not None:
            raise ConnectExistingError(
                "duplicate_number",
                f"Phone number {e164} is already registered",
            )

        row = TenantPhoneNumber(
            tenant_id=tenant_id,
            provider=TelephonyProviderId.TWILIO.value,
            e164=e164,
            twilio_account_sid=twilio_account_sid,
            connection_status=ConnectionStatus.CONFIGURING.value,
            verification_status=VerificationStatus.UNVERIFIED.value,
            onboarding_path=OnboardingPath.CONNECT_EXISTING.value,
            auth_method=AuthMethod.MANUAL.value,
            provisioning_state=ProvisioningState.IN_PROGRESS.value,
            provisioning_details={},
        )
        self._session.add(row)
        self._session.flush()

        metadata = self._signer.sign_payload(
            {
                "tenant_id": str(tenant_id),
                "did": e164,
                "phone_number_id": str(row.id),
                "source": "sip_dispatch",
                **(
                    {"agent_profile_id": str(tenant.default_agent_profile_id)}
                    if tenant.default_agent_profile_id
                    else {}
                ),
            }
        )

        details: dict[str, Any] = {"steps_completed": []}
        try:
            trunk = self._livekit.create_livekit_inbound_trunk(
                name=f"inbound-{tenant.slug}-{e164}",
                numbers=[e164],
                metadata=metadata,
            )
            row.livekit_inbound_trunk_id = trunk.trunk_id
            details["steps_completed"].append("livekit_inbound_trunk")
            details["livekit_inbound_trunk_id"] = trunk.trunk_id

            dispatch = self._livekit.create_individual_dispatch_rule(
                name=f"dispatch-{tenant.slug}-{e164}",
                agent_name=self._settings.agent_name,
                metadata=metadata,
                trunk_ids=[trunk.trunk_id],
                room_prefix="call-",
            )
            row.livekit_dispatch_rule_id = dispatch.dispatch_rule_id
            details["steps_completed"].append("livekit_dispatch_rule")
            details["livekit_dispatch_rule_id"] = dispatch.dispatch_rule_id

            row.connection_status = ConnectionStatus.PENDING_SETUP.value
            row.provisioning_state = ProvisioningState.COMPLETE.value
            row.provisioning_details = details
            row.updated_at = datetime.now(UTC)
        except (LiveKitApiError, Exception) as exc:
            row.connection_status = ConnectionStatus.PARTIAL.value
            row.provisioning_state = ProvisioningState.PARTIAL.value
            details["error"] = str(exc)
            row.provisioning_details = details
            row.updated_at = datetime.now(UTC)
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="connect_existing_partial",
                resource_ids={"phone_number_id": str(row.id), "e164": e164},
                payload_summary=details,
            )
            self._session.flush()
            raise ConnectExistingError(
                "partial_provisioning",
                f"Partial LiveKit provisioning; recover manually: {exc}",
            ) from exc

        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="connect_existing_started",
            resource_ids={
                "phone_number_id": str(row.id),
                "e164": e164,
                "livekit_inbound_trunk_id": row.livekit_inbound_trunk_id,
                "livekit_dispatch_rule_id": row.livekit_dispatch_rule_id,
            },
        )
        self._session.flush()

        return {
            "phone_number": self._serialize(row),
            "twilio_setup": self._twilio_instructions(e164),
        }

    def confirm_trunk(
        self,
        *,
        tenant_id: UUID,
        phone_number_id: UUID,
        twilio_trunk_sid: str | None,
        actor: str = "tenant_user",
    ) -> dict[str, Any]:
        row = self._owned(tenant_id, phone_number_id)
        if twilio_trunk_sid:
            row.twilio_trunk_sid = twilio_trunk_sid.strip()
        row.connection_status = ConnectionStatus.PENDING_VERIFICATION.value
        row.updated_at = datetime.now(UTC)
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="connect_existing_trunk_confirmed",
            resource_ids={
                "phone_number_id": str(row.id),
                "twilio_trunk_sid": row.twilio_trunk_sid,
            },
        )
        self._session.flush()
        return self._serialize(row)

    def _twilio_instructions(self, e164: str) -> dict[str, Any]:
        uri = self._settings.livekit_origination_uri
        return {
            "provider": "twilio",
            "e164": e164,
            "steps": [
                {
                    "step": 1,
                    "title": "Create Elastic SIP Trunk",
                    "ui": (
                        "Twilio Console → Elastic SIP Trunking → Trunks → Create new SIP trunk"
                    ),
                    "cli": (
                        'twilio api trunking v1 trunks create '
                        '--friendly-name "LiveKit inbound" '
                        '--domain-name "livekit-inbound-<unique>.pstn.twilio.com"'
                    ),
                },
                {
                    "step": 2,
                    "title": "Add Origination URI to LiveKit",
                    "ui": (
                        f"Trunk → Origination → Add Origination URI → {uri}"
                    ),
                    "cli": (
                        "twilio api trunking v1 trunks origination-urls create "
                        "--trunk-sid <twilio_trunk_sid> "
                        '--friendly-name "LiveKit SIP URI" '
                        f'--sip-url "{uri}" --weight 1 --priority 1 --enabled'
                    ),
                    "origination_uri": uri,
                },
                {
                    "step": 3,
                    "title": "Associate your existing number with the trunk",
                    "ui": "Trunk → Numbers → Add your existing Twilio number",
                    "cli": (
                        "twilio api trunking v1 trunks phone-numbers create "
                        "--trunk-sid <twilio_trunk_sid> "
                        "--phone-number-sid <twilio_phone_number_sid>"
                    ),
                    "number": e164,
                },
                {
                    "step": 4,
                    "title": "Paste Twilio trunk SID (optional) and start verification",
                    "ui": "Return to the wizard → Confirm trunk → Start verification call",
                },
            ],
            "notes": [
                "Do not share your Twilio Auth Token with this platform for Path A.",
                "Twilio Elastic SIP Trunking does not support username/password auth for LiveKit inbound trunks.",
                "Number becomes active only after a successful inbound verification call.",
            ],
            "docs": {
                "livekit_twilio": "https://docs.livekit.io/telephony/start/providers/twilio/",
                "livekit_inbound_trunk": "https://docs.livekit.io/telephony/accepting-calls/inbound-trunk/",
                "livekit_dispatch_rule": "https://docs.livekit.io/telephony/accepting-calls/dispatch-rule/",
            },
        }

    def _owned(self, tenant_id: UUID, phone_number_id: UUID) -> TenantPhoneNumber:
        row = self._session.get(TenantPhoneNumber, phone_number_id)
        if row is None or row.tenant_id != tenant_id:
            raise ConnectExistingError("not_found", "Phone number not found for tenant")
        return row

    def _serialize(self, row: TenantPhoneNumber) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "tenant_id": str(row.tenant_id),
            "provider": row.provider,
            "e164": row.e164,
            "twilio_account_sid": row.twilio_account_sid,
            "twilio_trunk_sid": row.twilio_trunk_sid,
            "livekit_inbound_trunk_id": row.livekit_inbound_trunk_id,
            "livekit_dispatch_rule_id": row.livekit_dispatch_rule_id,
            "connection_status": row.connection_status,
            "verification_status": row.verification_status,
            "onboarding_path": row.onboarding_path,
            "auth_method": row.auth_method,
            "oauth_connection_id": row.oauth_connection_id,
            "provisioning_state": row.provisioning_state,
            "provisioning_details": row.provisioning_details,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

"""Path A: connect an existing Twilio number (manual Elastic SIP setup)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.async_jobs.service import AsyncJobService
from callbot_platform.async_jobs.types import JobType
from callbot_platform.billing.entitlements import EntitlementError, EntitlementGuard
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
from callbot_platform.telephony.adapters.livekit_sip import LiveKitSipService
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

        try:
            EntitlementGuard(self._session).require_capacity(tenant_id, "phone_numbers")
        except EntitlementError as exc:
            raise ConnectExistingError(exc.code, str(exc)) from exc

        _ = tenant  # validated above; LiveKit work runs in async job after commit
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
            provisioning_details={"steps_completed": []},
        )
        self._session.add(row)
        self._session.flush()

        job = AsyncJobService(self._session, settings=self._settings).enqueue(
            tenant_id=tenant_id,
            job_type=JobType.TELEPHONY_PROVISION_CONNECT,
            idempotency_key=f"tenant:{tenant_id}:phone:{row.id}:connect",
            resource_id=str(row.id),
            payload={"phone_number_id": str(row.id), "e164": e164},
        )

        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="connect_existing_queued",
            resource_ids={
                "phone_number_id": str(row.id),
                "e164": e164,
                "job_id": str(job.id),
            },
        )
        self._session.flush()

        return {
            "phone_number": self._serialize(row),
            "job_id": str(job.id),
            "provisioning": "queued",
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
                        "twilio api trunking v1 trunks create "
                        '--friendly-name "LiveKit inbound" '
                        '--domain-name "livekit-inbound-<unique>.pstn.twilio.com"'
                    ),
                },
                {
                    "step": 2,
                    "title": "Add Origination URI to LiveKit",
                    "ui": (f"Trunk → Origination → Add Origination URI → {uri}"),
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

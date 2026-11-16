"""Path B: purchase Twilio numbers via platform subaccounts (saga / async job)."""

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
from callbot_platform.db.models import (
    TelephonyIdempotencyKey,
    Tenant,
    TenantPhoneNumber,
    TenantTwilioSubaccount,
)
from callbot_platform.domain.enums import (
    AuthMethod,
    ConnectionStatus,
    OnboardingPath,
    ProvisioningState,
    TelephonyProviderId,
    VerificationStatus,
)
from callbot_platform.domain.phone import PhoneNumberError, normalize_e164
from callbot_platform.security.crypto import CredentialCipher
from callbot_platform.security.metadata import MetadataSigner
from callbot_platform.telephony.adapters.livekit_sip import LiveKitSipService
from callbot_platform.telephony.adapters.twilio_adapter import (
    TwilioNumberInventoryService,
    TwilioNumberProvisioningService,
    TwilioSipTrunkService,
)
from callbot_platform.telephony.audit import write_audit


class PurchaseError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class PlatformPurchaseService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        *,
        cipher: CredentialCipher,
        signer: MetadataSigner,
        inventory: TwilioNumberInventoryService,
        provisioning: TwilioNumberProvisioningService,
        twilio_sip: TwilioSipTrunkService,
        livekit: LiveKitSipService,
    ) -> None:
        self._session = session
        self._settings = settings
        self._cipher = cipher
        self._signer = signer
        self._inventory = inventory
        self._provisioning = provisioning
        self._twilio_sip = twilio_sip
        self._livekit = livekit

    def ensure_subaccount(
        self, *, tenant_id: UUID, actor: str = "system"
    ) -> dict[str, Any]:
        """
        Ensure Twilio subaccount exists.

        Reads DB then calls Twilio only when missing — no write before provider call.
        """
        tenant = self._require_tenant(tenant_id)
        existing = self._session.scalar(
            select(TenantTwilioSubaccount).where(
                TenantTwilioSubaccount.tenant_id == tenant_id
            )
        )
        if existing is not None:
            return {
                "twilio_subaccount_sid": existing.twilio_subaccount_sid,
                "friendly_name": existing.friendly_name,
                "created": False,
            }

        if (
            not self._settings.twilio_account_sid
            or not self._settings.twilio_auth_token
        ):
            raise PurchaseError(
                "twilio_not_configured",
                "Platform Twilio master credentials are required for Path B",
            )

        friendly = f"call-bot-{tenant.slug}"
        # Provider I/O before any DB write for this resource.
        sid, token = self._twilio_sip.create_subaccount(
            master_account_sid=self._settings.twilio_account_sid,
            master_auth_token=self._settings.twilio_auth_token,
            friendly_name=friendly,
        )
        if not token:
            raise PurchaseError(
                "subaccount_token_unavailable",
                "Existing Twilio subaccount found but auth token is unavailable; "
                "store the subaccount token securely or create a new friendly name",
            )

        # Re-check race: another request may have inserted meanwhile.
        existing = self._session.scalar(
            select(TenantTwilioSubaccount).where(
                TenantTwilioSubaccount.tenant_id == tenant_id
            )
        )
        if existing is not None:
            return {
                "twilio_subaccount_sid": existing.twilio_subaccount_sid,
                "friendly_name": existing.friendly_name,
                "created": False,
            }

        row = TenantTwilioSubaccount(
            tenant_id=tenant_id,
            twilio_subaccount_sid=sid,
            encrypted_auth_token=self._cipher.encrypt(token),
            friendly_name=friendly,
        )
        self._session.add(row)
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="twilio_subaccount_created",
            resource_ids={"twilio_subaccount_sid": sid},
        )
        self._session.flush()
        return {
            "twilio_subaccount_sid": sid,
            "friendly_name": friendly,
            "created": True,
        }

    def search_inventory(
        self,
        *,
        tenant_id: UUID,
        country: str,
        area_code: str | None = None,
        number_type: str = "local",
        voice_enabled: bool = True,
        sms_enabled: bool | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Read-only Twilio inventory search.

        Requires an existing subaccount (call ensure_subaccount first).
        Does not write during the provider call.
        """
        row = self._session.scalar(
            select(TenantTwilioSubaccount).where(
                TenantTwilioSubaccount.tenant_id == tenant_id
            )
        )
        if row is None:
            raise PurchaseError(
                "subaccount_required",
                "Twilio subaccount required before inventory search; "
                "call ensure_subaccount first",
            )
        account_sid = row.twilio_subaccount_sid
        auth_token = self._cipher.decrypt(row.encrypted_auth_token)
        # Snapshot credentials then expire ORM state so no dirty writes ride along.
        self._session.expire_all()
        numbers = self._inventory.search(
            account_sid=account_sid,
            auth_token=auth_token,
            country=country,
            area_code=area_code,
            number_type=number_type,
            voice_enabled=voice_enabled,
            sms_enabled=sms_enabled,
            limit=limit,
        )
        return [
            {
                "e164": n.e164,
                "friendly_name": n.friendly_name,
                "locality": n.locality,
                "region": n.region,
                "iso_country": n.iso_country,
                "capabilities": n.capabilities,
                "monthly_price": n.monthly_price,
                "price_unit": n.price_unit,
            }
            for n in numbers
        ]

    def release(
        self,
        *,
        tenant_id: UUID,
        phone_number_id: UUID,
        phone_number_sid: str | None = None,
        actor: str = "tenant_user",
    ) -> dict[str, Any]:
        """
        Queue release saga (no Twilio/LiveKit I/O in this transaction).

        Marks phone releasing + enqueues telephony.release job.
        """
        row = self._owned(tenant_id, phone_number_id)
        if row.onboarding_path != OnboardingPath.PLATFORM_PURCHASE.value:
            raise PurchaseError(
                "release_not_allowed",
                "Only platform-purchased numbers can be released via this API",
            )
        if row.connection_status == ConnectionStatus.RELEASED.value:
            return {"phone_number": self._serialize(row), "provisioning": "released"}
        if row.connection_status == ConnectionStatus.RELEASING.value:
            # Idempotent re-queue is handled by async job idempotency key.
            pass

        details = dict(row.provisioning_details or {})
        resolved_sid = phone_number_sid or details.get("phone_number_sid")
        if not isinstance(resolved_sid, str) or not resolved_sid.strip():
            raise PurchaseError(
                "missing_phone_sid",
                "Phone number SID is missing from provisioning details",
            )
        phone_number_sid = resolved_sid.strip()

        row.connection_status = ConnectionStatus.RELEASING.value
        row.provisioning_state = ProvisioningState.IN_PROGRESS.value
        details["release_requested_sid"] = phone_number_sid
        row.provisioning_details = details
        row.updated_at = datetime.now(UTC)
        self._session.flush()

        job = AsyncJobService(self._session, settings=self._settings).enqueue(
            tenant_id=tenant_id,
            job_type=JobType.TELEPHONY_RELEASE,
            idempotency_key=f"tenant:{tenant_id}:phone:{row.id}:release",
            resource_id=str(row.id),
            payload={
                "phone_number_id": str(row.id),
                "phone_number_sid": phone_number_sid,
            },
        )
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="number_release_queued",
            resource_ids={
                "phone_number_id": str(row.id),
                "e164": row.e164,
                "job_id": str(job.id),
            },
        )
        self._session.flush()
        return {
            "phone_number": self._serialize(row),
            "job_id": str(job.id),
            "provisioning": "queued",
        }

    def purchase(
        self,
        *,
        tenant_id: UUID,
        phone_number: str,
        confirm: bool,
        idempotency_key: str,
        actor: str = "tenant_user",
    ) -> dict[str, Any]:
        """
        Create internal phone intent + async provisioning job (no Twilio/LiveKit I/O).

        Caller must commit the DB transaction, then run AsyncJobWorker.process_job.
        """
        if not confirm:
            raise PurchaseError(
                "confirmation_required",
                "Explicit confirm=true is required to purchase a number",
            )
        if not idempotency_key or not idempotency_key.strip():
            raise PurchaseError(
                "idempotency_required",
                "Idempotency-Key is required for purchases",
            )

        try:
            EntitlementGuard(self._session).require_capacity(tenant_id, "phone_numbers")
        except EntitlementError as exc:
            raise PurchaseError(exc.code, str(exc)) from exc

        prior = self._session.scalar(
            select(TelephonyIdempotencyKey).where(
                TelephonyIdempotencyKey.tenant_id == tenant_id,
                TelephonyIdempotencyKey.operation == "purchase_number",
                TelephonyIdempotencyKey.key == idempotency_key.strip(),
            )
        )
        if prior is not None:
            if prior.status == "failed":
                raise PurchaseError(
                    "failed_purchase_not_retryable",
                    "A previous purchase with this Idempotency-Key failed; "
                    "do not retry blindly — use a new key after investigation",
                )
            return prior.response_json

        self._require_tenant(tenant_id)
        try:
            e164 = normalize_e164(phone_number)
        except PhoneNumberError as exc:
            raise PurchaseError("invalid_phone", str(exc)) from exc

        duplicate = self._session.scalar(
            select(TenantPhoneNumber).where(TenantPhoneNumber.e164 == e164)
        )
        if duplicate is not None:
            raise PurchaseError(
                "duplicate_number", f"Phone number {e164} is already registered"
            )

        row = TenantPhoneNumber(
            tenant_id=tenant_id,
            provider=TelephonyProviderId.TWILIO.value,
            e164=e164,
            twilio_account_sid=None,
            connection_status=ConnectionStatus.CONFIGURING.value,
            verification_status=VerificationStatus.UNVERIFIED.value,
            onboarding_path=OnboardingPath.PLATFORM_PURCHASE.value,
            auth_method=AuthMethod.PLATFORM_SUBACCOUNT.value,
            provisioning_state=ProvisioningState.IN_PROGRESS.value,
            provisioning_details={"steps_completed": []},
        )
        self._session.add(row)
        self._session.flush()

        job_key = f"tenant:{tenant_id}:phone:{row.id}:provision"
        job = AsyncJobService(self._session, settings=self._settings).enqueue(
            tenant_id=tenant_id,
            job_type=JobType.TELEPHONY_PROVISION_PURCHASE,
            idempotency_key=job_key,
            resource_id=str(row.id),
            payload={
                "phone_number_id": str(row.id),
                "idempotency_key": idempotency_key.strip(),
                "e164": e164,
            },
        )

        response = {
            "phone_number": self._serialize(row),
            "job_id": str(job.id),
            "provisioning": "queued",
        }
        self._store_idempotency(
            tenant_id=tenant_id,
            key=idempotency_key,
            response=response,
            status="queued",
        )
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="number_purchase_queued",
            resource_ids={
                "phone_number_id": str(row.id),
                "e164": e164,
                "job_id": str(job.id),
            },
            idempotency_key=idempotency_key,
        )
        self._session.flush()
        return response

    def mark_idempotency_completed(
        self, *, tenant_id: UUID, idempotency_key: str, response: dict[str, Any]
    ) -> None:
        prior = self._session.scalar(
            select(TelephonyIdempotencyKey).where(
                TelephonyIdempotencyKey.tenant_id == tenant_id,
                TelephonyIdempotencyKey.operation == "purchase_number",
                TelephonyIdempotencyKey.key == idempotency_key.strip(),
            )
        )
        if prior is None:
            return
        prior.status = "completed"
        prior.response_json = response
        self._session.flush()

    def mark_idempotency_failed(
        self, *, tenant_id: UUID, idempotency_key: str, response: dict[str, Any]
    ) -> None:
        prior = self._session.scalar(
            select(TelephonyIdempotencyKey).where(
                TelephonyIdempotencyKey.tenant_id == tenant_id,
                TelephonyIdempotencyKey.operation == "purchase_number",
                TelephonyIdempotencyKey.key == idempotency_key.strip(),
            )
        )
        if prior is None:
            return
        prior.status = "failed"
        prior.response_json = response
        self._session.flush()

    def _tenant_twilio_creds(self, tenant_id: UUID) -> tuple[str, str]:
        self.ensure_subaccount(tenant_id=tenant_id)
        row = self._session.scalar(
            select(TenantTwilioSubaccount).where(
                TenantTwilioSubaccount.tenant_id == tenant_id
            )
        )
        if row is None:
            raise PurchaseError("subaccount_missing", "Twilio subaccount missing")
        return row.twilio_subaccount_sid, self._cipher.decrypt(row.encrypted_auth_token)

    def _require_tenant(self, tenant_id: UUID) -> Tenant:
        tenant = self._session.get(Tenant, tenant_id)
        if tenant is None:
            raise PurchaseError("tenant_not_found", "Tenant not found")
        return tenant

    def _owned(self, tenant_id: UUID, phone_number_id: UUID) -> TenantPhoneNumber:
        row = self._session.scalar(
            select(TenantPhoneNumber).where(
                TenantPhoneNumber.id == phone_number_id,
                TenantPhoneNumber.tenant_id == tenant_id,
            )
        )
        if row is None:
            raise PurchaseError("not_found", "Phone number not found for tenant")
        return row

    def _store_idempotency(
        self,
        *,
        tenant_id: UUID,
        key: str,
        response: dict[str, Any],
        status: str,
    ) -> None:
        row = TelephonyIdempotencyKey(
            tenant_id=tenant_id,
            operation="purchase_number",
            key=key.strip(),
            response_json=response,
            status=status,
        )
        self._session.add(row)
        self._session.flush()

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
            "provisioning_state": row.provisioning_state,
            "provisioning_details": row.provisioning_details,
            "last_purchase_error": row.last_purchase_error,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

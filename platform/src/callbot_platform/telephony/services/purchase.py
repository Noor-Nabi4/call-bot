"""Path B: purchase Twilio numbers via platform subaccounts."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.config import Settings
from callbot_platform.db.models import (
    Tenant,
    TenantPhoneNumber,
    TenantTwilioSubaccount,
    TelephonyIdempotencyKey,
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
    TwilioApiError,
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

    def ensure_subaccount(self, *, tenant_id: UUID, actor: str = "system") -> dict[str, Any]:
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

        if not self._settings.twilio_account_sid or not self._settings.twilio_auth_token:
            raise PurchaseError(
                "twilio_not_configured",
                "Platform Twilio master credentials are required for Path B",
            )

        friendly = f"call-bot-{tenant.slug}"
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
        account_sid, auth_token = self._tenant_twilio_creds(tenant_id)
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

    def purchase(
        self,
        *,
        tenant_id: UUID,
        phone_number: str,
        confirm: bool,
        idempotency_key: str,
        actor: str = "tenant_user",
    ) -> dict[str, Any]:
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

        tenant = self._require_tenant(tenant_id)
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

        account_sid, auth_token = self._tenant_twilio_creds(tenant_id)
        row = TenantPhoneNumber(
            tenant_id=tenant_id,
            provider=TelephonyProviderId.TWILIO.value,
            e164=e164,
            twilio_account_sid=account_sid,
            connection_status=ConnectionStatus.CONFIGURING.value,
            verification_status=VerificationStatus.UNVERIFIED.value,
            onboarding_path=OnboardingPath.PLATFORM_PURCHASE.value,
            auth_method=AuthMethod.PLATFORM_SUBACCOUNT.value,
            provisioning_state=ProvisioningState.IN_PROGRESS.value,
            provisioning_details={"steps_completed": []},
        )
        self._session.add(row)
        self._session.flush()

        details: dict[str, Any] = {"steps_completed": []}
        phone_sid: str | None = None

        try:
            purchased = self._provisioning.purchase(
                account_sid=account_sid,
                auth_token=auth_token,
                e164=e164,
                idempotency_key=idempotency_key,
            )
            phone_sid = purchased.phone_number_sid
            details["steps_completed"].append("twilio_purchase")
            details["phone_number_sid"] = phone_sid

            domain = self._domain_for_tenant(tenant.slug)
            trunk = self._twilio_sip.create_or_get_twilio_trunk(
                account_sid=account_sid,
                auth_token=auth_token,
                friendly_name=f"call-bot-{tenant.slug}",
                domain_name=domain,
                livekit_origination_uri=self._settings.livekit_origination_uri,
            )
            row.twilio_trunk_sid = trunk.trunk_sid
            details["steps_completed"].append("twilio_trunk")
            details["twilio_trunk_sid"] = trunk.trunk_sid

            self._twilio_sip.associate_number_with_twilio_trunk(
                account_sid=account_sid,
                auth_token=auth_token,
                trunk_sid=trunk.trunk_sid,
                phone_number_sid=phone_sid,
            )
            details["steps_completed"].append("twilio_trunk_association")

            metadata = self._signer.sign_payload(
                {
                    "tenant_id": str(tenant_id),
                    "did": e164,
                    "phone_number_id": str(row.id),
                    "source": "sip_dispatch",
                }
            )
            lk_trunk = self._livekit.create_livekit_inbound_trunk(
                name=f"inbound-{tenant.slug}-{e164}",
                numbers=[e164],
                metadata=metadata,
            )
            row.livekit_inbound_trunk_id = lk_trunk.trunk_id
            details["steps_completed"].append("livekit_inbound_trunk")
            details["livekit_inbound_trunk_id"] = lk_trunk.trunk_id

            dispatch = self._livekit.create_individual_dispatch_rule(
                name=f"dispatch-{tenant.slug}-{e164}",
                agent_name=self._settings.agent_name,
                metadata=metadata,
                trunk_ids=[lk_trunk.trunk_id],
            )
            row.livekit_dispatch_rule_id = dispatch.dispatch_rule_id
            details["steps_completed"].append("livekit_dispatch_rule")
            details["livekit_dispatch_rule_id"] = dispatch.dispatch_rule_id

            row.connection_status = ConnectionStatus.PENDING_VERIFICATION.value
            row.provisioning_state = ProvisioningState.COMPLETE.value
            row.provisioning_details = details
            row.updated_at = datetime.now(UTC)
        except (TwilioApiError, Exception) as exc:
            row.connection_status = ConnectionStatus.PARTIAL.value
            row.provisioning_state = ProvisioningState.PARTIAL.value
            row.last_purchase_error = str(exc)
            details["error"] = str(exc)
            row.provisioning_details = details
            # Safe rollback of LiveKit resources only; never auto-release Twilio number.
            self._safe_rollback_livekit(row, details)
            row.updated_at = datetime.now(UTC)
            response = {
                "error": "partial_provisioning",
                "message": str(exc),
                "phone_number": self._serialize(row),
            }
            self._store_idempotency(
                tenant_id=tenant_id,
                key=idempotency_key,
                response=response,
                status="failed",
            )
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="purchase_partial_failure",
                resource_ids={"phone_number_id": str(row.id), "e164": e164},
                idempotency_key=idempotency_key,
                payload_summary=details,
            )
            self._session.flush()
            raise PurchaseError(
                "partial_provisioning",
                f"Purchase partially completed; number was NOT auto-released. {exc}",
            ) from exc

        response = {"phone_number": self._serialize(row)}
        self._store_idempotency(
            tenant_id=tenant_id,
            key=idempotency_key,
            response=response,
            status="completed",
        )
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="number_purchased",
            resource_ids={
                "phone_number_id": str(row.id),
                "e164": e164,
                "phone_number_sid": phone_sid,
            },
            idempotency_key=idempotency_key,
        )
        self._session.flush()
        return response

    def release(
        self,
        *,
        tenant_id: UUID,
        phone_number_id: UUID,
        phone_number_sid: str,
        actor: str = "tenant_user",
    ) -> dict[str, Any]:
        row = self._owned(tenant_id, phone_number_id)
        if row.onboarding_path != OnboardingPath.PLATFORM_PURCHASE.value:
            raise PurchaseError(
                "release_not_allowed",
                "Only platform-purchased numbers can be released via this API",
            )
        account_sid, auth_token = self._tenant_twilio_creds(tenant_id)
        self._provisioning.release(
            account_sid=account_sid,
            auth_token=auth_token,
            phone_number_sid=phone_number_sid,
        )
        if row.livekit_dispatch_rule_id:
            try:
                self._livekit.delete_dispatch_rule(row.livekit_dispatch_rule_id)
            except Exception:
                pass
        if row.livekit_inbound_trunk_id:
            try:
                self._livekit.delete_livekit_inbound_trunk(row.livekit_inbound_trunk_id)
            except Exception:
                pass
        row.connection_status = ConnectionStatus.RELEASED.value
        row.updated_at = datetime.now(UTC)
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="number_released",
            resource_ids={
                "phone_number_id": str(row.id),
                "e164": row.e164,
                "phone_number_sid": phone_number_sid,
            },
        )
        self._session.flush()
        return self._serialize(row)

    def _safe_rollback_livekit(
        self, row: TenantPhoneNumber, details: dict[str, Any]
    ) -> None:
        if row.livekit_dispatch_rule_id:
            try:
                self._livekit.delete_dispatch_rule(row.livekit_dispatch_rule_id)
                details["rollback"] = details.get("rollback", []) + ["dispatch_rule"]
                row.livekit_dispatch_rule_id = None
            except Exception as exc:
                details["rollback_error_dispatch"] = str(exc)
        if row.livekit_inbound_trunk_id:
            try:
                self._livekit.delete_livekit_inbound_trunk(row.livekit_inbound_trunk_id)
                details["rollback"] = details.get("rollback", []) + ["inbound_trunk"]
                row.livekit_inbound_trunk_id = None
            except Exception as exc:
                details["rollback_error_trunk"] = str(exc)

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
        row = self._session.get(TenantPhoneNumber, phone_number_id)
        if row is None or row.tenant_id != tenant_id:
            raise PurchaseError("not_found", "Phone number not found for tenant")
        return row

    def _domain_for_tenant(self, slug: str) -> str:
        safe = re.sub(r"[^a-z0-9-]", "", slug.lower()) or "tenant"
        digest = hashlib.sha1(slug.encode("utf-8")).hexdigest()[:8]
        return f"callbot-{safe}-{digest}.pstn.twilio.com"

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

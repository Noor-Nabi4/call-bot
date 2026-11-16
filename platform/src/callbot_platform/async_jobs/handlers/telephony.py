"""Telephony provisioning saga handlers (Twilio + LiveKit)."""

from __future__ import annotations

import contextlib
import hashlib
import logging
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.config import Settings, get_settings
from callbot_platform.db.models import (
    Tenant,
    TenantPhoneNumber,
    TenantTwilioSubaccount,
)
from callbot_platform.db.models.async_job import AsyncJob
from callbot_platform.domain.enums import ConnectionStatus, ProvisioningState
from callbot_platform.security.crypto import CredentialCipher
from callbot_platform.security.metadata import MetadataSigner
from callbot_platform.telephony.adapters.livekit_sip import LiveKitSipService
from callbot_platform.telephony.adapters.twilio_adapter import (
    TwilioNumberProvisioningService,
    TwilioSipTrunkService,
)
from callbot_platform.telephony.audit import write_audit

logger = logging.getLogger(__name__)


class TelephonyProvisionHandler:
    """
    Idempotent multi-step telephony provisioner.

    Steps are recorded on TenantPhoneNumber.provisioning_details.steps_completed
    so retries never duplicate Twilio numbers / LiveKit resources when possible.
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        cipher: CredentialCipher | None = None,
        signer: MetadataSigner | None = None,
        provisioning: TwilioNumberProvisioningService | None = None,
        twilio_sip: TwilioSipTrunkService | None = None,
        livekit: LiveKitSipService | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._cipher = cipher
        self._signer = signer
        self._provisioning = provisioning
        self._twilio_sip = twilio_sip
        self._livekit = livekit

    def _deps(
        self,
    ) -> tuple[
        CredentialCipher,
        MetadataSigner,
        TwilioNumberProvisioningService,
        TwilioSipTrunkService,
        LiveKitSipService,
    ]:
        cipher = self._cipher or CredentialCipher(
            self._settings.credentials_encryption_key
        )
        signer = self._signer or MetadataSigner(self._settings.metadata_hmac_secret)
        provisioning = self._provisioning or TwilioNumberProvisioningService()
        twilio_sip = self._twilio_sip or TwilioSipTrunkService()
        livekit = self._livekit or self._build_livekit()
        return cipher, signer, provisioning, twilio_sip, livekit

    def _build_livekit(self) -> LiveKitSipService:
        return LiveKitSipService(
            url=self._settings.livekit_url,
            api_key=self._settings.livekit_api_key,
            api_secret=self._settings.livekit_api_secret,
        )

    def handle_purchase(self, session: Session, job: AsyncJob) -> dict[str, Any]:
        cipher, signer, provisioning, twilio_sip, livekit = self._deps()
        phone_id = UUID(str(job.payload["phone_number_id"]))
        idempotency_key = str(job.payload.get("idempotency_key") or job.idempotency_key)
        row = session.get(TenantPhoneNumber, phone_id)
        if row is None or row.tenant_id != job.tenant_id:
            raise ValueError("phone_number_not_found")
        tenant = session.get(Tenant, job.tenant_id)
        if tenant is None:
            raise ValueError("tenant_not_found")

        details: dict[str, Any] = dict(row.provisioning_details or {})
        steps: list[str] = list(details.get("steps_completed") or [])

        account_sid, auth_token = self._ensure_subaccount(
            session,
            tenant_id=job.tenant_id,
            tenant_slug=tenant.slug,
            cipher=cipher,
            twilio_sip=twilio_sip,
            steps=steps,
            details=details,
        )
        row.twilio_account_sid = account_sid

        if "twilio_purchase" not in steps:
            purchased = provisioning.purchase(
                account_sid=account_sid,
                auth_token=auth_token,
                e164=row.e164,
                idempotency_key=idempotency_key,
            )
            details["phone_number_sid"] = purchased.phone_number_sid
            steps.append("twilio_purchase")
            details["steps_completed"] = steps
            row.provisioning_details = dict(details)
            session.flush()

        phone_sid = str(details.get("phone_number_sid") or "")
        if not phone_sid:
            raise ValueError("missing_phone_number_sid")

        if "twilio_trunk" not in steps:
            domain = self._domain_for_tenant(tenant.slug)
            trunk = twilio_sip.create_or_get_twilio_trunk(
                account_sid=account_sid,
                auth_token=auth_token,
                friendly_name=f"call-bot-{tenant.slug}",
                domain_name=domain,
                livekit_origination_uri=self._settings.livekit_origination_uri,
            )
            row.twilio_trunk_sid = trunk.trunk_sid
            details["twilio_trunk_sid"] = trunk.trunk_sid
            steps.append("twilio_trunk")
            details["steps_completed"] = steps
            row.provisioning_details = dict(details)
            session.flush()

        trunk_sid = row.twilio_trunk_sid or str(details.get("twilio_trunk_sid") or "")
        if "twilio_trunk_association" not in steps:
            twilio_sip.associate_number_with_twilio_trunk(
                account_sid=account_sid,
                auth_token=auth_token,
                trunk_sid=trunk_sid,
                phone_number_sid=phone_sid,
            )
            steps.append("twilio_trunk_association")
            details["steps_completed"] = steps
            row.provisioning_details = dict(details)
            session.flush()

        metadata = signer.sign_payload(
            {
                "tenant_id": str(job.tenant_id),
                "did": row.e164,
                "phone_number_id": str(row.id),
                "source": "sip_dispatch",
                **(
                    {"agent_profile_id": str(tenant.default_agent_profile_id)}
                    if tenant.default_agent_profile_id
                    else {}
                ),
            }
        )

        if "livekit_inbound_trunk" not in steps:
            lk_trunk = livekit.create_livekit_inbound_trunk(
                name=f"inbound-{tenant.slug}-{row.e164}",
                numbers=[row.e164],
                metadata=metadata,
            )
            row.livekit_inbound_trunk_id = lk_trunk.trunk_id
            details["livekit_inbound_trunk_id"] = lk_trunk.trunk_id
            steps.append("livekit_inbound_trunk")
            details["steps_completed"] = steps
            row.provisioning_details = dict(details)
            session.flush()

        if "livekit_dispatch_rule" not in steps:
            trunk_ids = (
                [row.livekit_inbound_trunk_id] if row.livekit_inbound_trunk_id else []
            )
            dispatch = livekit.create_individual_dispatch_rule(
                name=f"dispatch-{tenant.slug}-{row.e164}",
                agent_name=self._settings.agent_name,
                metadata=metadata,
                trunk_ids=trunk_ids,
            )
            row.livekit_dispatch_rule_id = dispatch.dispatch_rule_id
            details["livekit_dispatch_rule_id"] = dispatch.dispatch_rule_id
            steps.append("livekit_dispatch_rule")
            details["steps_completed"] = steps
            row.provisioning_details = dict(details)
            session.flush()

        row.connection_status = ConnectionStatus.PENDING_VERIFICATION.value
        row.provisioning_state = ProvisioningState.COMPLETE.value
        row.provisioning_details = dict(details)
        row.last_purchase_error = None
        row.updated_at = datetime.now(UTC)
        write_audit(
            session,
            tenant_id=job.tenant_id,
            actor="async_job",
            action="number_purchased",
            resource_ids={
                "phone_number_id": str(row.id),
                "e164": row.e164,
                "phone_number_sid": phone_sid,
                "job_id": str(job.id),
            },
            idempotency_key=idempotency_key,
        )
        session.flush()
        return {"phone_number_id": str(row.id), "steps_completed": steps}

    def handle_connect(self, session: Session, job: AsyncJob) -> dict[str, Any]:
        _, signer, _, _, livekit = self._deps()
        phone_id = UUID(str(job.payload["phone_number_id"]))
        row = session.get(TenantPhoneNumber, phone_id)
        if row is None or row.tenant_id != job.tenant_id:
            raise ValueError("phone_number_not_found")
        tenant = session.get(Tenant, job.tenant_id)
        if tenant is None:
            raise ValueError("tenant_not_found")

        details: dict[str, Any] = dict(row.provisioning_details or {})
        steps: list[str] = list(details.get("steps_completed") or [])

        metadata = signer.sign_payload(
            {
                "tenant_id": str(job.tenant_id),
                "did": row.e164,
                "phone_number_id": str(row.id),
                "source": "sip_dispatch",
                **(
                    {"agent_profile_id": str(tenant.default_agent_profile_id)}
                    if tenant.default_agent_profile_id
                    else {}
                ),
            }
        )

        try:
            if "livekit_inbound_trunk" not in steps:
                trunk = livekit.create_livekit_inbound_trunk(
                    name=f"inbound-{tenant.slug}-{row.e164}",
                    numbers=[row.e164],
                    metadata=metadata,
                )
                row.livekit_inbound_trunk_id = trunk.trunk_id
                details["livekit_inbound_trunk_id"] = trunk.trunk_id
                steps.append("livekit_inbound_trunk")
                details["steps_completed"] = list(steps)
                # Fresh dict so SQLAlchemy persists JSON mutations across flushes.
                row.provisioning_details = dict(details)
                session.flush()

            if "livekit_dispatch_rule" not in steps:
                trunk_ids = (
                    [row.livekit_inbound_trunk_id]
                    if row.livekit_inbound_trunk_id
                    else []
                )
                dispatch = livekit.create_individual_dispatch_rule(
                    name=f"dispatch-{tenant.slug}-{row.e164}",
                    agent_name=self._settings.agent_name,
                    metadata=metadata,
                    trunk_ids=trunk_ids,
                    room_prefix="call-",
                )
                row.livekit_dispatch_rule_id = dispatch.dispatch_rule_id
                details["livekit_dispatch_rule_id"] = dispatch.dispatch_rule_id
                steps.append("livekit_dispatch_rule")
                details["steps_completed"] = list(steps)
                row.provisioning_details = dict(details)
                session.flush()

            row.connection_status = ConnectionStatus.PENDING_SETUP.value
            row.provisioning_state = ProvisioningState.COMPLETE.value
            row.provisioning_details = dict(details)
            row.updated_at = datetime.now(UTC)
            write_audit(
                session,
                tenant_id=job.tenant_id,
                actor="async_job",
                action="connect_existing_provisioned",
                resource_ids={"phone_number_id": str(row.id), "e164": row.e164},
            )
            session.flush()
            return {"phone_number_id": str(row.id), "steps_completed": steps}
        except Exception as exc:
            row.connection_status = ConnectionStatus.PARTIAL.value
            row.provisioning_state = ProvisioningState.PARTIAL.value
            details["error"] = str(exc)
            details["steps_completed"] = steps
            row.provisioning_details = dict(details)
            row.updated_at = datetime.now(UTC)
            session.flush()
            raise

    def mark_purchase_partial(
        self, session: Session, *, phone_id: UUID, tenant_id: UUID, error: str
    ) -> None:
        row = session.get(TenantPhoneNumber, phone_id)
        if row is None or row.tenant_id != tenant_id:
            return
        details = dict(row.provisioning_details or {})
        details["error"] = error
        row.connection_status = ConnectionStatus.PARTIAL.value
        row.provisioning_state = ProvisioningState.PARTIAL.value
        row.last_purchase_error = error[:500]
        row.provisioning_details = dict(details)
        row.updated_at = datetime.now(UTC)
        # Best-effort LiveKit rollback only (never release Twilio number).
        livekit = self._livekit or self._build_livekit()
        if row.livekit_dispatch_rule_id:
            with contextlib.suppress(Exception):
                livekit.delete_dispatch_rule(row.livekit_dispatch_rule_id)
                row.livekit_dispatch_rule_id = None
        if row.livekit_inbound_trunk_id:
            with contextlib.suppress(Exception):
                livekit.delete_livekit_inbound_trunk(row.livekit_inbound_trunk_id)
                row.livekit_inbound_trunk_id = None
        session.flush()

    def _ensure_subaccount(
        self,
        session: Session,
        *,
        tenant_id: UUID,
        tenant_slug: str,
        cipher: CredentialCipher,
        twilio_sip: TwilioSipTrunkService,
        steps: list[str],
        details: dict[str, Any],
    ) -> tuple[str, str]:
        existing = session.scalar(
            select(TenantTwilioSubaccount).where(
                TenantTwilioSubaccount.tenant_id == tenant_id
            )
        )
        if existing is not None:
            if "twilio_subaccount" not in steps:
                steps.append("twilio_subaccount")
                details["steps_completed"] = steps
            return existing.twilio_subaccount_sid, cipher.decrypt(
                existing.encrypted_auth_token
            )

        if (
            not self._settings.twilio_account_sid
            or not self._settings.twilio_auth_token
        ):
            raise ValueError("twilio_not_configured")

        friendly = f"call-bot-{tenant_slug}"
        sid, token = twilio_sip.create_subaccount(
            master_account_sid=self._settings.twilio_account_sid,
            master_auth_token=self._settings.twilio_auth_token,
            friendly_name=friendly,
        )
        if not token:
            raise ValueError("subaccount_token_unavailable")
        row = TenantTwilioSubaccount(
            tenant_id=tenant_id,
            twilio_subaccount_sid=sid,
            encrypted_auth_token=cipher.encrypt(token),
            friendly_name=friendly,
        )
        session.add(row)
        steps.append("twilio_subaccount")
        details["steps_completed"] = steps
        details["twilio_subaccount_sid"] = sid
        session.flush()
        return sid, token

    def handle_release(self, session: Session, job: AsyncJob) -> dict[str, Any]:
        """
        Idempotent release: Twilio number + LiveKit resources.

        If Twilio reports the number already gone, treat Twilio step as done
        (crash-after-provider recovery).
        """
        cipher, _, provisioning, _, livekit = self._deps()
        phone_id = UUID(str(job.payload["phone_number_id"]))
        phone_sid = str(job.payload.get("phone_number_sid") or "").strip()
        row = session.get(TenantPhoneNumber, phone_id)
        if row is None or row.tenant_id != job.tenant_id:
            raise ValueError("phone_number_not_found")

        if row.connection_status == ConnectionStatus.RELEASED.value:
            return {"phone_number_id": str(row.id), "already_released": True}

        details: dict[str, Any] = dict(row.provisioning_details or {})
        steps: list[str] = list(details.get("release_steps_completed") or [])
        if not phone_sid:
            phone_sid = str(details.get("phone_number_sid") or "").strip()
        if not phone_sid:
            raise ValueError("missing_phone_number_sid")

        sub = session.scalar(
            select(TenantTwilioSubaccount).where(
                TenantTwilioSubaccount.tenant_id == job.tenant_id
            )
        )
        if sub is None:
            raise ValueError("subaccount_missing")
        account_sid = sub.twilio_subaccount_sid
        auth_token = cipher.decrypt(sub.encrypted_auth_token)

        if "twilio_release" not in steps:
            try:
                provisioning.release(
                    account_sid=account_sid,
                    auth_token=auth_token,
                    phone_number_sid=phone_sid,
                )
            except Exception as exc:
                # Reconciliation: already-released / not-found → success.
                msg = str(exc).lower()
                if (
                    "not found" not in msg
                    and "20404" not in msg
                    and "was not found" not in msg
                ):
                    raise
            steps.append("twilio_release")
            details["release_steps_completed"] = steps
            row.provisioning_details = dict(details)
            session.flush()

        if "livekit_dispatch_deleted" not in steps and row.livekit_dispatch_rule_id:
            with contextlib.suppress(Exception):
                livekit.delete_dispatch_rule(row.livekit_dispatch_rule_id)
            row.livekit_dispatch_rule_id = None
            steps.append("livekit_dispatch_deleted")
            details["release_steps_completed"] = steps
            row.provisioning_details = dict(details)
            session.flush()
        elif "livekit_dispatch_deleted" not in steps:
            steps.append("livekit_dispatch_deleted")

        if "livekit_trunk_deleted" not in steps and row.livekit_inbound_trunk_id:
            with contextlib.suppress(Exception):
                livekit.delete_livekit_inbound_trunk(row.livekit_inbound_trunk_id)
            row.livekit_inbound_trunk_id = None
            steps.append("livekit_trunk_deleted")
            details["release_steps_completed"] = steps
            row.provisioning_details = dict(details)
            session.flush()
        elif "livekit_trunk_deleted" not in steps:
            steps.append("livekit_trunk_deleted")

        row.connection_status = ConnectionStatus.RELEASED.value
        row.provisioning_state = ProvisioningState.COMPLETE.value
        details["release_steps_completed"] = steps
        row.provisioning_details = dict(details)
        row.updated_at = datetime.now(UTC)
        write_audit(
            session,
            tenant_id=job.tenant_id,
            actor="async_job",
            action="number_released",
            resource_ids={
                "phone_number_id": str(row.id),
                "e164": row.e164,
                "phone_number_sid": phone_sid,
                "job_id": str(job.id),
            },
        )
        session.flush()
        return {"phone_number_id": str(row.id), "release_steps_completed": steps}

    def handle_refresh_dispatch(
        self, session: Session, job: AsyncJob
    ) -> dict[str, Any]:
        """Update LiveKit dispatch rule metadata after agent profile assign."""
        _, signer, _, _, livekit = self._deps()
        phone_id = UUID(str(job.payload["phone_number_id"]))
        row = session.get(TenantPhoneNumber, phone_id)
        if row is None or row.tenant_id != job.tenant_id:
            raise ValueError("phone_number_not_found")
        tenant = session.get(Tenant, job.tenant_id)
        if tenant is None:
            raise ValueError("tenant_not_found")
        if not row.livekit_dispatch_rule_id or not row.livekit_inbound_trunk_id:
            return {"skipped": True, "reason": "missing_livekit_resources"}

        agent_profile_id = job.payload.get("agent_profile_id")
        payload: dict[str, Any] = {
            "tenant_id": str(tenant.id),
            "did": row.e164,
            "phone_number_id": str(row.id),
            "source": "sip_dispatch",
        }
        if agent_profile_id:
            payload["agent_profile_id"] = str(agent_profile_id)
        metadata = signer.sign_payload(payload)
        livekit.update_dispatch_rule_agent_metadata(
            dispatch_rule_id=row.livekit_dispatch_rule_id,
            name=f"dispatch-{tenant.slug}-{row.e164}",
            agent_name=self._settings.agent_name,
            metadata=metadata,
            trunk_ids=[row.livekit_inbound_trunk_id],
        )
        write_audit(
            session,
            tenant_id=job.tenant_id,
            actor="async_job",
            action="dispatch_metadata_refreshed",
            resource_ids={
                "phone_number_id": str(row.id),
                "job_id": str(job.id),
            },
        )
        session.flush()
        return {"phone_number_id": str(row.id), "refreshed": True}

    @staticmethod
    def _domain_for_tenant(slug: str) -> str:
        safe = re.sub(r"[^a-z0-9-]", "", slug.lower()) or "tenant"
        digest = hashlib.sha1(slug.encode("utf-8")).hexdigest()[:8]
        return f"callbot-{safe}-{digest}.pstn.twilio.com"

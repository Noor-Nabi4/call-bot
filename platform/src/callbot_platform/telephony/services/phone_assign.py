"""Assign agent profiles to phone numbers; LiveKit refresh via async job."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.async_jobs.service import AsyncJobService
from callbot_platform.async_jobs.types import JobType
from callbot_platform.config import Settings
from callbot_platform.crm.repos.agent_profile_repo import AgentProfileRepository
from callbot_platform.db.models import Tenant, TenantPhoneNumber
from callbot_platform.security.metadata import MetadataSigner
from callbot_platform.telephony.adapters.livekit_sip import LiveKitSipService
from callbot_platform.telephony.audit import write_audit


class PhoneAssignError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class PhoneAssignmentService:
    def __init__(
        self,
        session: Session,
        *,
        signer: MetadataSigner,
        livekit: LiveKitSipService,
        settings: Settings,
    ) -> None:
        self._session = session
        self._signer = signer
        self._livekit = livekit
        self._settings = settings
        self._profiles = AgentProfileRepository(session)

    def assign_profile(
        self,
        tenant_id: UUID,
        phone_number_id: UUID,
        *,
        agent_profile_id: UUID | None,
        actor: str = "tenant_user",
        refresh_dispatch: bool = True,
    ) -> dict[str, Any]:
        phone = self._owned_phone(tenant_id, phone_number_id)
        tenant = self._session.get(Tenant, tenant_id)
        if tenant is None:
            raise PhoneAssignError("tenant_not_found", "Tenant not found")

        if agent_profile_id is not None:
            profile = self._profiles.get(tenant_id, agent_profile_id)
            if profile is None:
                raise PhoneAssignError(
                    "profile_not_found", "Agent profile not found for tenant"
                )
            if profile.get("status") != "active":
                raise PhoneAssignError(
                    "inactive_profile", "Cannot assign an inactive agent profile"
                )
            resolved_id = UUID(profile["id"])
        else:
            resolved_id = None

        phone.agent_profile_id = resolved_id
        phone.updated_at = datetime.now(UTC)
        self._session.flush()

        effective_profile_id = self._profiles.resolve_profile_id(
            tenant_id,
            phone_profile_id=resolved_id,
        )
        job_id = None
        if (
            refresh_dispatch
            and phone.livekit_dispatch_rule_id
            and phone.livekit_inbound_trunk_id
        ):
            job = AsyncJobService(self._session, settings=self._settings).enqueue(
                tenant_id=tenant_id,
                job_type=JobType.TELEPHONY_REFRESH_DISPATCH,
                idempotency_key=(
                    f"tenant:{tenant_id}:phone:{phone.id}:refresh_dispatch:"
                    f"{effective_profile_id or 'none'}"
                ),
                resource_id=str(phone.id),
                payload={
                    "phone_number_id": str(phone.id),
                    "agent_profile_id": str(effective_profile_id)
                    if effective_profile_id
                    else None,
                },
            )
            job_id = str(job.id)

        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="phone_agent_profile_assigned",
            resource_ids={
                "phone_number_id": str(phone.id),
                "agent_profile_id": str(resolved_id) if resolved_id else None,
                "effective_agent_profile_id": str(effective_profile_id)
                if effective_profile_id
                else None,
                "job_id": job_id,
            },
        )
        out = self.serialize_phone(phone, effective_profile_id=effective_profile_id)
        if job_id:
            out["dispatch_refresh_job_id"] = job_id
            out["dispatch_refresh"] = "queued"
        return out

    def serialize_phone(
        self,
        phone: TenantPhoneNumber,
        *,
        effective_profile_id: UUID | None = None,
    ) -> dict[str, Any]:
        if effective_profile_id is None:
            effective_profile_id = self._profiles.resolve_profile_id(
                phone.tenant_id,
                phone_profile_id=phone.agent_profile_id,
            )
        details = phone.provisioning_details or {}
        phone_sid = details.get("phone_number_sid")
        can_release = (
            phone.onboarding_path == "platform_purchase"
            and phone.connection_status not in {"released", "releasing"}
            and isinstance(phone_sid, str)
            and bool(phone_sid.strip())
        )
        return {
            "id": str(phone.id),
            "tenant_id": str(phone.tenant_id),
            "e164": phone.e164,
            "connection_status": phone.connection_status,
            "verification_status": phone.verification_status,
            "onboarding_path": phone.onboarding_path,
            "provisioning_state": phone.provisioning_state,
            "livekit_inbound_trunk_id": phone.livekit_inbound_trunk_id,
            "livekit_dispatch_rule_id": phone.livekit_dispatch_rule_id,
            "agent_profile_id": str(phone.agent_profile_id)
            if phone.agent_profile_id
            else None,
            "effective_agent_profile_id": str(effective_profile_id)
            if effective_profile_id
            else None,
            "is_primary": bool(phone.is_primary),
            "can_release": can_release,
            "created_at": phone.created_at.isoformat() if phone.created_at else None,
            "updated_at": phone.updated_at.isoformat() if phone.updated_at else None,
        }

    def list_phones(self, tenant_id: UUID) -> list[dict[str, Any]]:
        rows = list(
            self._session.scalars(
                select(TenantPhoneNumber).where(
                    TenantPhoneNumber.tenant_id == tenant_id
                )
            )
        )
        return [self.serialize_phone(r) for r in rows]

    def _owned_phone(self, tenant_id: UUID, phone_number_id: UUID) -> TenantPhoneNumber:
        row = self._session.scalar(
            select(TenantPhoneNumber).where(
                TenantPhoneNumber.id == phone_number_id,
                TenantPhoneNumber.tenant_id == tenant_id,
            )
        )
        if row is None:
            raise PhoneAssignError("not_found", "Phone number not found for tenant")
        return row

"""Number verification: mark active only after inbound observation."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.db.models import TenantPhoneNumber
from callbot_platform.domain.enums import ConnectionStatus, VerificationStatus
from callbot_platform.domain.phone import PhoneNumberError, normalize_e164
from callbot_platform.telephony.audit import write_audit


class VerificationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class DbNumberVerificationService:
    def __init__(self, session: Session, *, challenge_ttl_minutes: int = 30) -> None:
        self._session = session
        self._ttl = challenge_ttl_minutes

    def start_verification(
        self, *, tenant_id: UUID, phone_number_id: UUID
    ) -> dict[str, Any]:
        row = self._get_owned(tenant_id, phone_number_id)
        if row.connection_status not in {
            ConnectionStatus.PENDING_VERIFICATION.value,
            ConnectionStatus.CONFIGURING.value,
            ConnectionStatus.PENDING_SETUP.value,
            ConnectionStatus.PARTIAL.value,
        }:
            if row.connection_status == ConnectionStatus.ACTIVE.value:
                raise VerificationError("already_active", "Number is already active")
            raise VerificationError(
                "invalid_status",
                f"Cannot start verification in status={row.connection_status}",
            )
        if not row.livekit_inbound_trunk_id or not row.livekit_dispatch_rule_id:
            raise VerificationError(
                "incomplete_config",
                "LiveKit trunk/dispatch must exist before verification",
            )

        token = secrets.token_urlsafe(24)
        row.verification_token = token
        row.verification_expires_at = datetime.now(UTC) + timedelta(minutes=self._ttl)
        row.verification_status = VerificationStatus.PENDING.value
        row.connection_status = ConnectionStatus.PENDING_VERIFICATION.value
        row.updated_at = datetime.now(UTC)
        self._session.flush()

        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor="system",
            action="verification_started",
            resource_ids={"phone_number_id": str(phone_number_id), "e164": row.e164},
        )
        return {
            "phone_number_id": str(row.id),
            "e164": row.e164,
            "verification_status": row.verification_status,
            "connection_status": row.connection_status,
            "verification_token": token,
            "expires_at": row.verification_expires_at.isoformat(),
            "instructions": (
                f"Place an inbound call to {row.e164} within {self._ttl} minutes. "
                "The platform marks the number active after the call is observed."
            ),
        }

    def observe_inbound(
        self,
        *,
        called_number: str,
        caller_number: str | None,
        livekit_inbound_trunk_id: str | None,
        livekit_room_name: str | None,
        provider_call_id: str | None,
    ) -> dict[str, Any]:
        try:
            did = normalize_e164(called_number)
        except PhoneNumberError as exc:
            raise VerificationError("invalid_did", str(exc)) from exc

        row = self._session.scalar(
            select(TenantPhoneNumber).where(TenantPhoneNumber.e164 == did)
        )
        if row is None:
            return {"matched": False, "reason": "unknown_did", "e164": did}

        expires = row.verification_expires_at
        if expires is not None and expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if (
            row.verification_status == VerificationStatus.PENDING.value
            and expires
            and expires < datetime.now(UTC)
        ):
            row.verification_status = VerificationStatus.FAILED.value
            self._session.flush()
            write_audit(
                self._session,
                tenant_id=row.tenant_id,
                actor="system",
                action="verification_expired",
                resource_ids={"phone_number_id": str(row.id), "e164": did},
            )
            return {"matched": False, "reason": "verification_expired", "e164": did}

        activated = False
        if row.verification_status == VerificationStatus.PENDING.value:
            if (
                livekit_inbound_trunk_id
                and row.livekit_inbound_trunk_id
                and livekit_inbound_trunk_id != row.livekit_inbound_trunk_id
            ):
                return {
                    "matched": False,
                    "reason": "trunk_mismatch",
                    "e164": did,
                }
            row.verification_status = VerificationStatus.VERIFIED.value
            row.connection_status = ConnectionStatus.ACTIVE.value
            row.verification_token = None
            row.verification_expires_at = None
            row.updated_at = datetime.now(UTC)
            activated = True
            write_audit(
                self._session,
                tenant_id=row.tenant_id,
                actor="system",
                action="number_verified_active",
                resource_ids={"phone_number_id": str(row.id), "e164": did},
                payload_summary={
                    "caller_number": caller_number,
                    "livekit_room_name": livekit_room_name,
                    "provider_call_id": provider_call_id,
                },
            )

        write_audit(
            self._session,
            tenant_id=row.tenant_id,
            actor="system",
            action="inbound_observed",
            resource_ids={"phone_number_id": str(row.id), "e164": did},
            payload_summary={
                "caller_number": caller_number,
                "activated": activated,
                "livekit_room_name": livekit_room_name,
                "provider_call_id": provider_call_id,
            },
        )
        self._session.flush()
        return {
            "matched": True,
            "activated": activated,
            "tenant_id": str(row.tenant_id),
            "phone_number_id": str(row.id),
            "e164": did,
            "connection_status": row.connection_status,
            "verification_status": row.verification_status,
        }

    def _get_owned(self, tenant_id: UUID, phone_number_id: UUID) -> TenantPhoneNumber:
        row = self._session.scalar(
            select(TenantPhoneNumber).where(
                TenantPhoneNumber.id == phone_number_id,
                TenantPhoneNumber.tenant_id == tenant_id,
            )
        )
        if row is None:
            raise VerificationError("not_found", "Phone number not found for tenant")
        return row

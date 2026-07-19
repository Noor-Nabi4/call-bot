"""Booking confirmation notifications: Twilio SMS + email outbox."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from callbot_platform.config import Settings, get_settings
from callbot_platform.db.models import (
    Appointment,
    Customer,
    CustomerPhone,
    NotificationOutbox,
    TenantPhoneNumber,
    TenantTwilioSubaccount,
)
from callbot_platform.security.crypto import CredentialCipher

logger = logging.getLogger(__name__)


def _format_local(starts_at: datetime, timezone_name: str) -> str:
    try:
        from zoneinfo import ZoneInfo

        local = starts_at.astimezone(ZoneInfo(timezone_name))
        return local.strftime("%a %b %d at %I:%M %p %Z")
    except Exception:
        return starts_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _confirmation_body(
    *,
    business_name: str,
    confirmation_code: str,
    starts_at: datetime,
    timezone_name: str,
    action: str,
) -> str:
    when = _format_local(starts_at, timezone_name)
    if action == "canceled":
        return (
            f"{business_name}: Your appointment {confirmation_code} on {when} "
            f"has been canceled."
        )
    if action == "rescheduled":
        return (
            f"{business_name}: Your appointment {confirmation_code} was rescheduled "
            f"to {when}."
        )
    return (
        f"{business_name}: Your appointment is confirmed for {when}. "
        f"Confirmation code: {confirmation_code}."
    )


class NotificationService:
    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        sms_sender: Any | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._sms_sender = sms_sender

    def send_appointment_notifications(
        self,
        appointment: Appointment,
        *,
        customer: Customer,
        business_name: str,
        timezone_name: str,
        action: str = "booked",
    ) -> list[dict[str, Any]]:
        body = _confirmation_body(
            business_name=business_name,
            confirmation_code=appointment.confirmation_code,
            starts_at=appointment.starts_at,
            timezone_name=timezone_name,
            action=action,
        )
        results: list[dict[str, Any]] = []

        phone = self._primary_phone(appointment.tenant_id, customer.id)
        if phone:
            results.append(
                self._enqueue_and_maybe_send_sms(
                    tenant_id=appointment.tenant_id,
                    appointment_id=appointment.id,
                    to_address=phone,
                    body=body,
                )
            )
        else:
            results.append(
                {
                    "channel": "sms",
                    "status": "skipped",
                    "reason": "no_customer_phone",
                }
            )

        if customer.email:
            row = NotificationOutbox(
                tenant_id=appointment.tenant_id,
                appointment_id=appointment.id,
                channel="email",
                to_address=customer.email,
                body=body,
                status="pending",
            )
            self._session.add(row)
            self._session.flush()
            results.append(
                {
                    "channel": "email",
                    "status": "pending",
                    "outbox_id": str(row.id),
                }
            )
        else:
            results.append(
                {
                    "channel": "email",
                    "status": "skipped",
                    "reason": "no_customer_email",
                }
            )

        return results

    def _primary_phone(self, tenant_id: UUID, customer_id: UUID) -> str | None:
        from sqlalchemy import select

        row = self._session.scalar(
            select(CustomerPhone)
            .where(
                CustomerPhone.tenant_id == tenant_id,
                CustomerPhone.customer_id == customer_id,
            )
            .limit(1)
        )
        return row.e164 if row else None

    def _enqueue_and_maybe_send_sms(
        self,
        *,
        tenant_id: UUID,
        appointment_id: UUID,
        to_address: str,
        body: str,
    ) -> dict[str, Any]:
        row = NotificationOutbox(
            tenant_id=tenant_id,
            appointment_id=appointment_id,
            channel="sms",
            to_address=to_address,
            body=body,
            status="pending",
        )
        self._session.add(row)
        self._session.flush()

        try:
            sid = self._send_sms(tenant_id=tenant_id, to=to_address, body=body)
        except Exception as exc:
            logger.exception("sms_send_failed", extra={"tenant_id": str(tenant_id)})
            row.status = "failed"
            row.error = str(exc)[:500]
            row.updated_at = datetime.now(UTC)
            self._session.flush()
            return {
                "channel": "sms",
                "status": "failed",
                "outbox_id": str(row.id),
                "error": row.error,
            }

        if sid is None:
            row.status = "skipped"
            row.error = "twilio_not_configured"
            row.updated_at = datetime.now(UTC)
            self._session.flush()
            return {
                "channel": "sms",
                "status": "skipped",
                "outbox_id": str(row.id),
                "reason": "twilio_not_configured",
            }

        row.status = "sent"
        row.provider_ref = sid
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        return {
            "channel": "sms",
            "status": "sent",
            "outbox_id": str(row.id),
            "provider_ref": sid,
        }

    def _send_sms(self, *, tenant_id: UUID, to: str, body: str) -> str | None:
        if self._sms_sender is not None:
            return self._sms_sender(tenant_id=tenant_id, to=to, body=body)

        creds = self._resolve_twilio_creds(tenant_id)
        if creds is None:
            return None
        account_sid, auth_token, from_number = creds
        from twilio.rest import Client

        client = Client(account_sid, auth_token)
        message = client.messages.create(to=to, from_=from_number, body=body)
        return message.sid

    def _resolve_twilio_creds(
        self, tenant_id: UUID
    ) -> tuple[str, str, str] | None:
        from sqlalchemy import select

        settings = self._settings
        from_number: str | None = None
        phone = self._session.scalar(
            select(TenantPhoneNumber)
            .where(
                TenantPhoneNumber.tenant_id == tenant_id,
                TenantPhoneNumber.connection_status.in_(
                    ["active", "connected", "ready"]
                ),
            )
            .limit(1)
        )
        if phone is None:
            phone = self._session.scalar(
                select(TenantPhoneNumber)
                .where(TenantPhoneNumber.tenant_id == tenant_id)
                .limit(1)
            )
        if phone is not None:
            from_number = phone.e164

        sub = self._session.scalar(
            select(TenantTwilioSubaccount).where(
                TenantTwilioSubaccount.tenant_id == tenant_id
            )
        )
        if sub is not None and settings.credentials_encryption_key:
            try:
                cipher = CredentialCipher(settings.credentials_encryption_key)
                token = cipher.decrypt(sub.encrypted_auth_token)
                if from_number:
                    return sub.twilio_subaccount_sid, token, from_number
            except Exception:
                logger.exception("decrypt_subaccount_token_failed")

        if (
            settings.twilio_account_sid
            and settings.twilio_auth_token
            and from_number
        ):
            return (
                settings.twilio_account_sid,
                settings.twilio_auth_token,
                from_number,
            )
        return None

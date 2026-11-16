"""Booking confirmation notifications: enqueue-only outbox (no I/O in TX)."""

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
    """Enqueue SMS/email into notification_outbox. Delivery is worker-only."""

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        sms_sender: Any | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        # Kept for tests that inject senders into the worker path; unused in enqueue.
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
                self.enqueue_sms(
                    tenant_id=appointment.tenant_id,
                    appointment_id=appointment.id,
                    to_address=phone,
                    body=body,
                    idempotency_key=f"sms:{appointment.id}:{action}",
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
            results.append(
                self.enqueue_email(
                    tenant_id=appointment.tenant_id,
                    appointment_id=appointment.id,
                    to_address=customer.email,
                    body=body,
                    idempotency_key=f"email:{appointment.id}:{action}",
                )
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

    def enqueue_sms(
        self,
        *,
        tenant_id: UUID,
        to_address: str,
        body: str,
        appointment_id: UUID | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self._enqueue(
            tenant_id=tenant_id,
            appointment_id=appointment_id,
            channel="sms",
            to_address=to_address,
            body=body,
            idempotency_key=idempotency_key,
        )

    def enqueue_email(
        self,
        *,
        tenant_id: UUID,
        to_address: str,
        body: str,
        appointment_id: UUID | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self._enqueue(
            tenant_id=tenant_id,
            appointment_id=appointment_id,
            channel="email",
            to_address=to_address,
            body=body,
            idempotency_key=idempotency_key,
        )

    def enqueue_webhook(
        self,
        *,
        tenant_id: UUID,
        url: str,
        event: str,
        event_payload: dict[str, Any],
        secret: str | None = None,
        timeout_sec: float = 15.0,
        rule_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self._enqueue(
            tenant_id=tenant_id,
            appointment_id=None,
            channel="webhook",
            to_address=url[:255],
            body=event,
            idempotency_key=idempotency_key,
            payload={
                "url": url,
                "secret": secret,
                "timeout_sec": timeout_sec,
                "event": event,
                "event_payload": event_payload,
                "rule_id": rule_id,
            },
        )

    def _enqueue(
        self,
        *,
        tenant_id: UUID,
        channel: str,
        to_address: str,
        body: str,
        appointment_id: UUID | None,
        idempotency_key: str | None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if idempotency_key:
            from sqlalchemy import select

            existing = self._session.scalar(
                select(NotificationOutbox).where(
                    NotificationOutbox.tenant_id == tenant_id,
                    NotificationOutbox.idempotency_key == idempotency_key,
                )
            )
            if existing is not None:
                return {
                    "channel": channel,
                    "status": existing.status,
                    "outbox_id": str(existing.id),
                    "idempotent": True,
                }

        row = NotificationOutbox(
            tenant_id=tenant_id,
            appointment_id=appointment_id,
            channel=channel,
            to_address=to_address,
            body=body,
            status="pending",
            idempotency_key=idempotency_key,
            payload=payload or {},
            attempt_count=0,
            next_attempt_at=datetime.now(UTC),
        )
        self._session.add(row)
        self._session.flush()
        if row.idempotency_key is None:
            row.idempotency_key = str(row.id)
            self._session.flush()
        return {
            "channel": channel,
            "status": "pending",
            "outbox_id": str(row.id),
        }

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

    def send_sms_now(
        self,
        *,
        tenant_id: UUID,
        to: str,
        body: str,
        idempotency_key: str | None = None,
    ) -> str | None:
        """Synchronous SMS for the outbox worker only — never call from request TX."""
        if self._sms_sender is not None:
            return self._sms_sender(
                tenant_id=tenant_id,
                to=to,
                body=body,
                idempotency_key=idempotency_key,
            )

        creds = self._resolve_twilio_creds(tenant_id)
        if creds is None:
            return None
        account_sid, auth_token, from_number = creds
        from twilio.rest import Client

        client = Client(account_sid, auth_token)
        # Pass Idempotency-Key when available so provider timeouts do not double-send.
        try:
            message = client.messages.create(
                to=to,
                from_=from_number,
                body=body,
                idempotency_key=idempotency_key,
            )
        except TypeError:
            message = client.messages.create(to=to, from_=from_number, body=body)
        return message.sid

    def _resolve_twilio_creds(self, tenant_id: UUID) -> tuple[str, str, str] | None:
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

        if settings.twilio_account_sid and settings.twilio_auth_token and from_number:
            return (
                settings.twilio_account_sid,
                settings.twilio_auth_token,
                from_number,
            )
        return None

"""Twilio inbound SMS webhook authenticity."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.config import Settings, get_settings
from callbot_platform.db.models import TenantPhoneNumber, TenantTwilioSubaccount
from callbot_platform.security.crypto import CredentialCipher

logger = logging.getLogger(__name__)


class SmsWebhookAuthError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def resolve_tenant_by_business_phone(
    session: Session, business_phone_e164: str
) -> tuple[UUID, TenantPhoneNumber]:
    row = session.scalar(
        select(TenantPhoneNumber).where(TenantPhoneNumber.e164 == business_phone_e164)
    )
    if row is None:
        raise SmsWebhookAuthError(
            "unknown_business_number",
            "No tenant mapped to this Twilio To number",
        )
    return row.tenant_id, row


def resolve_auth_token_for_tenant(
    session: Session,
    tenant_id: UUID,
    *,
    settings: Settings | None = None,
) -> str:
    cfg = settings or get_settings()
    sub = session.scalar(
        select(TenantTwilioSubaccount).where(
            TenantTwilioSubaccount.tenant_id == tenant_id
        )
    )
    if sub is not None and cfg.credentials_encryption_key:
        try:
            cipher = CredentialCipher(cfg.credentials_encryption_key)
            return cipher.decrypt(sub.encrypted_auth_token)
        except Exception:
            logger.exception("sms_webhook_token_decrypt_failed tenant_id=%s", tenant_id)
    if cfg.twilio_auth_token:
        return cfg.twilio_auth_token
    raise SmsWebhookAuthError(
        "auth_token_unavailable",
        "Twilio auth token not configured for signature validation",
    )


def validate_twilio_signature(
    *,
    auth_token: str,
    url: str,
    params: dict[str, str],
    signature: str | None,
) -> None:
    if not signature or not signature.strip():
        raise SmsWebhookAuthError("invalid_signature", "Missing X-Twilio-Signature")
    try:
        from twilio.request_validator import RequestValidator
    except ImportError as exc:
        raise SmsWebhookAuthError(
            "validator_unavailable", "Twilio validator not installed"
        ) from exc
    validator = RequestValidator(auth_token)
    if not validator.validate(url, params, signature.strip()):
        raise SmsWebhookAuthError("invalid_signature", "Twilio signature mismatch")

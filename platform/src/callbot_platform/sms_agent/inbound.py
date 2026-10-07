"""Inbound SMS intake: verify, idempotency, identify, orchestrate, reply."""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.config import Settings, get_settings
from callbot_platform.db.models import NotificationOutbox
from callbot_platform.db.models.sms import SmsMessage
from callbot_platform.domain.phone import PhoneNumberError, normalize_e164
from callbot_platform.sms_agent.agent import SmsAgentOrchestrator, identify_customer
from callbot_platform.sms_agent.constants import MAX_BODY_CHARS
from callbot_platform.sms_agent.conversations import SmsConversationService
from callbot_platform.sms_agent.webhook_security import (
    SmsWebhookAuthError,
    resolve_auth_token_for_tenant,
    resolve_tenant_by_business_phone,
    validate_twilio_signature,
)
from callbot_platform.telephony.audit import write_audit

logger = logging.getLogger(__name__)


class InboundSmsService:
    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        skip_signature: bool = False,
        orchestrator: SmsAgentOrchestrator | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._skip_signature = skip_signature
        self._conversations = SmsConversationService(session)
        self._orchestrator = orchestrator or SmsAgentOrchestrator(
            session, settings=self._settings
        )

    def process_twilio_webhook(
        self,
        *,
        form: dict[str, str],
        signature: str | None,
        request_url: str,
    ) -> dict[str, Any]:
        logger.info("sms.webhook.received")
        try:
            to_raw = (form.get("To") or "").strip()
            from_raw = (form.get("From") or "").strip()
            body_raw = form.get("Body") or ""
            provider_sid = (form.get("MessageSid") or form.get("SmsSid") or "").strip()
            if not to_raw or not from_raw or not provider_sid:
                raise SmsWebhookAuthError(
                    "invalid_payload", "Missing To/From/MessageSid"
                )

            business_phone = normalize_e164(to_raw)
            caller_phone = normalize_e164(from_raw)
            body = body_raw.strip()
            if len(body) > MAX_BODY_CHARS:
                body = body[:MAX_BODY_CHARS]

            tenant_id, _phone_row = resolve_tenant_by_business_phone(
                self._session, business_phone
            )

            if not self._skip_signature:
                token = resolve_auth_token_for_tenant(
                    self._session, tenant_id, settings=self._settings
                )
                validate_twilio_signature(
                    auth_token=token,
                    url=request_url,
                    params={k: str(v) for k, v in form.items()},
                    signature=signature,
                )

            # Loop prevention: ignore echoes of our own outbound provider SIDs.
            if self._is_known_outbound(tenant_id, provider_sid):
                logger.info(
                    "sms.webhook.duplicate tenant_id=%s provider_message_id=%s reason=outbound_echo",
                    tenant_id,
                    provider_sid,
                )
                return {"ok": True, "duplicate": True, "reason": "outbound_echo"}

            return self._ingest(
                tenant_id=tenant_id,
                business_phone=business_phone,
                caller_phone=caller_phone,
                body=body,
                provider_sid=provider_sid,
                form=form,
            )
        except PhoneNumberError as exc:
            raise SmsWebhookAuthError("invalid_phone", str(exc)) from exc

    def _is_known_outbound(self, tenant_id: UUID, provider_sid: str) -> bool:
        existing = self._session.scalar(
            select(SmsMessage).where(
                SmsMessage.tenant_id == tenant_id,
                SmsMessage.provider_message_id == provider_sid,
                SmsMessage.direction == "OUTBOUND",
            )
        )
        if existing is not None:
            return True
        outbox = self._session.scalar(
            select(NotificationOutbox).where(
                NotificationOutbox.tenant_id == tenant_id,
                NotificationOutbox.provider_ref == provider_sid,
                NotificationOutbox.channel == "sms",
            )
        )
        return outbox is not None

    def _lock_provider_message(self, tenant_id: UUID, provider_sid: str) -> None:
        """Serialize concurrent webhooks for the same provider MessageSid (PG)."""
        bind = self._session.get_bind()
        if bind is None or bind.dialect.name != "postgresql":
            return
        material = f"{tenant_id}:sms_inbound:{provider_sid}".encode()
        digest = hashlib.sha256(material).digest()
        k1 = int.from_bytes(digest[:4], "big", signed=True)
        k2 = int.from_bytes(digest[4:8], "big", signed=True)
        try:
            self._session.execute(
                text("SELECT pg_advisory_xact_lock(:k1, :k2)"),
                {"k1": k1, "k2": k2},
            )
        except Exception:
            logger.warning(
                "sms_inbound_advisory_lock_failed provider_message_id=%s",
                provider_sid,
                exc_info=True,
            )

    def _ingest(
        self,
        *,
        tenant_id: UUID,
        business_phone: str,
        caller_phone: str,
        body: str,
        provider_sid: str,
        form: dict[str, str],
    ) -> dict[str, Any]:
        # Transaction-scoped lock + unique constraint = one AI execution.
        self._lock_provider_message(tenant_id, provider_sid)

        # Fast-path dedupe (sequential retries / post-lock losers) before AI work.
        existing = self._session.scalar(
            select(SmsMessage).where(
                SmsMessage.tenant_id == tenant_id,
                SmsMessage.provider_message_id == provider_sid,
            )
        )
        if existing is not None:
            logger.info(
                "sms.webhook.duplicate tenant_id=%s provider_message_id=%s status=%s",
                tenant_id,
                provider_sid,
                existing.status,
            )
            return {
                "ok": True,
                "duplicate": True,
                "message_id": str(existing.id),
                "status": existing.status,
            }

        customer = identify_customer(
            self._session, tenant_id=tenant_id, phone_e164=caller_phone
        )
        customer_id = UUID(str(customer["id"])) if customer else None
        conversation = self._conversations.get_or_create(
            tenant_id=tenant_id,
            phone_e164=caller_phone,
            business_phone_e164=business_phone,
            customer_id=customer_id,
        )

        inbound = SmsMessage(
            tenant_id=tenant_id,
            conversation_id=conversation.id,
            customer_id=customer_id,
            provider_message_id=provider_sid,
            direction="INBOUND",
            sender_phone=caller_phone,
            recipient_phone=business_phone,
            body=body,
            status="RECEIVED",
            metadata_json={
                "AccountSid": form.get("AccountSid"),
                "NumMedia": form.get("NumMedia"),
            },
        )
        try:
            with self._session.begin_nested():
                self._session.add(inbound)
                self._session.flush()
        except IntegrityError:
            # Concurrent duplicate — unique (tenant_id, provider_message_id).
            self._session.expire_all()
            raced = self._session.scalar(
                select(SmsMessage).where(
                    SmsMessage.tenant_id == tenant_id,
                    SmsMessage.provider_message_id == provider_sid,
                )
            )
            logger.info(
                "sms.webhook.duplicate tenant_id=%s provider_message_id=%s",
                tenant_id,
                provider_sid,
            )
            return {
                "ok": True,
                "duplicate": True,
                "message_id": str(raced.id) if raced else None,
                "status": raced.status if raced else "PROCESSED",
            }

        # Claim processing under row lock semantics via status transition.
        locked = self._session.scalar(
            select(SmsMessage)
            .where(
                SmsMessage.id == inbound.id,
                SmsMessage.tenant_id == tenant_id,
            )
            .with_for_update()
        )
        assert locked is not None
        if locked.status in {"PROCESSING", "PROCESSED"}:
            logger.info(
                "sms.webhook.duplicate tenant_id=%s message_id=%s status=%s",
                tenant_id,
                locked.id,
                locked.status,
            )
            return {
                "ok": True,
                "duplicate": True,
                "message_id": str(locked.id),
                "status": locked.status,
            }
        locked.status = "PROCESSING"
        conversation.last_message_at = datetime.now(UTC)
        self._session.flush()

        if customer:
            logger.info(
                "sms.customer.identified tenant_id=%s customer_id=%s",
                tenant_id,
                customer_id,
            )
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor="AI_SMS_AGENT",
            action="sms.webhook.received",
            resource_ids={
                "conversation_id": str(conversation.id),
                "message_id": str(locked.id),
                "provider_message_id": provider_sid,
                "customer_id": str(customer_id) if customer_id else None,
            },
            idempotency_key=f"sms_inbound:{tenant_id}:{provider_sid}",
        )

        try:
            result = self._orchestrator.handle_inbound_message(
                conversation=conversation,
                inbound=locked,
                customer=customer,
            )
            locked.status = "PROCESSED"
            self._session.flush()
            return {
                "ok": True,
                "duplicate": False,
                "message_id": str(locked.id),
                "conversation_id": str(conversation.id),
                "intent": result.get("intent"),
                "status": "PROCESSED",
            }
        except Exception as exc:
            locked.status = "FAILED"
            locked.metadata_json = {
                **(locked.metadata_json or {}),
                "error": type(exc).__name__,
            }
            self._session.flush()
            logger.exception(
                "sms.ai.failed tenant_id=%s message_id=%s", tenant_id, locked.id
            )
            # Still acknowledge webhook so Twilio does not storm retries forever;
            # FAILED rows can be investigated / replayed operationally.
            return {
                "ok": True,
                "duplicate": False,
                "message_id": str(locked.id),
                "status": "FAILED",
                "error": "processing_failed",
            }

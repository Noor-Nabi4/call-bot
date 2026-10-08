"""Provider-facing Twilio inbound SMS webhook (Phase 15)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from callbot_platform.api.deps import db_dep, settings_dep
from callbot_platform.config import Settings
from callbot_platform.sms_agent.inbound import InboundSmsService
from callbot_platform.sms_agent.webhook_security import SmsWebhookAuthError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sms-webhooks"])


def _request_url(request: Request) -> str:
    # Twilio signs the full URL as configured in the console (often https public URL).
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get(
        "host"
    )
    if forwarded_proto and forwarded_host:
        return f"{forwarded_proto}://{forwarded_host}{request.url.path}"
    return str(request.url)


@router.post("/webhooks/twilio/sms/inbound")
async def twilio_inbound_sms(
    request: Request,
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
) -> Response:
    form = await request.form()
    params = {str(k): str(v) for k, v in form.items()}
    signature = request.headers.get("X-Twilio-Signature")
    # Production always validates. Tests may pass skip_signature via service directly.
    skip = False
    try:
        result = InboundSmsService(
            session, settings=settings, skip_signature=skip
        ).process_twilio_webhook(
            form=params,
            signature=signature,
            request_url=_request_url(request),
        )
        session.commit()
    except SmsWebhookAuthError as exc:
        session.rollback()
        status = (
            403 if exc.code in {"invalid_signature", "unknown_business_number"} else 400
        )
        logger.warning(
            "sms.webhook.rejected code=%s",
            exc.code,
        )
        raise HTTPException(
            status_code=status,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    except Exception as exc:
        session.rollback()
        logger.exception("sms.webhook.failed")
        raise HTTPException(
            status_code=500,
            detail={"code": "webhook_failed", "message": "SMS webhook failed"},
        ) from exc

    # Twilio expects 2xx; empty TwiML avoids double-sending via Messaging response.
    _ = result
    return Response(content="<Response></Response>", media_type="application/xml")


@router.post("/webhooks/twilio/sms/status")
async def twilio_sms_status(
    request: Request,
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
) -> dict[str, Any]:
    """Delivery status callback — updates outbound sms_messages when present."""
    from sqlalchemy import select

    from callbot_platform.db.models.sms import SmsMessage
    from callbot_platform.domain.phone import PhoneNumberError, normalize_e164
    from callbot_platform.sms_agent.webhook_security import (
        resolve_auth_token_for_tenant,
        resolve_tenant_by_business_phone,
        validate_twilio_signature,
    )

    form = await request.form()
    params = {str(k): str(v) for k, v in form.items()}
    signature = request.headers.get("X-Twilio-Signature")
    message_sid = (params.get("MessageSid") or params.get("SmsSid") or "").strip()
    message_status = (
        (params.get("MessageStatus") or params.get("SmsStatus") or "").strip().lower()
    )
    to_raw = (params.get("From") or params.get("To") or "").strip()
    # Status callbacks use the Twilio number as From for outbound; prefer To (customer)
    # and resolve tenant via AccountSid-linked business number when possible.
    business_raw = (params.get("From") or "").strip()
    if not message_sid:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_payload", "message": "Missing MessageSid"},
        )
    try:
        if business_raw:
            business = normalize_e164(business_raw)
            tenant_id, _ = resolve_tenant_by_business_phone(session, business)
        else:
            raise SmsWebhookAuthError(
                "invalid_payload", "Missing From for tenant resolve"
            )
        token = resolve_auth_token_for_tenant(session, tenant_id, settings=settings)
        validate_twilio_signature(
            auth_token=token,
            url=_request_url(request),
            params=params,
            signature=signature,
        )
        row = session.scalar(
            select(SmsMessage).where(
                SmsMessage.tenant_id == tenant_id,
                SmsMessage.provider_message_id == message_sid,
                SmsMessage.direction == "OUTBOUND",
            )
        )
        if row is None:
            # Also match by outbox provider_ref linkage later filled.
            from callbot_platform.db.models import NotificationOutbox

            outbox = session.scalar(
                select(NotificationOutbox).where(
                    NotificationOutbox.tenant_id == tenant_id,
                    NotificationOutbox.provider_ref == message_sid,
                    NotificationOutbox.channel == "sms",
                )
            )
            if outbox is not None:
                row = session.scalar(
                    select(SmsMessage).where(
                        SmsMessage.tenant_id == tenant_id,
                        SmsMessage.outbox_id == outbox.id,
                    )
                )
                if row is not None and not row.provider_message_id:
                    row.provider_message_id = message_sid
        if row is not None:
            if message_status in {"delivered"}:
                row.status = "DELIVERED"
                logger.info(
                    "sms.outbound.delivered tenant_id=%s message_id=%s",
                    tenant_id,
                    row.id,
                )
            elif message_status in {"sent", "queued", "accepted", "sending"}:
                if row.status not in {"DELIVERED"}:
                    row.status = "SENT"
                    logger.info(
                        "sms.outbound.sent tenant_id=%s message_id=%s",
                        tenant_id,
                        row.id,
                    )
            elif message_status in {"failed", "undelivered"}:
                row.status = "FAILED"
                logger.info(
                    "sms.outbound.failed tenant_id=%s message_id=%s",
                    tenant_id,
                    row.id,
                )
            if row.status in {"SENT", "DELIVERED"}:
                try:
                    from callbot_platform.billing.usage_ledger import ingest_sms_message

                    ingest_sms_message(session, row)
                except Exception:
                    logger.exception(
                        "usage_ledger_sms_ingest_failed message_id=%s", row.id
                    )
            session.commit()
        else:
            session.commit()
        _ = to_raw
        return {"ok": True}
    except (SmsWebhookAuthError, PhoneNumberError) as exc:
        session.rollback()
        code = getattr(exc, "code", "invalid_payload")
        raise HTTPException(
            status_code=403 if code == "invalid_signature" else 400,
            detail={"code": code, "message": str(exc)},
        ) from exc

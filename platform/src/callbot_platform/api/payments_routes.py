"""Customer invoice payment APIs + Stripe webhook (Phase 19)."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from callbot_platform.api.deps import CurrentUser, db_dep, require_entitled_permission
from callbot_platform.config import Settings, get_settings
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.payments import PaymentService
from callbot_platform.crm.payments.webhooks import InvoicePaymentWebhookService
from callbot_platform.rbac.errors import RbacError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["payments"])

_require_read = require_entitled_permission("payments.read")
_require_create = require_entitled_permission("payments.create")
_require_refund = require_entitled_permission("payments.refund")


def _settings_dep() -> Settings:
    return get_settings()


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, RbacError):
        return HTTPException(
            status_code=403, detail={"code": exc.code, "message": str(exc)}
        )
    if isinstance(exc, CrmError):
        status = (
            404 if exc.code == "not_found" or exc.code.endswith("_not_found") else 400
        )
        if exc.code in {
            "idempotency_conflict",
            "payment_conflict",
            "stripe_not_configured",
        }:
            status = 409 if exc.code != "stripe_not_configured" else 503
        if exc.code == "webhook_invalid":
            status = 400
        return HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        )
    return HTTPException(
        status_code=500, detail={"code": "internal", "message": "Internal error"}
    )


def _actor(user: CurrentUser) -> str:
    return user.email or str(user.user_id)


class PaymentLinkBody(BaseModel):
    model_config = {"extra": "forbid"}
    amount: str | None = None
    description: str | None = Field(default=None, max_length=500)


class RefundBody(BaseModel):
    model_config = {"extra": "forbid"}
    amount: str | None = None
    reason: str | None = Field(default=None, max_length=500)


@router.post("/api/admin/crm/invoices/{invoice_id}/payment-link", status_code=201)
def create_payment_link(
    invoice_id: UUID,
    body: PaymentLinkBody,
    user: CurrentUser = Depends(_require_create),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    try:
        payment = PaymentService(session).create_payment_link(
            user.tenant_id,
            invoice_id,
            actor=_actor(user),
            amount=body.amount,
            description=body.description,
            idempotency_key=idempotency_key,
        )
        session.commit()
        return {"payment": payment}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.get("/api/admin/crm/payments")
def list_payments(
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    invoice_id: UUID = Query(...),  # noqa: B008
) -> dict[str, Any]:
    """List Stripe payment records for an invoice."""
    try:
        payments = PaymentService(session).list_for_invoice(user.tenant_id, invoice_id)
        return {"payments": payments}
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/api/admin/crm/payments/{payment_id}")
def get_payment(
    payment_id: UUID,
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        payment = PaymentService(session).get(user.tenant_id, payment_id)
        return {"payment": payment}
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/api/admin/crm/payments/{payment_id}/refund")
def refund_payment(
    payment_id: UUID,
    body: RefundBody,
    user: CurrentUser = Depends(_require_refund),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    try:
        result = PaymentService(session).request_refund(
            user.tenant_id,
            payment_id,
            actor=_actor(user),
            amount=body.amount,
            reason=body.reason,
            idempotency_key=idempotency_key,
        )
        session.commit()
        return result
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.post("/webhooks/stripe/payments")
async def stripe_invoice_payments_webhook(
    request: Request,
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(_settings_dep),  # noqa: B008
) -> dict[str, Any]:
    """Verified Stripe webhook for customer invoice payments (not SaaS billing)."""
    payload = await request.body()
    signature = request.headers.get("Stripe-Signature")
    service = InvoicePaymentWebhookService(session, settings=settings)
    try:
        event = service.construct_event(payload, signature)
        result = service.handle_event(event)
        session.commit()
        return result
    except CrmError as exc:
        session.rollback()
        raise _http(exc) from exc
    except Exception as exc:
        session.rollback()
        logger.exception("Invoice payment Stripe webhook failed")
        raise HTTPException(
            status_code=500,
            detail={"code": "webhook_failed", "message": "Webhook processing failed"},
        ) from exc

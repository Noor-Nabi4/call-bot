"""Admin Invoice CRM APIs (Phase 18)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.api.deps import CurrentUser, db_dep, require_entitled_permission
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.invoices import InvoiceService
from callbot_platform.rbac.errors import RbacError

router = APIRouter(prefix="/api/admin/crm", tags=["invoices"])

_require_read = require_entitled_permission("invoices.read")
_require_create = require_entitled_permission("invoices.create")
_require_update = require_entitled_permission("invoices.update")
_require_send = require_entitled_permission("invoices.send")
_require_void = require_entitled_permission("invoices.void")


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
            "invalid_transition",
            "invoice_immutable",
            "invoice_conflict",
            "idempotency_conflict",
            "payment_conflict",
            "items_required",
        }:
            status = 409
        return HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        )
    if isinstance(exc, IntegrityError):
        return HTTPException(
            status_code=409,
            detail={"code": "conflict", "message": "Conflicting write"},
        )
    return HTTPException(
        status_code=500, detail={"code": "internal", "message": "Internal error"}
    )


def _actor(user: CurrentUser) -> str:
    return user.email or str(user.user_id)


class InvoiceLineBody(BaseModel):
    model_config = {"extra": "forbid"}
    item_type: str
    service_id: UUID | None = None
    product_id: UUID | None = None
    variant_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    quantity: str | int = 1
    unit_price: str | None = None
    discount_amount: str | None = None
    tax_amount: str | None = None
    sort_order: int | None = None


class InvoiceCreateBody(BaseModel):
    model_config = {"extra": "forbid"}
    customer_id: UUID
    items: list[InvoiceLineBody] = Field(min_length=1)
    job_id: UUID | None = None
    order_id: UUID | None = None
    estimate_id: UUID | None = None
    currency: str | None = Field(default=None, max_length=3)
    invoice_discount: str | None = None
    issue_date: datetime | None = None
    due_date: datetime | None = None
    notes: str | None = None
    terms: str | None = None


class InvoiceUpdateBody(BaseModel):
    model_config = {"extra": "forbid"}
    customer_id: UUID | None = None
    job_id: UUID | None = None
    order_id: UUID | None = None
    estimate_id: UUID | None = None
    clear_job: bool = False
    clear_order: bool = False
    clear_estimate: bool = False
    invoice_discount: str | None = None
    issue_date: datetime | None = None
    due_date: datetime | None = None
    notes: str | None = None
    clear_notes: bool = False
    terms: str | None = None
    clear_terms: bool = False
    items: list[InvoiceLineBody] | None = None


class PaymentBody(BaseModel):
    model_config = {"extra": "forbid"}
    amount: str
    payment_id: UUID | None = None
    reference_note: str | None = Field(default=None, max_length=255)


class VoidBody(BaseModel):
    model_config = {"extra": "forbid"}
    reason: str | None = Field(default=None, max_length=500)


@router.get("/invoices")
def list_invoices(
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    customer_id: UUID | None = Query(default=None),  # noqa: B008
    job_id: UUID | None = Query(default=None),  # noqa: B008
    order_id: UUID | None = Query(default=None),  # noqa: B008
    overdue_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
) -> dict[str, Any]:
    try:
        return InvoiceService(session).list(
            user.tenant_id,
            q=q,
            status=status,
            customer_id=customer_id,
            job_id=job_id,
            order_id=order_id,
            overdue_only=overdue_only,
            limit=limit,
            cursor=cursor,
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/invoices", status_code=201)
def create_invoice(
    body: InvoiceCreateBody,
    user: CurrentUser = Depends(_require_create),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    try:
        invoice = InvoiceService(session).create(
            user.tenant_id,
            customer_id=body.customer_id,
            actor=_actor(user),
            items=[i.model_dump() for i in body.items],
            job_id=body.job_id,
            order_id=body.order_id,
            estimate_id=body.estimate_id,
            currency=body.currency,
            invoice_discount=body.invoice_discount,
            issue_date=body.issue_date,
            due_date=body.due_date,
            notes=body.notes,
            terms=body.terms,
            idempotency_key=idempotency_key,
        )
        session.commit()
        return {"invoice": invoice}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.get("/invoices/{invoice_id}")
def get_invoice(
    invoice_id: UUID,
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        invoice = InvoiceService(session).get(user.tenant_id, invoice_id)
        return {"invoice": invoice}
    except Exception as exc:
        raise _http(exc) from exc


@router.patch("/invoices/{invoice_id}")
def update_invoice(
    invoice_id: UUID,
    body: InvoiceUpdateBody,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        invoice = InvoiceService(session).update(
            user.tenant_id,
            invoice_id,
            actor=_actor(user),
            customer_id=body.customer_id,
            job_id=body.job_id,
            order_id=body.order_id,
            estimate_id=body.estimate_id,
            clear_job=body.clear_job,
            clear_order=body.clear_order,
            clear_estimate=body.clear_estimate,
            invoice_discount=body.invoice_discount,
            issue_date=body.issue_date,
            due_date=body.due_date,
            notes=body.notes,
            clear_notes=body.clear_notes,
            terms=body.terms,
            clear_terms=body.clear_terms,
            items=[i.model_dump() for i in body.items] if body.items else None,
        )
        session.commit()
        return {"invoice": invoice}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.post("/invoices/{invoice_id}/send")
def send_invoice(
    invoice_id: UUID,
    user: CurrentUser = Depends(_require_send),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    try:
        invoice = InvoiceService(session).send(
            user.tenant_id,
            invoice_id,
            actor=_actor(user),
            idempotency_key=idempotency_key,
        )
        session.commit()
        return {"invoice": invoice}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.post("/invoices/{invoice_id}/void")
def void_invoice(
    invoice_id: UUID,
    body: VoidBody,
    user: CurrentUser = Depends(_require_void),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    try:
        invoice = InvoiceService(session).void(
            user.tenant_id,
            invoice_id,
            actor=_actor(user),
            reason=body.reason,
            idempotency_key=idempotency_key,
        )
        session.commit()
        return {"invoice": invoice}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.post("/invoices/{invoice_id}/payments")
def record_payment(
    invoice_id: UUID,
    body: PaymentBody,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    try:
        invoice = InvoiceService(session).payments.record_payment(
            user.tenant_id,
            invoice_id,
            amount=body.amount,
            actor=_actor(user),
            payment_id=body.payment_id,
            idempotency_key=idempotency_key,
            reference_note=body.reference_note,
        )
        session.commit()
        return {"invoice": invoice}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.get("/invoices/{invoice_id}/history")
def invoice_history(
    invoice_id: UUID,
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        history = InvoiceService(session).history(user.tenant_id, invoice_id)
        return {"history": history}
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/invoices/{invoice_id}/payments")
def invoice_payments(
    invoice_id: UUID,
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        invoice = InvoiceService(session).get(user.tenant_id, invoice_id)
        return {"payments": invoice.get("payments") or []}
    except Exception as exc:
        raise _http(exc) from exc

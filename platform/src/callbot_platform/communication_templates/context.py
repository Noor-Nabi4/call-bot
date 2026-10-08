"""Server-authoritative template context from event/entity payloads."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.db.models import Customer, CustomerPhone, Tenant
from callbot_platform.db.models.jobs import Job, Technician


def _fmt_money(value: Any) -> str:
    if value is None or value == "":
        return ""
    try:
        from decimal import Decimal

        from callbot_platform.crm.products.normalize import money_to_str

        if isinstance(value, Decimal):
            return money_to_str(value) or str(value)
        return money_to_str(Decimal(str(value))) or str(value)
    except Exception:
        return str(value)


def _fmt_date(dt: datetime | None, timezone_name: str = "UTC") -> str:
    if dt is None:
        return ""
    try:
        from zoneinfo import ZoneInfo

        local = dt.astimezone(ZoneInfo(timezone_name))
        return local.strftime("%a %b %d, %Y")
    except Exception:
        return dt.astimezone(UTC).strftime("%Y-%m-%d")


def _fmt_time(dt: datetime | None, timezone_name: str = "UTC") -> str:
    if dt is None:
        return ""
    try:
        from zoneinfo import ZoneInfo

        local = dt.astimezone(ZoneInfo(timezone_name))
        return local.strftime("%I:%M %p %Z").lstrip("0")
    except Exception:
        return dt.astimezone(UTC).strftime("%H:%M UTC")


def build_template_context(
    session: Session,
    *,
    tenant_id: UUID,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build flat {{path}} context. Only server-derived values — never trust client vars."""
    payload = dict(payload or {})
    ctx: dict[str, Any] = dict.fromkeys((), "")  # start empty; renderer allow-lists

    tenant = session.get(Tenant, tenant_id)
    tz = (tenant.timezone if tenant else None) or "UTC"
    ctx["business.name"] = tenant.name if tenant else "Your service provider"
    ctx["business.phone"] = ""
    ctx["business.email"] = ""
    ctx["business.website"] = ""
    ctx["business.address"] = ""

    customer_id = payload.get("customer_id")
    if customer_id:
        customer = session.scalar(
            select(Customer).where(
                Customer.id == UUID(str(customer_id)),
                Customer.tenant_id == tenant_id,
            )
        )
        if customer is not None:
            first = customer.first_name or (
                customer.name.split(" ")[0] if customer.name else ""
            )
            last = customer.last_name or ""
            ctx["customer.first_name"] = first
            ctx["customer.last_name"] = last
            ctx["customer.full_name"] = customer.name or f"{first} {last}".strip()
            ctx["customer.email"] = customer.email or ""
            phone = session.scalar(
                select(CustomerPhone).where(
                    CustomerPhone.tenant_id == tenant_id,
                    CustomerPhone.customer_id == customer.id,
                )
            )
            ctx["customer.phone"] = phone.e164 if phone else ""

    # Payload overlays for entity fields (already server-authored by publishers).
    ctx["appointment.id"] = str(payload.get("appointment_id") or "")
    ctx["appointment.confirmation_code"] = str(payload.get("confirmation_code") or "")
    ctx["appointment.service"] = str(
        payload.get("service_type") or payload.get("service") or "appointment"
    )
    ctx["appointment.address"] = str(payload.get("address") or "")
    starts = payload.get("starts_at")
    if isinstance(starts, str):
        try:
            starts_dt = datetime.fromisoformat(starts.replace("Z", "+00:00"))
        except ValueError:
            starts_dt = None
    elif isinstance(starts, datetime):
        starts_dt = starts
    else:
        starts_dt = None
    ctx["appointment.date"] = _fmt_date(starts_dt, tz)
    ctx["appointment.time"] = _fmt_time(starts_dt, tz)

    ctx["job.id"] = str(payload.get("job_id") or "")
    ctx["job.number"] = str(payload.get("job_number") or "")
    ctx["job.status"] = str(payload.get("job_status") or "")
    ctx["job.service"] = str(
        payload.get("job_service") or payload.get("service_type") or "service"
    )

    tech_id = payload.get("technician_id")
    if tech_id:
        tech = session.scalar(
            select(Technician).where(
                Technician.id == UUID(str(tech_id)),
                Technician.tenant_id == tenant_id,
            )
        )
        if tech is not None:
            ctx["technician.name"] = tech.display_name or ""
            ctx["technician.phone"] = tech.phone or ""
    else:
        ctx["technician.name"] = str(payload.get("technician_name") or "")
        ctx["technician.phone"] = str(payload.get("technician_phone") or "")

    ctx["invoice.number"] = str(payload.get("invoice_number") or "")
    ctx["invoice.total"] = _fmt_money(
        payload.get("invoice_total") or payload.get("total")
    )
    ctx["invoice.balance_due"] = _fmt_money(
        payload.get("balance_due") or payload.get("invoice_balance_due")
    )
    ctx["invoice.due_date"] = str(payload.get("due_date") or "")
    # URLs must come from server publishers — never invent from template editor.
    ctx["invoice.payment_url"] = str(payload.get("payment_url") or "")

    ctx["estimate.number"] = str(payload.get("estimate_number") or "")
    ctx["estimate.total"] = _fmt_money(payload.get("estimate_total"))
    ctx["estimate.status"] = str(payload.get("estimate_status") or "")
    ctx["estimate.approval_url"] = str(payload.get("approval_url") or "")

    ctx["payment.amount"] = _fmt_money(
        payload.get("payment_amount") or payload.get("amount")
    )
    ctx["payment.date"] = str(payload.get("payment_date") or "")
    ctx["payment.status"] = str(payload.get("payment_status") or "")
    ctx["payment.receipt_url"] = str(payload.get("receipt_url") or "")

    ctx["review.url"] = str(payload.get("review_url") or "")

    # Enrich from Job row when only job_id present
    job_id = payload.get("job_id")
    if job_id and not ctx.get("job.number"):
        job = session.scalar(
            select(Job).where(Job.id == UUID(str(job_id)), Job.tenant_id == tenant_id)
        )
        if job is not None:
            ctx["job.number"] = job.job_number or ""
            ctx["job.status"] = job.status or ""
            ctx["job.service"] = job.service_type or ctx["job.service"]

    return ctx


def preview_context() -> dict[str, Any]:
    """Safe synthetic context for admin preview — never used for delivery."""
    return {
        "customer.first_name": "Alex",
        "customer.last_name": "Rivera",
        "customer.full_name": "Alex Rivera",
        "customer.phone": "+15551234567",
        "customer.email": "alex@example.com",
        "appointment.id": "preview",
        "appointment.date": "Mon Oct 12, 2026",
        "appointment.time": "10:00 AM UTC",
        "appointment.service": "HVAC tune-up",
        "appointment.address": "123 Main St",
        "appointment.confirmation_code": "ABC123",
        "job.id": "preview",
        "job.number": "JOB-1001",
        "job.status": "COMPLETED",
        "job.service": "HVAC tune-up",
        "technician.name": "Jordan Lee",
        "technician.phone": "+15557654321",
        "invoice.number": "INV-1001",
        "invoice.total": "250.00",
        "invoice.balance_due": "250.00",
        "invoice.due_date": "2026-10-20",
        "invoice.payment_url": "https://example.com/pay/preview",
        "estimate.number": "EST-1001",
        "estimate.total": "180.00",
        "estimate.status": "SENT",
        "estimate.approval_url": "https://example.com/estimate/preview",
        "payment.amount": "250.00",
        "payment.date": "2026-10-08",
        "payment.status": "SUCCEEDED",
        "payment.receipt_url": "https://example.com/receipt/preview",
        "business.name": "Acme Home Services",
        "business.phone": "+15550001111",
        "business.email": "hello@acme.example",
        "business.website": "https://acme.example",
        "business.address": "1 Business Rd",
        "review.url": "https://example.com/review/preview",
    }

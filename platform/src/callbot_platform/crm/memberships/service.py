"""Membership plans + customer memberships (Phase 20, Option A billing)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from callbot_platform.config import Settings, get_settings
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.invoices import InvoiceService
from callbot_platform.crm.memberships.constants import (
    DEFAULT_CANCEL_AT_PERIOD_END,
    OPEN_MEMBERSHIP_STATUSES,
    PLAN_CHANGE_EFFECTIVE,
    PLAN_SUBSCRIBABLE,
    BillingInterval,
    BillingPeriodStatus,
    DiscountType,
    MembershipEvent,
    MembershipStatus,
    PlanStatus,
)
from callbot_platform.crm.memberships.entitlements import MembershipEntitlementService
from callbot_platform.crm.memberships.fingerprint import (
    plan_change_fingerprint,
    subscribe_fingerprint,
)
from callbot_platform.crm.memberships.money import (
    money_or_zero,
    normalize_currency,
    require_money,
    serialize_money,
)
from callbot_platform.crm.memberships.periods import period_end_for
from callbot_platform.crm.memberships.serialize import (
    serialize_billing_period,
    serialize_history,
    serialize_membership,
    serialize_plan,
)
from callbot_platform.crm.payments import PaymentService
from callbot_platform.db.models import Customer
from callbot_platform.db.models.invoices import Invoice
from callbot_platform.db.models.memberships import (
    CustomerMembership,
    MembershipBillingPeriod,
    MembershipHistory,
    MembershipPlan,
    MembershipPlanService,
)
from callbot_platform.db.models.services.service import Service
from callbot_platform.scheduling.notifications import NotificationService
from callbot_platform.telephony.audit import write_audit

logger = logging.getLogger(__name__)

_MONEY_ZERO = Decimal("0.0000")


class MembershipService:
    """
    Application-managed memberships.

    Billing: InvoiceService + PaymentService Checkout (not Stripe Subscriptions).
    Plan changes: effective at next period (no proration).
    Cancel: cancel_at_period_end by default (entitlements until period end).
    """

    def __init__(self, session: Session, *, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self.entitlements = MembershipEntitlementService(session)

    # --- loaders ---

    def _require_customer(self, tenant_id: UUID, customer_id: UUID) -> Customer:
        row = self._session.scalar(
            select(Customer).where(
                Customer.id == customer_id, Customer.tenant_id == tenant_id
            )
        )
        if row is None:
            raise CrmError("customer_not_found", "Customer not found for tenant")
        return row

    def _load_plan(
        self,
        tenant_id: UUID,
        plan_id: UUID,
        *,
        for_update: bool = False,
        include_services: bool = True,
    ) -> MembershipPlan:
        q = select(MembershipPlan).where(
            MembershipPlan.id == plan_id, MembershipPlan.tenant_id == tenant_id
        )
        if for_update:
            q = q.with_for_update()
        if include_services:
            q = q.options(selectinload(MembershipPlan.included_services))
        row = self._session.scalar(q)
        if row is None:
            raise CrmError("not_found", "Membership plan not found for tenant")
        return row

    def _load_membership(
        self,
        tenant_id: UUID,
        membership_id: UUID,
        *,
        for_update: bool = False,
    ) -> CustomerMembership:
        q = select(CustomerMembership).where(
            CustomerMembership.id == membership_id,
            CustomerMembership.tenant_id == tenant_id,
        )
        if for_update:
            q = q.with_for_update()
        row = self._session.scalar(q)
        if row is None:
            raise CrmError("not_found", "Membership not found for tenant")
        return row

    def _require_service(self, tenant_id: UUID, service_id: UUID) -> Service:
        row = self._session.scalar(
            select(Service).where(
                Service.id == service_id, Service.tenant_id == tenant_id
            )
        )
        if row is None:
            raise CrmError("service_not_found", "Service not found for tenant")
        return row

    def _append_history(
        self,
        membership: CustomerMembership,
        *,
        event_type: str,
        actor: str,
        from_status: str | None = None,
        to_status: str | None = None,
        from_plan_id: UUID | None = None,
        to_plan_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
        actor_type: str = "user",
    ) -> None:
        self._session.add(
            MembershipHistory(
                tenant_id=membership.tenant_id,
                membership_id=membership.id,
                customer_id=membership.customer_id,
                event_type=event_type,
                from_plan_id=from_plan_id or membership.plan_id,
                to_plan_id=to_plan_id or membership.plan_id,
                from_status=from_status,
                to_status=to_status,
                effective_at=datetime.now(UTC),
                actor_type=actor_type,
                actor_id=actor,
                metadata_json=metadata or {},
            )
        )

    def _validate_discount(
        self, discount_type: str | None, discount_value: object | None
    ) -> tuple[str | None, Decimal | None]:
        if discount_type is None and discount_value is None:
            return None, None
        if discount_type is None or discount_value is None:
            raise CrmError(
                "invalid_discount",
                "discount_type and discount_value must be set together",
            )
        dtype = discount_type.strip().upper()
        if dtype not in {
            DiscountType.PERCENTAGE.value,
            DiscountType.FIXED_AMOUNT.value,
        }:
            raise CrmError("invalid_discount", "Unsupported discount_type")
        value = require_money(discount_value, field="discount_value")
        if value < 0:
            raise CrmError("invalid_discount", "discount_value must be non-negative")
        if dtype == DiscountType.PERCENTAGE.value and value > Decimal("100"):
            raise CrmError("invalid_discount", "percentage discount cannot exceed 100")
        return dtype, value

    def _price_for_interval(self, plan: MembershipPlan, interval: str) -> Decimal:
        if interval == BillingInterval.MONTHLY.value:
            price = plan.monthly_price
        elif interval == BillingInterval.ANNUAL.value:
            price = plan.annual_price
        else:
            raise CrmError(
                "invalid_billing_interval", "billing_interval must be MONTHLY or ANNUAL"
            )
        if price is None or price <= 0:
            raise CrmError(
                "plan_price_invalid",
                f"Plan has no positive {interval.lower()} price",
            )
        return price

    # --- plans ---

    def get_plan(self, tenant_id: UUID, plan_id: UUID) -> dict[str, Any]:
        return serialize_plan(self._load_plan(tenant_id, plan_id))

    def list_plans(
        self,
        tenant_id: UUID,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        q = select(MembershipPlan).where(MembershipPlan.tenant_id == tenant_id)
        if status:
            q = q.where(MembershipPlan.status == status.strip().upper())
        q = (
            q.options(selectinload(MembershipPlan.included_services))
            .order_by(MembershipPlan.created_at.desc())
            .offset(max(0, offset))
            .limit(min(max(1, limit), 100))
        )
        rows = self._session.scalars(q).all()
        return {"plans": [serialize_plan(r) for r in rows]}

    def create_plan(
        self,
        tenant_id: UUID,
        *,
        actor: str,
        name: str,
        monthly_price: object = "0",
        annual_price: object = "0",
        currency: str | None = None,
        description: str | None = None,
        priority_scheduling: bool = False,
        discount_type: str | None = None,
        discount_value: object | None = None,
        included_services: list[dict[str, Any]] | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        clean_name = (name or "").strip()
        if not clean_name:
            raise CrmError("invalid_name", "Plan name is required")
        monthly = money_or_zero(monthly_price, field="monthly_price")
        annual = money_or_zero(annual_price, field="annual_price")
        if monthly <= 0 and annual <= 0:
            raise CrmError(
                "invalid_price",
                "At least one of monthly_price or annual_price must be positive",
            )
        dtype, dval = self._validate_discount(discount_type, discount_value)
        cur = normalize_currency(currency)
        initial = (status or PlanStatus.DRAFT.value).strip().upper()
        if initial not in {s.value for s in PlanStatus}:
            raise CrmError("invalid_status", f"Invalid plan status: {initial}")

        plan = MembershipPlan(
            tenant_id=tenant_id,
            name=clean_name[:255],
            description=(
                description.strip() if description and description.strip() else None
            ),
            status=initial,
            monthly_price=monthly,
            annual_price=annual,
            currency=cur,
            priority_scheduling=bool(priority_scheduling),
            discount_type=dtype,
            discount_value=dval,
            metadata_json={},
            created_by=actor,
        )
        try:
            with self._session.begin_nested():
                self._session.add(plan)
                self._session.flush()
        except IntegrityError as exc:
            raise CrmError(
                "plan_name_conflict",
                "A membership plan with this name already exists for the tenant",
            ) from exc

        self._replace_included_services(
            tenant_id, plan, included_services or [], actor=actor
        )
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="membership.plan_created",
            resource_ids={"plan_id": str(plan.id)},
            payload_summary={
                "name": plan.name,
                "monthly_price": serialize_money(monthly),
                "annual_price": serialize_money(annual),
            },
        )
        return serialize_plan(self._load_plan(tenant_id, plan.id))

    def update_plan(
        self,
        tenant_id: UUID,
        plan_id: UUID,
        *,
        actor: str,
        name: str | None = None,
        description: str | None = None,
        monthly_price: object | None = None,
        annual_price: object | None = None,
        currency: str | None = None,
        priority_scheduling: bool | None = None,
        discount_type: object = ...,
        discount_value: object = ...,
        included_services: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        plan = self._load_plan(tenant_id, plan_id, for_update=True)
        if plan.status == PlanStatus.ARCHIVED.value:
            raise CrmError("plan_archived", "Archived plans cannot be edited")

        if name is not None:
            clean = name.strip()
            if not clean:
                raise CrmError("invalid_name", "Plan name is required")
            plan.name = clean[:255]
        if description is not None:
            plan.description = description.strip() or None
        if monthly_price is not None:
            plan.monthly_price = money_or_zero(monthly_price, field="monthly_price")
        if annual_price is not None:
            plan.annual_price = money_or_zero(annual_price, field="annual_price")
        if plan.monthly_price <= 0 and plan.annual_price <= 0:
            raise CrmError(
                "invalid_price",
                "At least one of monthly_price or annual_price must be positive",
            )
        if currency is not None:
            plan.currency = normalize_currency(currency)
        if priority_scheduling is not None:
            plan.priority_scheduling = bool(priority_scheduling)
        if discount_type is not ... or discount_value is not ...:
            dt = plan.discount_type if discount_type is ... else discount_type
            dv = plan.discount_value if discount_value is ... else discount_value
            if dt is None or dt == "":
                plan.discount_type, plan.discount_value = None, None
            else:
                plan.discount_type, plan.discount_value = self._validate_discount(
                    str(dt) if dt is not None else None, dv
                )
        plan.updated_at = datetime.now(UTC)
        if included_services is not None:
            self._replace_included_services(
                tenant_id, plan, included_services, actor=actor
            )
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise CrmError(
                "plan_name_conflict",
                "A membership plan with this name already exists for the tenant",
            ) from exc
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="membership.plan_updated",
            resource_ids={"plan_id": str(plan.id)},
        )
        return serialize_plan(self._load_plan(tenant_id, plan.id))

    def _replace_included_services(
        self,
        tenant_id: UUID,
        plan: MembershipPlan,
        items: list[dict[str, Any]],
        *,
        actor: str,
    ) -> None:
        for existing in list(plan.included_services or []):
            self._session.delete(existing)
        self._session.flush()
        seen: set[UUID] = set()
        for raw in items:
            sid = raw.get("service_id")
            if sid is None:
                raise CrmError(
                    "service_required", "included service requires service_id"
                )
            service_id = UUID(str(sid))
            if service_id in seen:
                raise CrmError("duplicate_service", "Duplicate included service")
            seen.add(service_id)
            self._require_service(tenant_id, service_id)
            qty = int(raw.get("included_quantity") or 1)
            if qty <= 0:
                raise CrmError("invalid_quantity", "included_quantity must be positive")
            self._session.add(
                MembershipPlanService(
                    tenant_id=tenant_id,
                    plan_id=plan.id,
                    service_id=service_id,
                    included_quantity=qty,
                )
            )
        self._session.flush()
        _ = actor

    def activate_plan(
        self, tenant_id: UUID, plan_id: UUID, *, actor: str
    ) -> dict[str, Any]:
        plan = self._load_plan(tenant_id, plan_id, for_update=True)
        if plan.status == PlanStatus.ARCHIVED.value:
            raise CrmError("plan_archived", "Cannot activate an archived plan")
        plan.status = PlanStatus.ACTIVE.value
        plan.archived_at = None
        plan.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="membership.plan_activated",
            resource_ids={"plan_id": str(plan.id)},
        )
        return serialize_plan(plan)

    def deactivate_plan(
        self, tenant_id: UUID, plan_id: UUID, *, actor: str
    ) -> dict[str, Any]:
        plan = self._load_plan(tenant_id, plan_id, for_update=True)
        if plan.status == PlanStatus.ARCHIVED.value:
            raise CrmError("plan_archived", "Plan is already archived")
        plan.status = PlanStatus.INACTIVE.value
        plan.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="membership.plan_deactivated",
            resource_ids={"plan_id": str(plan.id)},
        )
        return serialize_plan(plan)

    def archive_plan(
        self, tenant_id: UUID, plan_id: UUID, *, actor: str
    ) -> dict[str, Any]:
        plan = self._load_plan(tenant_id, plan_id, for_update=True)
        plan.status = PlanStatus.ARCHIVED.value
        plan.archived_at = datetime.now(UTC)
        plan.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="membership.plan_archived",
            resource_ids={"plan_id": str(plan.id)},
        )
        return serialize_plan(plan)

    # --- memberships ---

    def get_membership(
        self, tenant_id: UUID, membership_id: UUID, *, include_history: bool = False
    ) -> dict[str, Any]:
        row = self._load_membership(tenant_id, membership_id)
        plan = self._load_plan(tenant_id, row.plan_id)
        history = None
        if include_history:
            history = list(
                self._session.scalars(
                    select(MembershipHistory)
                    .where(
                        MembershipHistory.tenant_id == tenant_id,
                        MembershipHistory.membership_id == membership_id,
                    )
                    .order_by(MembershipHistory.created_at.asc())
                ).all()
            )
        return serialize_membership(
            row, plan=plan, include_history=include_history, history=history
        )

    def list_memberships(
        self,
        tenant_id: UUID,
        *,
        customer_id: UUID | None = None,
        plan_id: UUID | None = None,
        status: str | None = None,
        billing_interval: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        q = select(CustomerMembership).where(CustomerMembership.tenant_id == tenant_id)
        if customer_id is not None:
            q = q.where(CustomerMembership.customer_id == customer_id)
        if plan_id is not None:
            q = q.where(CustomerMembership.plan_id == plan_id)
        if status:
            q = q.where(CustomerMembership.status == status.strip().upper())
        if billing_interval:
            q = q.where(
                CustomerMembership.billing_interval == billing_interval.strip().upper()
            )
        rows = self._session.scalars(
            q.order_by(CustomerMembership.created_at.desc())
            .offset(max(0, offset))
            .limit(min(max(1, limit), 100))
        ).all()
        return {"memberships": [serialize_membership(r) for r in rows]}

    def get_customer_membership(
        self, tenant_id: UUID, customer_id: UUID
    ) -> dict[str, Any] | None:
        self._require_customer(tenant_id, customer_id)
        row = self._session.scalar(
            select(CustomerMembership)
            .where(
                CustomerMembership.tenant_id == tenant_id,
                CustomerMembership.customer_id == customer_id,
                CustomerMembership.status.in_(tuple(OPEN_MEMBERSHIP_STATUSES)),
            )
            .order_by(CustomerMembership.created_at.desc())
            .limit(1)
        )
        if row is None:
            return None
        plan = self._load_plan(tenant_id, row.plan_id)
        return serialize_membership(row, plan=plan)

    def subscribe(
        self,
        tenant_id: UUID,
        *,
        customer_id: UUID,
        plan_id: UUID,
        billing_interval: str,
        actor: str,
        idempotency_key: str | None = None,
        create_payment_link: bool = True,
    ) -> dict[str, Any]:
        customer = self._require_customer(tenant_id, customer_id)
        plan = self._load_plan(tenant_id, plan_id)
        if plan.status not in PLAN_SUBSCRIBABLE:
            raise CrmError(
                "plan_not_active",
                "Only ACTIVE plans can be subscribed",
            )
        interval = billing_interval.strip().upper()
        if interval not in {
            BillingInterval.MONTHLY.value,
            BillingInterval.ANNUAL.value,
        }:
            raise CrmError(
                "invalid_billing_interval",
                "billing_interval must be MONTHLY or ANNUAL",
            )
        price = self._price_for_interval(plan, interval)
        key = idempotency_key.strip() if idempotency_key else None
        req_hash = subscribe_fingerprint(
            customer_id=customer.id, plan_id=plan.id, billing_interval=interval
        )

        if key:
            existing = self._session.scalar(
                select(CustomerMembership).where(
                    CustomerMembership.tenant_id == tenant_id,
                    CustomerMembership.idempotency_key == key,
                )
            )
            if existing is not None:
                if (
                    existing.idempotency_request_hash
                    and existing.idempotency_request_hash != req_hash
                ):
                    raise CrmError(
                        "idempotency_conflict",
                        "Idempotency-Key reused with a different subscribe payload",
                    )
                return self._subscribe_result(tenant_id, existing.id)

        open_existing = self._session.scalar(
            select(CustomerMembership).where(
                CustomerMembership.tenant_id == tenant_id,
                CustomerMembership.customer_id == customer.id,
                CustomerMembership.status.in_(tuple(OPEN_MEMBERSHIP_STATUSES)),
            )
        )
        if open_existing is not None:
            raise CrmError(
                "membership_already_active",
                "Customer already has an open membership",
            )

        now = datetime.now(UTC)
        period_end = period_end_for(now, interval)
        membership = CustomerMembership(
            tenant_id=tenant_id,
            customer_id=customer.id,
            plan_id=plan.id,
            billing_interval=interval,
            status=MembershipStatus.PENDING.value,
            current_period_start=now,
            current_period_end=period_end,
            cancel_at_period_end=False,
            idempotency_key=key,
            idempotency_request_hash=req_hash if key else None,
            metadata_json={},
            created_by=actor,
        )
        try:
            with self._session.begin_nested():
                self._session.add(membership)
                self._session.flush()
        except IntegrityError as exc:
            if key:
                raced = self._session.scalar(
                    select(CustomerMembership).where(
                        CustomerMembership.tenant_id == tenant_id,
                        CustomerMembership.idempotency_key == key,
                    )
                )
                if raced is not None:
                    if (
                        raced.idempotency_request_hash
                        and raced.idempotency_request_hash != req_hash
                    ):
                        raise CrmError(
                            "idempotency_conflict",
                            "Idempotency-Key reused with a different subscribe payload",
                        ) from exc
                    return self._subscribe_result(tenant_id, raced.id)
            raise CrmError(
                "membership_already_active",
                "Customer already has an open membership",
            ) from exc

        self._append_history(
            membership,
            event_type=MembershipEvent.SUBSCRIBED.value,
            actor=actor,
            from_status=None,
            to_status=MembershipStatus.PENDING.value,
            to_plan_id=plan.id,
            metadata={"billing_interval": interval},
        )

        billing = self._create_billing_period(
            tenant_id,
            membership,
            plan=plan,
            period_start=now,
            period_end=period_end,
            amount=price,
            actor=actor,
            purpose="subscribe",
        )
        payment_link = None
        if create_payment_link and price > 0 and billing.get("invoice_id"):
            payment_link = self._maybe_payment_link(
                tenant_id,
                UUID(billing["invoice_id"]),
                actor=actor,
                idempotency_key=f"membership_pay:{membership.id}:{billing['id']}",
            )

        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="membership.created",
            resource_ids={
                "membership_id": str(membership.id),
                "customer_id": str(customer.id),
                "plan_id": str(plan.id),
            },
            idempotency_key=key,
            payload_summary={
                "billing_interval": interval,
                "amount": serialize_money(price),
            },
        )
        logger.info(
            "membership.created tenant_id=%s membership_id=%s customer_id=%s",
            tenant_id,
            membership.id,
            customer.id,
        )
        result = self._subscribe_result(tenant_id, membership.id)
        result["billing_period"] = billing
        if payment_link is not None:
            result["payment"] = payment_link
        return result

    def _subscribe_result(self, tenant_id: UUID, membership_id: UUID) -> dict[str, Any]:
        return self.get_membership(tenant_id, membership_id, include_history=True)

    def _create_billing_period(
        self,
        tenant_id: UUID,
        membership: CustomerMembership,
        *,
        plan: MembershipPlan,
        period_start: datetime,
        period_end: datetime,
        amount: Decimal,
        actor: str,
        purpose: str,
    ) -> dict[str, Any]:
        idem = f"membership_{purpose}:{membership.id}:{period_start.isoformat()}"
        existing = self._session.scalar(
            select(MembershipBillingPeriod).where(
                MembershipBillingPeriod.tenant_id == tenant_id,
                MembershipBillingPeriod.idempotency_key == idem,
            )
        )
        if existing is not None:
            return serialize_billing_period(existing)

        invoice = InvoiceService(self._session).create(
            tenant_id,
            customer_id=membership.customer_id,
            actor=actor,
            currency=plan.currency,
            due_date=period_end,
            notes=f"Membership {plan.name} ({membership.billing_interval})",
            items=[
                {
                    "item_type": "CUSTOM",
                    "name": f"{plan.name} membership ({membership.billing_interval})",
                    "description": f"Period {period_start.date()} - {period_end.date()}",
                    "quantity": 1,
                    "unit_price": serialize_money(amount),
                }
            ],
            idempotency_key=f"inv:{idem}",
        )
        inv_id = UUID(invoice["id"])
        inv_row = self._session.scalar(
            select(Invoice).where(Invoice.id == inv_id, Invoice.tenant_id == tenant_id)
        )
        if inv_row is not None:
            meta = dict(inv_row.metadata_json or {})
            meta.update(
                {
                    "purpose": "membership_billing",
                    "membership_id": str(membership.id),
                    "billing_period_start": period_start.isoformat(),
                }
            )
            inv_row.metadata_json = meta
            self._session.flush()

        InvoiceService(self._session).send(tenant_id, inv_id, actor=actor)

        period = MembershipBillingPeriod(
            tenant_id=tenant_id,
            membership_id=membership.id,
            period_start=period_start,
            period_end=period_end,
            invoice_id=inv_id,
            amount=amount,
            currency=plan.currency,
            status=BillingPeriodStatus.PENDING.value,
            idempotency_key=idem,
        )
        try:
            with self._session.begin_nested():
                self._session.add(period)
                self._session.flush()
        except IntegrityError:
            raced = self._session.scalar(
                select(MembershipBillingPeriod).where(
                    MembershipBillingPeriod.tenant_id == tenant_id,
                    MembershipBillingPeriod.idempotency_key == idem,
                )
            )
            if raced is not None:
                return serialize_billing_period(raced)
            raise

        membership.last_invoice_id = inv_id
        membership.updated_at = datetime.now(UTC)
        self._session.flush()
        return serialize_billing_period(period)

    def _maybe_payment_link(
        self,
        tenant_id: UUID,
        invoice_id: UUID,
        *,
        actor: str,
        idempotency_key: str,
    ) -> dict[str, Any] | None:
        if not self._settings.stripe_secret_key.strip():
            return None
        try:
            return PaymentService(
                self._session, settings=self._settings
            ).create_payment_link(
                tenant_id,
                invoice_id,
                actor=actor,
                idempotency_key=idempotency_key,
                description="Membership billing",
            )
        except CrmError as exc:
            if exc.code == "stripe_not_configured":
                return None
            raise

    def on_invoice_paid(
        self, tenant_id: UUID, invoice_id: UUID, *, actor: str = "system"
    ) -> dict[str, Any] | None:
        """Activate / renew membership when a membership invoice is fully paid."""
        period = self._session.scalar(
            select(MembershipBillingPeriod)
            .where(
                MembershipBillingPeriod.tenant_id == tenant_id,
                MembershipBillingPeriod.invoice_id == invoice_id,
            )
            .with_for_update()
        )
        if period is None:
            return None
        if period.status == BillingPeriodStatus.PAID.value:
            return serialize_billing_period(period)

        membership = self._load_membership(
            tenant_id, period.membership_id, for_update=True
        )
        period.status = BillingPeriodStatus.PAID.value
        period.updated_at = datetime.now(UTC)

        now = datetime.now(UTC)
        if membership.status == MembershipStatus.PENDING.value:
            membership.status = MembershipStatus.ACTIVE.value
            membership.started_at = membership.started_at or now
            self._append_history(
                membership,
                event_type=MembershipEvent.ACTIVATED.value,
                actor=actor,
                from_status=MembershipStatus.PENDING.value,
                to_status=MembershipStatus.ACTIVE.value,
                actor_type="system",
                metadata={"invoice_id": str(invoice_id)},
            )
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="membership.activated",
                resource_ids={
                    "membership_id": str(membership.id),
                    "invoice_id": str(invoice_id),
                },
            )
            self._notify_membership(
                tenant_id,
                membership,
                subject="Membership activated",
                body=(
                    f"Your membership is now active through "
                    f"{membership.current_period_end.date()}."
                ),
                idempotency_key=f"membership_activated:{membership.id}",
            )
        elif membership.status in {
            MembershipStatus.ACTIVE.value,
            MembershipStatus.PAST_DUE.value,
        }:
            from_status = membership.status
            if membership.status == MembershipStatus.PAST_DUE.value:
                membership.status = MembershipStatus.ACTIVE.value
            # Advance entitlement period only after verified payment.
            if period.period_start >= membership.current_period_end or (
                period.period_start == membership.current_period_end
            ):
                membership.current_period_start = period.period_start
                membership.current_period_end = period.period_end
            membership.renewed_at = now
            self._append_history(
                membership,
                event_type=MembershipEvent.RENEWED.value,
                actor=actor,
                from_status=from_status,
                to_status=MembershipStatus.ACTIVE.value,
                actor_type="system",
                metadata={"invoice_id": str(invoice_id)},
            )
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="membership.renewed",
                resource_ids={
                    "membership_id": str(membership.id),
                    "invoice_id": str(invoice_id),
                },
            )

        membership.updated_at = now
        self._session.flush()
        logger.info(
            "membership.invoice_paid tenant_id=%s membership_id=%s invoice_id=%s",
            tenant_id,
            membership.id,
            invoice_id,
        )
        return self.get_membership(tenant_id, membership.id)

    def cancel(
        self,
        tenant_id: UUID,
        membership_id: UUID,
        *,
        actor: str,
        immediate: bool = False,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        membership = self._load_membership(tenant_id, membership_id, for_update=True)
        if membership.status in {
            MembershipStatus.CANCELLED.value,
            MembershipStatus.EXPIRED.value,
        }:
            return self.get_membership(tenant_id, membership_id, include_history=True)

        if membership.status not in OPEN_MEMBERSHIP_STATUSES:
            raise CrmError(
                "invalid_status",
                f"Cannot cancel membership in status {membership.status}",
            )

        # Idempotent cancel-at-period-end re-request.
        if (
            not immediate
            and membership.cancel_at_period_end
            and membership.status == MembershipStatus.ACTIVE.value
        ):
            return self.get_membership(tenant_id, membership_id, include_history=True)

        now = datetime.now(UTC)
        if immediate or not DEFAULT_CANCEL_AT_PERIOD_END:
            from_status = membership.status
            membership.status = MembershipStatus.CANCELLED.value
            membership.cancelled_at = now
            membership.ended_at = now
            membership.cancel_at_period_end = False
            membership.updated_at = now
            self._append_history(
                membership,
                event_type=MembershipEvent.CANCELLED.value,
                actor=actor,
                from_status=from_status,
                to_status=MembershipStatus.CANCELLED.value,
                metadata={"immediate": True, "idempotency_key": idempotency_key},
            )
            action = "membership.cancelled"
        else:
            membership.cancel_at_period_end = True
            membership.cancelled_at = now
            membership.updated_at = now
            self._append_history(
                membership,
                event_type=MembershipEvent.CANCEL_SCHEDULED.value,
                actor=actor,
                from_status=membership.status,
                to_status=membership.status,
                metadata={
                    "cancel_at_period_end": True,
                    "period_end": membership.current_period_end.isoformat(),
                    "idempotency_key": idempotency_key,
                },
            )
            action = "membership.cancel_scheduled"

        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action=action,
            resource_ids={
                "membership_id": str(membership.id),
                "customer_id": str(membership.customer_id),
            },
            idempotency_key=idempotency_key,
        )
        self._notify_membership(
            tenant_id,
            membership,
            subject="Membership cancellation",
            body=(
                "Your membership has been cancelled."
                if membership.status == MembershipStatus.CANCELLED.value
                else (
                    "Your membership will cancel at the end of the current billing "
                    f"period ({membership.current_period_end.date()})."
                )
            ),
            idempotency_key=f"membership_cancel:{membership.id}:{int(immediate)}",
        )
        logger.info(
            "membership.cancelled tenant_id=%s membership_id=%s immediate=%s",
            tenant_id,
            membership.id,
            immediate,
        )
        return self.get_membership(tenant_id, membership_id, include_history=True)

    def renew(
        self,
        tenant_id: UUID,
        membership_id: UUID,
        *,
        actor: str,
        create_payment_link: bool = True,
    ) -> dict[str, Any]:
        """
        Create next-period billing invoice (idempotent per period_start).

        Does not extend the period until the invoice is paid (on_invoice_paid),
        except when applying a scheduled plan change at period boundary after pay.
        Period dates advance when renew is called for an ACTIVE membership that
        is at/near period end — billing period uniqueness prevents double renew.
        """
        membership = self._load_membership(tenant_id, membership_id, for_update=True)
        if membership.cancel_at_period_end:
            raise CrmError(
                "membership_cancel_pending",
                "Membership is scheduled to cancel; cannot renew",
            )
        if membership.status not in {
            MembershipStatus.ACTIVE.value,
            MembershipStatus.PAST_DUE.value,
        }:
            raise CrmError(
                "invalid_status",
                f"Cannot renew membership in status {membership.status}",
            )

        # Apply scheduled plan change at renewal boundary (no proration).
        if membership.pending_plan_id is not None:
            new_plan = self._load_plan(tenant_id, membership.pending_plan_id)
            if new_plan.status not in PLAN_SUBSCRIBABLE:
                raise CrmError("plan_not_active", "Pending plan is not active")
            old_plan_id = membership.plan_id
            membership.plan_id = new_plan.id
            if membership.pending_billing_interval:
                membership.billing_interval = membership.pending_billing_interval
            membership.pending_plan_id = None
            membership.pending_billing_interval = None
            self._append_history(
                membership,
                event_type=MembershipEvent.PLAN_CHANGE_SCHEDULED.value,
                actor=actor,
                from_plan_id=old_plan_id,
                to_plan_id=new_plan.id,
                from_status=membership.status,
                to_status=membership.status,
                metadata={
                    "effective": PLAN_CHANGE_EFFECTIVE,
                    "applied_at_renewal": True,
                },
            )

        plan = self._load_plan(tenant_id, membership.plan_id)
        next_start = membership.current_period_end
        next_end = period_end_for(next_start, membership.billing_interval)
        price = self._price_for_interval(plan, membership.billing_interval)

        billing = self._create_billing_period(
            tenant_id,
            membership,
            plan=plan,
            period_start=next_start,
            period_end=next_end,
            amount=price,
            actor=actor,
            purpose="renew",
        )
        # Period dates advance only after invoice is paid (on_invoice_paid).
        membership.updated_at = datetime.now(UTC)
        self._session.flush()

        payment_link = None
        if create_payment_link and price > 0 and billing.get("invoice_id"):
            payment_link = self._maybe_payment_link(
                tenant_id,
                UUID(billing["invoice_id"]),
                actor=actor,
                idempotency_key=f"membership_pay:{membership.id}:{billing['id']}",
            )

        result = self.get_membership(tenant_id, membership_id, include_history=True)
        result["billing_period"] = billing
        result["next_period_start"] = next_start.isoformat()
        result["next_period_end"] = next_end.isoformat()
        if payment_link is not None:
            result["payment"] = payment_link
        return result

    def schedule_plan_change(
        self,
        tenant_id: UUID,
        membership_id: UUID,
        *,
        target_plan_id: UUID,
        actor: str,
        billing_interval: str | None = None,
        direction: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Schedule upgrade/downgrade at next billing period (no proration)."""
        membership = self._load_membership(tenant_id, membership_id, for_update=True)
        if membership.status not in {
            MembershipStatus.ACTIVE.value,
            MembershipStatus.PAST_DUE.value,
        }:
            raise CrmError(
                "invalid_status",
                f"Cannot change plan in status {membership.status}",
            )
        target = self._load_plan(tenant_id, target_plan_id)
        if target.status not in PLAN_SUBSCRIBABLE:
            raise CrmError("plan_not_active", "Target plan must be ACTIVE")
        if target.id == membership.plan_id and not billing_interval:
            raise CrmError("same_plan", "Membership is already on this plan")

        interval = membership.billing_interval
        if billing_interval:
            interval = billing_interval.strip().upper()
            if interval not in {
                BillingInterval.MONTHLY.value,
                BillingInterval.ANNUAL.value,
            }:
                raise CrmError(
                    "invalid_billing_interval",
                    "billing_interval must be MONTHLY or ANNUAL",
                )
            self._price_for_interval(target, interval)

        key = idempotency_key.strip() if idempotency_key else None
        req_hash = plan_change_fingerprint(
            membership_id=membership.id,
            target_plan_id=target.id,
            billing_interval=interval,
        )
        if key:
            meta = membership.metadata_json or {}
            prev = meta.get("last_plan_change_idempotency")
            if prev and prev.get("key") == key:
                if prev.get("hash") != req_hash:
                    raise CrmError(
                        "idempotency_conflict",
                        "Idempotency-Key reused with a different plan-change payload",
                    )
                return self.get_membership(
                    tenant_id, membership_id, include_history=True
                )

        membership.pending_plan_id = target.id
        membership.pending_billing_interval = interval
        membership.updated_at = datetime.now(UTC)
        if key:
            meta = dict(membership.metadata_json or {})
            meta["last_plan_change_idempotency"] = {"key": key, "hash": req_hash}
            membership.metadata_json = meta

        event = (
            MembershipEvent.UPGRADED.value
            if direction == "upgrade"
            else MembershipEvent.DOWNGRADED.value
        )
        self._append_history(
            membership,
            event_type=MembershipEvent.PLAN_CHANGE_SCHEDULED.value,
            actor=actor,
            from_plan_id=membership.plan_id,
            to_plan_id=target.id,
            from_status=membership.status,
            to_status=membership.status,
            metadata={
                "direction": direction,
                "effective": PLAN_CHANGE_EFFECTIVE,
                "pending_billing_interval": interval,
                "event": event,
            },
        )
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action=f"membership.{direction}_scheduled",
            resource_ids={
                "membership_id": str(membership.id),
                "from_plan_id": str(membership.plan_id),
                "to_plan_id": str(target.id),
            },
            idempotency_key=key,
            payload_summary={"effective": PLAN_CHANGE_EFFECTIVE},
        )
        self._session.flush()
        return self.get_membership(tenant_id, membership_id, include_history=True)

    def upgrade(
        self,
        tenant_id: UUID,
        membership_id: UUID,
        *,
        target_plan_id: UUID,
        actor: str,
        billing_interval: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self.schedule_plan_change(
            tenant_id,
            membership_id,
            target_plan_id=target_plan_id,
            actor=actor,
            billing_interval=billing_interval,
            direction="upgrade",
            idempotency_key=idempotency_key,
        )

    def downgrade(
        self,
        tenant_id: UUID,
        membership_id: UUID,
        *,
        target_plan_id: UUID,
        actor: str,
        billing_interval: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self.schedule_plan_change(
            tenant_id,
            membership_id,
            target_plan_id=target_plan_id,
            actor=actor,
            billing_interval=billing_interval,
            direction="downgrade",
            idempotency_key=idempotency_key,
        )

    def expire_due(
        self, tenant_id: UUID, membership_id: UUID, *, actor: str = "system"
    ) -> dict[str, Any]:
        """Apply period-end cancel / expire (worker or admin)."""
        membership = self._load_membership(tenant_id, membership_id, for_update=True)
        now = datetime.now(UTC)
        if membership.current_period_end > now:
            raise CrmError("period_not_ended", "Current period has not ended")

        if membership.cancel_at_period_end:
            from_status = membership.status
            membership.status = MembershipStatus.CANCELLED.value
            membership.ended_at = now
            membership.updated_at = now
            self._append_history(
                membership,
                event_type=MembershipEvent.CANCELLED.value,
                actor=actor,
                from_status=from_status,
                to_status=MembershipStatus.CANCELLED.value,
                actor_type="system",
            )
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="membership.cancelled",
                resource_ids={"membership_id": str(membership.id)},
            )
        elif membership.status in OPEN_MEMBERSHIP_STATUSES:
            from_status = membership.status
            membership.status = MembershipStatus.EXPIRED.value
            membership.ended_at = now
            membership.updated_at = now
            self._append_history(
                membership,
                event_type=MembershipEvent.EXPIRED.value,
                actor=actor,
                from_status=from_status,
                to_status=MembershipStatus.EXPIRED.value,
                actor_type="system",
            )
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="membership.expired",
                resource_ids={"membership_id": str(membership.id)},
            )
        self._session.flush()
        return self.get_membership(tenant_id, membership_id, include_history=True)

    def history(self, tenant_id: UUID, membership_id: UUID) -> list[dict[str, Any]]:
        self._load_membership(tenant_id, membership_id)
        rows = self._session.scalars(
            select(MembershipHistory)
            .where(
                MembershipHistory.tenant_id == tenant_id,
                MembershipHistory.membership_id == membership_id,
            )
            .order_by(MembershipHistory.created_at.asc())
        ).all()
        return [serialize_history(r) for r in rows]

    def _notify_membership(
        self,
        tenant_id: UUID,
        membership: CustomerMembership,
        *,
        subject: str,
        body: str,
        idempotency_key: str,
    ) -> None:
        from callbot_platform.db.models.crm import CustomerPhone

        customer = self._session.scalar(
            select(Customer).where(
                Customer.id == membership.customer_id,
                Customer.tenant_id == tenant_id,
            )
        )
        if customer is None:
            return
        ns = NotificationService(self._session)
        email_body = f"{subject}\n\n{body}"
        if customer.email:
            try:
                ns.enqueue_email(
                    tenant_id=tenant_id,
                    to_address=customer.email,
                    body=email_body,
                    idempotency_key=f"{idempotency_key}:email",
                )
            except Exception:
                logger.exception(
                    "membership.notify_email_failed tenant_id=%s membership_id=%s",
                    tenant_id,
                    membership.id,
                )
        phone_row = self._session.scalar(
            select(CustomerPhone)
            .where(
                CustomerPhone.tenant_id == tenant_id,
                CustomerPhone.customer_id == customer.id,
            )
            .order_by(CustomerPhone.created_at.asc())
            .limit(1)
        )
        if phone_row is not None and phone_row.e164:
            try:
                ns.enqueue_sms(
                    tenant_id=tenant_id,
                    to_address=phone_row.e164,
                    body=body[:480],
                    idempotency_key=f"{idempotency_key}:sms",
                )
            except Exception:
                logger.exception(
                    "membership.notify_sms_failed tenant_id=%s membership_id=%s",
                    tenant_id,
                    membership.id,
                )

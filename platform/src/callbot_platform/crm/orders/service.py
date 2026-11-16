"""Order CRM facade (Phase 9)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.orders.constants import (
    DEFAULT_ORDER_STATUS,
    EDITABLE_STATUSES,
    OrderStatus,
)
from callbot_platform.crm.orders.fingerprint import order_create_fingerprint
from callbot_platform.crm.orders.money import (
    compute_tax_amount,
    line_subtotal,
    line_total,
    money_or_zero,
    normalize_currency,
    require_money,
)
from callbot_platform.crm.orders.numbering import allocate_order_number
from callbot_platform.crm.orders.search import OrderSearchService
from callbot_platform.crm.orders.serialize import serialize_order
from callbot_platform.crm.orders.transitions import OrderTransitionService
from callbot_platform.db.models import Customer, Product, ProductVariant
from callbot_platform.db.models.orders import Order, OrderItem, OrderStatusHistory
from callbot_platform.telephony.audit import write_audit

_MONEY_ZERO = Decimal("0.0000")


class OrderService:
    """Application service for Orders (RBAC enforced at the route layer)."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self.search = OrderSearchService(session)
        self.transitions = OrderTransitionService(session)

    def _load(
        self,
        tenant_id: UUID,
        order_id: UUID,
        *,
        for_update: bool = False,
        require_active: bool = False,
        include_history: bool = False,
    ) -> Order:
        q = select(Order).where(Order.id == order_id, Order.tenant_id == tenant_id)
        if for_update:
            q = q.with_for_update()
        opts = [selectinload(Order.customer), selectinload(Order.items)]
        if include_history:
            opts.append(selectinload(Order.status_history))
        q = q.options(*opts)
        order = self._session.scalar(q)
        if order is None:
            raise CrmError("not_found", "Order not found for tenant")
        if require_active and order.archived_at is not None:
            raise CrmError("order_archived", "Order is archived")
        return order

    def _require_customer(self, tenant_id: UUID, customer_id: UUID) -> Customer:
        row = self._session.scalar(
            select(Customer).where(
                Customer.id == customer_id, Customer.tenant_id == tenant_id
            )
        )
        if row is None:
            raise CrmError("customer_not_found", "Customer not found for tenant")
        return row

    def _resolve_line(
        self,
        tenant_id: UUID,
        *,
        product_id: UUID,
        variant_id: UUID | None,
        quantity: int,
        unit_price: object | None,
        discount_total: object | None,
        tax_total: object | None,
        sort_order: int,
    ) -> dict[str, Any]:
        if quantity <= 0:
            raise CrmError("invalid_quantity", "Quantity must be positive")

        product = self._session.scalar(
            select(Product).where(
                Product.id == product_id, Product.tenant_id == tenant_id
            )
        )
        if product is None:
            raise CrmError("product_not_found", "Product not found for tenant")
        if product.archived_at is not None:
            raise CrmError("product_archived", "Product is archived")
        if product.status != "ACTIVE":
            raise CrmError("product_inactive", "Product is not active")

        variant: ProductVariant | None = None
        if variant_id is not None:
            variant = self._session.scalar(
                select(ProductVariant).where(
                    ProductVariant.id == variant_id,
                    ProductVariant.tenant_id == tenant_id,
                )
            )
            if variant is None:
                raise CrmError("variant_not_found", "Variant not found for tenant")
            if variant.product_id != product.id:
                raise CrmError(
                    "variant_product_mismatch",
                    "Variant does not belong to the specified product",
                )
            if variant.archived_at is not None:
                raise CrmError("variant_archived", "Variant is archived")
            if variant.status != "ACTIVE":
                raise CrmError("variant_inactive", "Variant is not active")

        if unit_price is not None:
            price = require_money(unit_price, field="unit_price")
        else:
            catalog = (
                variant.price
                if variant is not None and variant.price is not None
                else product.price
            )
            if catalog is None:
                raise CrmError("price_unavailable", "No catalog price for line item")
            price = require_money(catalog, field="unit_price")

        disc = money_or_zero(discount_total, field="discount_total")
        sub = line_subtotal(price, quantity)
        if tax_total is not None:
            tax = money_or_zero(tax_total, field="tax_total")
        else:
            tax = compute_tax_amount(
                taxable=sub - disc,
                tax_rate_percent=product.tax_rate,
            )
        total = line_total(subtotal=sub, discount=disc, tax=tax)

        sku = (
            variant.sku
            if variant is not None
            else (product.sku or product.sku_normalized or "UNKNOWN")
        )
        return {
            "product_id": product.id,
            "variant_id": variant.id if variant else None,
            "sku_snapshot": sku[:64],
            "product_name_snapshot": product.name[:255],
            "variant_name_snapshot": (
                (variant.name or variant.sku)[:255] if variant else None
            ),
            "unit_price": price,
            "quantity": quantity,
            "discount_total": disc,
            "tax_total": tax,
            "line_subtotal": sub,
            "line_total": total,
            "sort_order": sort_order,
        }

    def _apply_totals(
        self,
        order: Order,
        *,
        line_payloads: list[dict[str, Any]],
        order_discount: Decimal,
        shipping_total: Decimal,
    ) -> None:
        subtotal = sum((p["line_subtotal"] for p in line_payloads), _MONEY_ZERO)
        line_discount = sum((p["discount_total"] for p in line_payloads), _MONEY_ZERO)
        tax_total = sum((p["tax_total"] for p in line_payloads), _MONEY_ZERO)
        discount_total = line_discount + order_discount
        if discount_total > subtotal + shipping_total and discount_total > subtotal:
            # Order discount may exceed line subtotal only when shipping offsets —
            # keep strict: order discount cannot push total negative.
            pass
        total = subtotal - discount_total + tax_total + shipping_total
        if total < 0:
            raise CrmError("invalid_total", "Order total cannot be negative")
        order.subtotal = subtotal
        order.discount_total = discount_total
        order.tax_total = tax_total
        order.shipping_total = shipping_total
        order.total = total

    def get(self, tenant_id: UUID, order_id: UUID) -> dict[str, Any]:
        order = self._load(tenant_id, order_id, include_history=True)
        return serialize_order(order, include_history=True)

    def list(self, tenant_id: UUID, **kwargs: Any) -> dict[str, Any]:
        return self.search.search(tenant_id, **kwargs)

    def create(
        self,
        tenant_id: UUID,
        *,
        customer_id: UUID,
        actor: str,
        items: list[dict[str, Any]],
        currency: str | None = None,
        notes: str | None = None,
        shipping_total: object | None = None,
        order_discount: object | None = None,
        shipping_address_snapshot: dict[str, Any] | None = None,
        billing_address_snapshot: dict[str, Any] | None = None,
        fulfillment_location_id: UUID | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        key = idempotency_key.strip() if idempotency_key else None

        if not items:
            raise CrmError("items_required", "Order requires at least one line item")

        customer = self._require_customer(tenant_id, customer_id)
        ship = money_or_zero(shipping_total, field="shipping_total")
        odisc = money_or_zero(order_discount, field="order_discount")
        cur = normalize_currency(currency)
        notes_clean = notes.strip() if notes and notes.strip() else None

        line_payloads: list[dict[str, Any]] = []
        for idx, raw in enumerate(items):
            pid = raw.get("product_id")
            if pid is None:
                raise CrmError("product_required", "Line item requires product_id")
            qty = int(raw.get("quantity") or 0)
            line_payloads.append(
                self._resolve_line(
                    tenant_id,
                    product_id=UUID(str(pid)),
                    variant_id=(
                        UUID(str(raw["variant_id"])) if raw.get("variant_id") else None
                    ),
                    quantity=qty,
                    unit_price=raw.get("unit_price"),
                    discount_total=raw.get("discount_total"),
                    tax_total=raw.get("tax_total"),
                    sort_order=int(raw.get("sort_order") or idx),
                )
            )

        req_hash = order_create_fingerprint(
            customer_id=customer.id,
            currency=cur,
            shipping_total=ship,
            order_discount=odisc,
            fulfillment_location_id=fulfillment_location_id,
            items=items,
            notes=notes_clean,
        )

        if key:
            existing = self._session.scalar(
                select(Order).where(
                    Order.tenant_id == tenant_id,
                    Order.idempotency_key == key,
                )
            )
            if existing is not None:
                if (
                    existing.idempotency_request_hash
                    and existing.idempotency_request_hash != req_hash
                ):
                    raise CrmError(
                        "idempotency_conflict",
                        "Idempotency-Key reused with a different order payload",
                    )
                return serialize_order(
                    self._load(tenant_id, existing.id, include_history=True),
                    include_history=True,
                )

        order_number = allocate_order_number(self._session, tenant_id)
        order = Order(
            tenant_id=tenant_id,
            order_number=order_number,
            customer_id=customer.id,
            status=DEFAULT_ORDER_STATUS,
            currency=cur,
            notes=notes_clean,
            shipping_address_snapshot=shipping_address_snapshot,
            billing_address_snapshot=billing_address_snapshot,
            fulfillment_location_id=fulfillment_location_id,
            idempotency_key=key,
            idempotency_request_hash=req_hash if key else None,
            created_by=actor,
            updated_by=actor,
        )
        self._apply_totals(
            order,
            line_payloads=line_payloads,
            order_discount=odisc,
            shipping_total=ship,
        )
        try:
            with self._session.begin_nested():
                self._session.add(order)
                self._session.flush()
        except IntegrityError as exc:
            if key:
                raced = self._session.scalar(
                    select(Order).where(
                        Order.tenant_id == tenant_id,
                        Order.idempotency_key == key,
                    )
                )
                if raced is not None:
                    if (
                        raced.idempotency_request_hash
                        and raced.idempotency_request_hash != req_hash
                    ):
                        raise CrmError(
                            "idempotency_conflict",
                            "Idempotency-Key reused with a different order payload",
                        ) from exc
                    return serialize_order(
                        self._load(tenant_id, raced.id, include_history=True),
                        include_history=True,
                    )
            raise CrmError("order_conflict", "Could not create order") from exc

        for payload in line_payloads:
            self._session.add(
                OrderItem(
                    tenant_id=tenant_id,
                    order_id=order.id,
                    product_id=payload["product_id"],
                    variant_id=payload["variant_id"],
                    sku_snapshot=payload["sku_snapshot"],
                    product_name_snapshot=payload["product_name_snapshot"],
                    variant_name_snapshot=payload["variant_name_snapshot"],
                    unit_price=payload["unit_price"],
                    quantity=payload["quantity"],
                    discount_total=payload["discount_total"],
                    tax_total=payload["tax_total"],
                    line_subtotal=payload["line_subtotal"],
                    line_total=payload["line_total"],
                    sort_order=payload["sort_order"],
                )
            )

        self._session.add(
            OrderStatusHistory(
                tenant_id=tenant_id,
                order_id=order.id,
                from_status=None,
                to_status=OrderStatus.DRAFT.value,
                changed_by=actor,
                reason="created",
                metadata_json={"event": "ORDER_CREATED"},
            )
        )
        self._session.flush()

        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="order_created",
            resource_ids={
                "order_id": str(order.id),
                "order_number": order.order_number,
                "customer_id": str(customer.id),
            },
            idempotency_key=key,
            payload_summary={
                "total": str(order.total),
                "currency": order.currency,
                "item_count": len(line_payloads),
            },
        )
        from callbot_platform.automations.constants import AutomationEventType
        from callbot_platform.automations.publishers import publish_order_event

        publish_order_event(
            self._session,
            tenant_id=tenant_id,
            order_id=order.id,
            event_type=AutomationEventType.ORDER_CREATED.value,
            customer_id=customer.id,
            status=order.status,
        )
        return serialize_order(
            self._load(tenant_id, order.id, include_history=True),
            include_history=True,
        )

    def update(
        self,
        tenant_id: UUID,
        order_id: UUID,
        *,
        actor: str,
        notes: str | None = None,
        clear_notes: bool = False,
        shipping_total: object | None = None,
        order_discount: object | None = None,
        shipping_address_snapshot: dict[str, Any] | None = None,
        billing_address_snapshot: dict[str, Any] | None = None,
        fulfillment_location_id: UUID | None = None,
        clear_fulfillment_location: bool = False,
        items: list[dict[str, Any]] | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        if status is not None:
            raise CrmError(
                "use_transition",
                "Status changes must use POST /orders/{id}/transition",
            )

        order = self._load(tenant_id, order_id, for_update=True, require_active=True)
        mutable = order.status in EDITABLE_STATUSES

        if notes is not None or clear_notes:
            order.notes = None if clear_notes else (notes.strip() if notes else None)

        address_touched = (
            shipping_address_snapshot is not None
            or billing_address_snapshot is not None
            or fulfillment_location_id is not None
            or clear_fulfillment_location
        )
        if address_touched and not mutable:
            raise CrmError(
                "order_immutable",
                "Address and fulfillment fields are immutable after PENDING",
            )

        if shipping_address_snapshot is not None:
            order.shipping_address_snapshot = shipping_address_snapshot
        if billing_address_snapshot is not None:
            order.billing_address_snapshot = billing_address_snapshot

        if clear_fulfillment_location:
            order.fulfillment_location_id = None
        elif fulfillment_location_id is not None:
            order.fulfillment_location_id = fulfillment_location_id

        money_touched = (
            shipping_total is not None
            or order_discount is not None
            or items is not None
        )
        if money_touched and not mutable:
            raise CrmError(
                "order_immutable",
                "Line items and money fields are immutable after PENDING",
            )

        if money_touched:
            if items is not None:
                if not items:
                    raise CrmError(
                        "items_required", "Order requires at least one line item"
                    )
                # Replace lines atomically within the same transaction.
                for old in list(order.items):
                    self._session.delete(old)
                self._session.flush()
                line_payloads = []
                for idx, raw in enumerate(items):
                    pid = raw.get("product_id")
                    if pid is None:
                        raise CrmError(
                            "product_required", "Line item requires product_id"
                        )
                    line_payloads.append(
                        self._resolve_line(
                            tenant_id,
                            product_id=UUID(str(pid)),
                            variant_id=(
                                UUID(str(raw["variant_id"]))
                                if raw.get("variant_id")
                                else None
                            ),
                            quantity=int(raw.get("quantity") or 0),
                            unit_price=raw.get("unit_price"),
                            discount_total=raw.get("discount_total"),
                            tax_total=raw.get("tax_total"),
                            sort_order=int(raw.get("sort_order") or idx),
                        )
                    )
                for payload in line_payloads:
                    self._session.add(
                        OrderItem(
                            tenant_id=tenant_id,
                            order_id=order.id,
                            product_id=payload["product_id"],
                            variant_id=payload["variant_id"],
                            sku_snapshot=payload["sku_snapshot"],
                            product_name_snapshot=payload["product_name_snapshot"],
                            variant_name_snapshot=payload["variant_name_snapshot"],
                            unit_price=payload["unit_price"],
                            quantity=payload["quantity"],
                            discount_total=payload["discount_total"],
                            tax_total=payload["tax_total"],
                            line_subtotal=payload["line_subtotal"],
                            line_total=payload["line_total"],
                            sort_order=payload["sort_order"],
                        )
                    )
                self._session.flush()
                order = self._load(tenant_id, order_id, for_update=True)

            # Recompute totals from current lines + optional overrides.
            current_lines = [
                {
                    "line_subtotal": i.line_subtotal,
                    "discount_total": i.discount_total,
                    "tax_total": i.tax_total,
                }
                for i in order.items
            ]
            # Derive prior order-level discount (total discount - line discounts).
            prior_line_disc = sum((i.discount_total for i in order.items), _MONEY_ZERO)
            prior_order_disc = order.discount_total - prior_line_disc
            if prior_order_disc < 0:
                prior_order_disc = _MONEY_ZERO
            odisc = (
                money_or_zero(order_discount, field="order_discount")
                if order_discount is not None
                else prior_order_disc
            )
            ship = (
                money_or_zero(shipping_total, field="shipping_total")
                if shipping_total is not None
                else order.shipping_total
            )
            self._apply_totals(
                order,
                line_payloads=current_lines,
                order_discount=odisc,
                shipping_total=ship,
            )

        order.updated_by = actor
        order.updated_at = datetime.now(UTC)
        self._session.flush()

        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="order_updated",
            resource_ids={
                "order_id": str(order.id),
                "order_number": order.order_number,
            },
        )
        return serialize_order(
            self._load(tenant_id, order.id, include_history=True),
            include_history=True,
        )

    def archive(self, tenant_id: UUID, order_id: UUID, *, actor: str) -> dict[str, Any]:
        order = self._load(tenant_id, order_id, for_update=True)
        if order.archived_at is not None:
            return serialize_order(order, include_history=True)
        if order.status not in {
            OrderStatus.DRAFT.value,
            OrderStatus.CANCELLED.value,
            OrderStatus.REFUNDED.value,
        }:
            raise CrmError(
                "archive_not_allowed",
                "Only DRAFT, CANCELLED, or REFUNDED orders can be archived",
            )
        order.archived_at = datetime.now(UTC)
        order.updated_by = actor
        order.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="order_archived",
            resource_ids={"order_id": str(order.id)},
        )
        return serialize_order(
            self._load(tenant_id, order.id, include_history=True),
            include_history=True,
        )

    def restore(self, tenant_id: UUID, order_id: UUID, *, actor: str) -> dict[str, Any]:
        order = self._load(tenant_id, order_id, for_update=True)
        if order.archived_at is None:
            return serialize_order(order, include_history=True)
        order.archived_at = None
        order.updated_by = actor
        order.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="order_restored",
            resource_ids={"order_id": str(order.id)},
        )
        return serialize_order(
            self._load(tenant_id, order.id, include_history=True),
            include_history=True,
        )

    def transition(
        self,
        tenant_id: UUID,
        order_id: UUID,
        *,
        to_status: str,
        actor: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        return self.transitions.transition(
            tenant_id,
            order_id,
            to_status=to_status,
            actor=actor,
            reason=reason,
        )

    def history(self, tenant_id: UUID, order_id: UUID) -> dict[str, Any]:
        return {"history": self.transitions.history(tenant_id, order_id)}

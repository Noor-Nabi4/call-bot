"""Estimate CRM facade (Phase 13)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.estimates.constants import (
    APPROVABLE_STATUSES,
    DEFAULT_ESTIMATE_STATUS,
    EDITABLE_STATUSES,
    ITEM_TYPES,
    REJECTABLE_STATUSES,
    EstimateItemType,
    EstimateStatus,
)
from callbot_platform.crm.estimates.fingerprint import estimate_create_fingerprint
from callbot_platform.crm.estimates.money import (
    compute_tax_amount,
    line_subtotal,
    line_total,
    money_or_zero,
    normalize_currency,
    require_money,
    require_quantity,
    serialize_money,
)
from callbot_platform.crm.estimates.numbering import allocate_estimate_number
from callbot_platform.crm.estimates.search import EstimateSearchService
from callbot_platform.crm.estimates.serialize import serialize_estimate
from callbot_platform.crm.estimates.transitions import (
    EstimateTransitionService,
    is_expired,
)
from callbot_platform.crm.services.service import ServicesPricebookService
from callbot_platform.db.models import (
    Customer,
    CustomerLocation,
    Product,
    ProductVariant,
)
from callbot_platform.db.models.estimates import (
    Estimate,
    EstimateItem,
    EstimateStatusHistory,
)
from callbot_platform.db.models.services import Service
from callbot_platform.telephony.audit import write_audit

_MONEY_ZERO = Decimal("0.0000")


class EstimateService:
    """Application service for Estimates (RBAC enforced at the route layer)."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self.search = EstimateSearchService(session)
        self.transitions = EstimateTransitionService(session)

    def _load(
        self,
        tenant_id: UUID,
        estimate_id: UUID,
        *,
        for_update: bool = False,
        require_active: bool = False,
        include_history: bool = False,
        include_conversions: bool = False,
    ) -> Estimate:
        q = select(Estimate).where(
            Estimate.id == estimate_id, Estimate.tenant_id == tenant_id
        )
        if for_update:
            q = q.with_for_update()
        opts = [
            selectinload(Estimate.customer),
            selectinload(Estimate.location),
            selectinload(Estimate.items),
        ]
        if include_history:
            opts.append(selectinload(Estimate.status_history))
        if include_conversions:
            opts.append(selectinload(Estimate.conversions))
        q = q.options(*opts)
        estimate = self._session.scalar(q)
        if estimate is None:
            raise CrmError("not_found", "Estimate not found for tenant")
        if require_active and estimate.archived_at is not None:
            raise CrmError("estimate_archived", "Estimate is archived")
        return estimate

    def _require_customer(self, tenant_id: UUID, customer_id: UUID) -> Customer:
        row = self._session.scalar(
            select(Customer).where(
                Customer.id == customer_id, Customer.tenant_id == tenant_id
            )
        )
        if row is None:
            raise CrmError("customer_not_found", "Customer not found for tenant")
        return row

    def _require_location(
        self, tenant_id: UUID, customer_id: UUID, location_id: UUID
    ) -> CustomerLocation:
        row = self._session.scalar(
            select(CustomerLocation).where(
                CustomerLocation.id == location_id,
                CustomerLocation.tenant_id == tenant_id,
                CustomerLocation.customer_id == customer_id,
            )
        )
        if row is None:
            raise CrmError("location_not_found", "Location not found for tenant")
        return row

    def _resolve_line(
        self,
        tenant_id: UUID,
        raw: dict[str, Any],
        *,
        sort_order: int,
        default_pricebook_id: UUID | None,
    ) -> dict[str, Any]:
        item_type = (raw.get("item_type") or "").strip().upper()
        if item_type not in ITEM_TYPES:
            raise CrmError(
                "invalid_item_type", "item_type must be SERVICE, PRODUCT, or CUSTOM"
            )
        qty = require_quantity(raw.get("quantity", 1))
        disc = money_or_zero(raw.get("discount_total"), field="discount_total")
        desc = None
        if raw.get("description") is not None:
            desc = str(raw["description"]).strip() or None

        if item_type == EstimateItemType.SERVICE.value:
            sid = raw.get("service_id")
            if sid is None:
                raise CrmError("service_required", "SERVICE line requires service_id")
            service_id = UUID(str(sid))
            service = self._session.scalar(
                select(Service).where(
                    Service.id == service_id, Service.tenant_id == tenant_id
                )
            )
            if service is None or service.archived_at is not None:
                raise CrmError("service_not_found", "Service not found for tenant")
            pb_id = (
                UUID(str(raw["pricebook_id"]))
                if raw.get("pricebook_id")
                else default_pricebook_id
            )
            if raw.get("unit_price") is not None:
                price = require_money(raw["unit_price"], field="unit_price")
                source = "manual_override"
            else:
                resolved = ServicesPricebookService(self._session).resolve_price(
                    tenant_id, service_id=service_id, pricebook_id=pb_id
                )
                if resolved.get("price") is None:
                    raise CrmError("price_unavailable", "No price for service line")
                price = require_money(resolved["price"], field="unit_price")
                source = str(resolved.get("source") or "pricebook")
                if pb_id is None and resolved.get("pricebook_id"):
                    pb_id = UUID(str(resolved["pricebook_id"]))
            tax_rate = None
            if raw.get("tax_total") is not None:
                tax = money_or_zero(raw.get("tax_total"), field="tax_total")
            else:
                tax = _MONEY_ZERO
            sub = line_subtotal(price, qty)
            total = line_total(subtotal=sub, discount=disc, tax=tax)
            return {
                "item_type": item_type,
                "service_id": service.id,
                "product_id": None,
                "variant_id": None,
                "pricebook_id": pb_id,
                "name_snapshot": service.name[:255],
                "description_snapshot": desc or (service.description or None),
                "sku_snapshot": None,
                "code_snapshot": (getattr(service, "code", None) or None),
                "pricing_source_snapshot": source,
                "tax_rate_snapshot": tax_rate,
                "quantity": qty,
                "unit_price": price,
                "discount_total": disc,
                "tax_total": tax,
                "line_subtotal": sub,
                "line_total": total,
                "sort_order": sort_order,
            }

        if item_type == EstimateItemType.PRODUCT.value:
            pid = raw.get("product_id")
            if pid is None:
                raise CrmError("product_required", "PRODUCT line requires product_id")
            product_id = UUID(str(pid))
            product = self._session.scalar(
                select(Product).where(
                    Product.id == product_id, Product.tenant_id == tenant_id
                )
            )
            if product is None or product.archived_at is not None:
                raise CrmError("product_not_found", "Product not found for tenant")
            if product.status != "ACTIVE":
                raise CrmError("product_inactive", "Product is not active")
            variant: ProductVariant | None = None
            if raw.get("variant_id"):
                variant = self._session.scalar(
                    select(ProductVariant).where(
                        ProductVariant.id == UUID(str(raw["variant_id"])),
                        ProductVariant.tenant_id == tenant_id,
                    )
                )
                if variant is None or variant.product_id != product.id:
                    raise CrmError(
                        "variant_product_mismatch",
                        "Variant does not belong to the specified product",
                    )
                if variant.archived_at is not None or variant.status != "ACTIVE":
                    raise CrmError("variant_inactive", "Variant is not active")
            if raw.get("unit_price") is not None:
                price = require_money(raw["unit_price"], field="unit_price")
                source = "manual_override"
            else:
                catalog = (
                    variant.price
                    if variant is not None and variant.price is not None
                    else product.price
                )
                if catalog is None:
                    raise CrmError("price_unavailable", "No catalog price for product")
                price = require_money(catalog, field="unit_price")
                source = "catalog"
            sub = line_subtotal(price, qty)
            if raw.get("tax_total") is not None:
                tax = money_or_zero(raw.get("tax_total"), field="tax_total")
            else:
                tax = compute_tax_amount(
                    taxable=sub - disc, tax_rate_percent=product.tax_rate
                )
            total = line_total(subtotal=sub, discount=disc, tax=tax)
            sku = (
                variant.sku
                if variant is not None
                else (product.sku or product.sku_normalized or "UNKNOWN")
            )
            return {
                "item_type": item_type,
                "service_id": None,
                "product_id": product.id,
                "variant_id": variant.id if variant else None,
                "pricebook_id": None,
                "name_snapshot": product.name[:255],
                "description_snapshot": desc,
                "sku_snapshot": str(sku)[:64],
                "code_snapshot": None,
                "pricing_source_snapshot": source,
                "tax_rate_snapshot": product.tax_rate,
                "quantity": qty,
                "unit_price": price,
                "discount_total": disc,
                "tax_total": tax,
                "line_subtotal": sub,
                "line_total": total,
                "sort_order": sort_order,
            }

        # CUSTOM
        name = (raw.get("name") or raw.get("description") or "").strip()
        if not name:
            raise CrmError("name_required", "CUSTOM line requires name or description")
        if raw.get("unit_price") is None:
            raise CrmError("unit_price_required", "CUSTOM line requires unit_price")
        price = require_money(raw["unit_price"], field="unit_price")
        sub = line_subtotal(price, qty)
        tax = money_or_zero(raw.get("tax_total"), field="tax_total")
        total = line_total(subtotal=sub, discount=disc, tax=tax)
        return {
            "item_type": item_type,
            "service_id": None,
            "product_id": None,
            "variant_id": None,
            "pricebook_id": None,
            "name_snapshot": name[:255],
            "description_snapshot": desc or name,
            "sku_snapshot": None,
            "code_snapshot": None,
            "pricing_source_snapshot": "custom",
            "tax_rate_snapshot": None,
            "quantity": qty,
            "unit_price": price,
            "discount_total": disc,
            "tax_total": tax,
            "line_subtotal": sub,
            "line_total": total,
            "sort_order": sort_order,
        }

    def _apply_totals(
        self,
        estimate: Estimate,
        *,
        line_payloads: list[dict[str, Any]],
        estimate_discount: Decimal,
    ) -> None:
        subtotal = sum((p["line_subtotal"] for p in line_payloads), _MONEY_ZERO)
        line_discount = sum((p["discount_total"] for p in line_payloads), _MONEY_ZERO)
        tax_total = sum((p["tax_total"] for p in line_payloads), _MONEY_ZERO)
        discount_total = line_discount + estimate_discount
        if discount_total > subtotal:
            raise CrmError(
                "invalid_discount_total",
                "Total discount cannot exceed estimate subtotal",
            )
        total = subtotal - discount_total + tax_total
        if total < 0:
            raise CrmError("invalid_total", "Estimate total cannot be negative")
        estimate.subtotal = subtotal
        estimate.discount_total = discount_total
        estimate.estimate_discount = estimate_discount
        estimate.tax_total = tax_total
        estimate.total = total

    def _replace_items(
        self, estimate: Estimate, line_payloads: list[dict[str, Any]]
    ) -> None:
        for existing in list(estimate.items or []):
            self._session.delete(existing)
        self._session.flush()
        for payload in line_payloads:
            self._session.add(
                EstimateItem(
                    tenant_id=estimate.tenant_id,
                    estimate_id=estimate.id,
                    **payload,
                )
            )
        self._session.flush()

    def get(self, tenant_id: UUID, estimate_id: UUID) -> dict[str, Any]:
        estimate = self._load(
            tenant_id,
            estimate_id,
            include_history=True,
            include_conversions=True,
        )
        return serialize_estimate(
            estimate, include_history=True, include_conversions=True
        )

    def list(self, tenant_id: UUID, **kwargs: Any) -> dict[str, Any]:
        return self.search.search(tenant_id, **kwargs)

    def create(
        self,
        tenant_id: UUID,
        *,
        customer_id: UUID,
        actor: str,
        items: list[dict[str, Any]],
        title: str | None = None,
        description: str | None = None,
        location_id: UUID | None = None,
        currency: str | None = None,
        estimate_discount: object | None = None,
        valid_until: datetime | None = None,
        notes: str | None = None,
        terms: str | None = None,
        pricebook_id: UUID | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        key = idempotency_key.strip() if idempotency_key else None
        if not items:
            raise CrmError("items_required", "Estimate requires at least one line item")

        customer = self._require_customer(tenant_id, customer_id)
        loc_id = None
        if location_id is not None:
            loc_id = self._require_location(tenant_id, customer.id, location_id).id

        cur = normalize_currency(currency)
        edisc = money_or_zero(estimate_discount, field="estimate_discount")
        title_clean = (title or "Estimate").strip()[:255] or "Estimate"
        notes_clean = notes.strip() if notes and notes.strip() else None
        terms_clean = terms.strip() if terms and terms.strip() else None
        desc_clean = (
            description.strip() if description and description.strip() else None
        )
        vu = valid_until
        if vu is not None and vu.tzinfo is None:
            vu = vu.replace(tzinfo=UTC)

        line_payloads = [
            self._resolve_line(
                tenant_id,
                raw,
                sort_order=int(raw.get("sort_order") or idx),
                default_pricebook_id=pricebook_id,
            )
            for idx, raw in enumerate(items)
        ]

        req_hash = estimate_create_fingerprint(
            customer_id=customer.id,
            location_id=loc_id,
            title=title_clean,
            currency=cur,
            estimate_discount=serialize_money(edisc),
            valid_until=vu.isoformat() if vu else None,
            items=items,
            notes=notes_clean,
            terms=terms_clean,
        )

        if key:
            existing = self._session.scalar(
                select(Estimate).where(
                    Estimate.tenant_id == tenant_id, Estimate.idempotency_key == key
                )
            )
            if existing is not None:
                if (
                    existing.idempotency_request_hash
                    and existing.idempotency_request_hash != req_hash
                ):
                    raise CrmError(
                        "idempotency_conflict",
                        "Idempotency-Key reused with a different estimate payload",
                    )
                return self.get(tenant_id, existing.id)

        number = allocate_estimate_number(self._session, tenant_id)
        estimate = Estimate(
            tenant_id=tenant_id,
            estimate_number=number,
            customer_id=customer.id,
            location_id=loc_id,
            title=title_clean,
            description=desc_clean,
            status=DEFAULT_ESTIMATE_STATUS,
            currency=cur,
            valid_until=vu,
            notes=notes_clean,
            terms=terms_clean,
            pricebook_id=pricebook_id,
            idempotency_key=key,
            idempotency_request_hash=req_hash if key else None,
            created_by=actor,
            updated_by=actor,
        )
        self._apply_totals(
            estimate, line_payloads=line_payloads, estimate_discount=edisc
        )
        try:
            with self._session.begin_nested():
                self._session.add(estimate)
                self._session.flush()
        except IntegrityError as exc:
            if key:
                raced = self._session.scalar(
                    select(Estimate).where(
                        Estimate.tenant_id == tenant_id,
                        Estimate.idempotency_key == key,
                    )
                )
                if raced is not None:
                    if (
                        raced.idempotency_request_hash
                        and raced.idempotency_request_hash != req_hash
                    ):
                        raise CrmError(
                            "idempotency_conflict",
                            "Idempotency-Key reused with a different estimate payload",
                        ) from exc
                    return self.get(tenant_id, raced.id)
            raise CrmError("estimate_conflict", "Could not create estimate") from exc

        for payload in line_payloads:
            self._session.add(
                EstimateItem(tenant_id=tenant_id, estimate_id=estimate.id, **payload)
            )
        self._session.add(
            EstimateStatusHistory(
                tenant_id=tenant_id,
                estimate_id=estimate.id,
                from_status=None,
                to_status=EstimateStatus.DRAFT.value,
                changed_by=actor,
                reason="created",
                metadata_json={"event": "ESTIMATE_CREATED"},
            )
        )
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="estimate_created",
            resource_ids={
                "estimate_id": str(estimate.id),
                "estimate_number": estimate.estimate_number,
                "customer_id": str(customer.id),
            },
            idempotency_key=key,
            payload_summary={
                "total": str(estimate.total),
                "currency": estimate.currency,
                "item_count": len(line_payloads),
            },
        )
        return self.get(tenant_id, estimate.id)

    def update(
        self,
        tenant_id: UUID,
        estimate_id: UUID,
        *,
        actor: str,
        title: str | None = None,
        description: str | None = None,
        clear_description: bool = False,
        location_id: UUID | None = None,
        clear_location: bool = False,
        notes: str | None = None,
        clear_notes: bool = False,
        terms: str | None = None,
        clear_terms: bool = False,
        estimate_discount: object | None = None,
        valid_until: datetime | None = None,
        clear_valid_until: bool = False,
        items: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        estimate = self._load(
            tenant_id, estimate_id, for_update=True, require_active=True
        )
        if estimate.status not in EDITABLE_STATUSES:
            raise CrmError(
                "estimate_immutable",
                f"Cannot update estimate in status {estimate.status}",
            )
        if title is not None:
            estimate.title = title.strip()[:255] or "Estimate"
        if clear_description:
            estimate.description = None
        elif description is not None:
            estimate.description = description.strip() or None
        if clear_location:
            estimate.location_id = None
        elif location_id is not None:
            estimate.location_id = self._require_location(
                tenant_id, estimate.customer_id, location_id
            ).id
        if clear_notes:
            estimate.notes = None
        elif notes is not None:
            estimate.notes = notes.strip() or None
        if clear_terms:
            estimate.terms = None
        elif terms is not None:
            estimate.terms = terms.strip() or None
        if clear_valid_until:
            estimate.valid_until = None
        elif valid_until is not None:
            vu = valid_until
            if vu.tzinfo is None:
                vu = vu.replace(tzinfo=UTC)
            estimate.valid_until = vu

        edisc = (
            money_or_zero(estimate_discount, field="estimate_discount")
            if estimate_discount is not None
            else estimate.estimate_discount
        )
        if items is not None:
            if not items:
                raise CrmError("items_required", "Estimate requires at least one line")
            payloads = [
                self._resolve_line(
                    tenant_id,
                    raw,
                    sort_order=int(raw.get("sort_order") or idx),
                    default_pricebook_id=estimate.pricebook_id,
                )
                for idx, raw in enumerate(items)
            ]
            self._replace_items(estimate, payloads)
            self._apply_totals(
                estimate, line_payloads=payloads, estimate_discount=edisc
            )
        else:
            current = [
                {
                    "line_subtotal": i.line_subtotal,
                    "discount_total": i.discount_total,
                    "tax_total": i.tax_total,
                }
                for i in (estimate.items or [])
            ]
            self._apply_totals(estimate, line_payloads=current, estimate_discount=edisc)

        estimate.updated_by = actor
        estimate.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="estimate_updated",
            resource_ids={"estimate_id": str(estimate.id)},
        )
        return self.get(tenant_id, estimate.id)

    def add_item(
        self,
        tenant_id: UUID,
        estimate_id: UUID,
        *,
        actor: str,
        item: dict[str, Any],
    ) -> dict[str, Any]:
        estimate = self._load(
            tenant_id, estimate_id, for_update=True, require_active=True
        )
        if estimate.status not in EDITABLE_STATUSES:
            raise CrmError("estimate_immutable", "Cannot modify items in this status")
        payloads = [
            {
                "line_subtotal": i.line_subtotal,
                "discount_total": i.discount_total,
                "tax_total": i.tax_total,
            }
            for i in (estimate.items or [])
        ]
        sort = int(item.get("sort_order") or len(payloads))
        new_payload = self._resolve_line(
            tenant_id,
            item,
            sort_order=sort,
            default_pricebook_id=estimate.pricebook_id,
        )
        self._session.add(
            EstimateItem(tenant_id=tenant_id, estimate_id=estimate.id, **new_payload)
        )
        payloads.append(new_payload)
        self._apply_totals(
            estimate,
            line_payloads=payloads,
            estimate_discount=estimate.estimate_discount,
        )
        estimate.updated_by = actor
        estimate.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="estimate_item_added",
            resource_ids={"estimate_id": str(estimate.id)},
        )
        return self.get(tenant_id, estimate.id)

    def remove_item(
        self,
        tenant_id: UUID,
        estimate_id: UUID,
        item_id: UUID,
        *,
        actor: str,
    ) -> dict[str, Any]:
        estimate = self._load(
            tenant_id, estimate_id, for_update=True, require_active=True
        )
        if estimate.status not in EDITABLE_STATUSES:
            raise CrmError("estimate_immutable", "Cannot modify items in this status")
        item = self._session.scalar(
            select(EstimateItem).where(
                EstimateItem.id == item_id,
                EstimateItem.tenant_id == tenant_id,
                EstimateItem.estimate_id == estimate_id,
            )
        )
        if item is None:
            raise CrmError("not_found", "Estimate item not found for tenant")
        self._session.delete(item)
        self._session.flush()
        remaining = list(
            self._session.scalars(
                select(EstimateItem).where(
                    EstimateItem.tenant_id == tenant_id,
                    EstimateItem.estimate_id == estimate_id,
                )
            ).all()
        )
        if not remaining:
            raise CrmError("items_required", "Estimate requires at least one line item")
        payloads = [
            {
                "line_subtotal": i.line_subtotal,
                "discount_total": i.discount_total,
                "tax_total": i.tax_total,
            }
            for i in remaining
        ]
        self._apply_totals(
            estimate,
            line_payloads=payloads,
            estimate_discount=estimate.estimate_discount,
        )
        estimate.updated_by = actor
        estimate.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="estimate_item_removed",
            resource_ids={
                "estimate_id": str(estimate.id),
                "item_id": str(item_id),
            },
        )
        return self.get(tenant_id, estimate.id)

    def send(self, tenant_id: UUID, estimate_id: UUID, *, actor: str) -> dict[str, Any]:
        return self.transitions.transition(
            tenant_id,
            estimate_id,
            to_status=EstimateStatus.SENT.value,
            actor=actor,
            reason="sent",
            metadata={"event": "ESTIMATE_SENT"},
        )

    def mark_viewed(
        self, tenant_id: UUID, estimate_id: UUID, *, actor: str
    ) -> dict[str, Any]:
        return self.transitions.transition(
            tenant_id,
            estimate_id,
            to_status=EstimateStatus.VIEWED.value,
            actor=actor,
            reason="viewed",
            metadata={"event": "ESTIMATE_VIEWED"},
        )

    def approve(
        self, tenant_id: UUID, estimate_id: UUID, *, actor: str
    ) -> dict[str, Any]:
        estimate = self._load(
            tenant_id, estimate_id, for_update=True, require_active=True
        )
        if estimate.status not in APPROVABLE_STATUSES:
            raise CrmError(
                "invalid_transition",
                f"Cannot approve estimate in status {estimate.status}",
            )
        if is_expired(estimate):
            raise CrmError("estimate_expired", "Estimate is past valid_until")
        if not estimate.items:
            raise CrmError("items_required", "Cannot approve an empty estimate")
        return self.transitions.transition(
            tenant_id,
            estimate_id,
            to_status=EstimateStatus.APPROVED.value,
            actor=actor,
            reason="approved",
            metadata={"event": "ESTIMATE_APPROVED"},
        )

    def reject(
        self,
        tenant_id: UUID,
        estimate_id: UUID,
        *,
        actor: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        estimate = self._load(
            tenant_id, estimate_id, for_update=True, require_active=True
        )
        if estimate.status not in REJECTABLE_STATUSES:
            raise CrmError(
                "invalid_transition",
                f"Cannot reject estimate in status {estimate.status}",
            )
        return self.transitions.transition(
            tenant_id,
            estimate_id,
            to_status=EstimateStatus.REJECTED.value,
            actor=actor,
            reason=reason or "rejected",
            metadata={"event": "ESTIMATE_REJECTED"},
        )

    def cancel(
        self,
        tenant_id: UUID,
        estimate_id: UUID,
        *,
        actor: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        return self.transitions.transition(
            tenant_id,
            estimate_id,
            to_status=EstimateStatus.CANCELLED.value,
            actor=actor,
            reason=reason or "cancelled",
            metadata={"event": "ESTIMATE_CANCELLED"},
        )

    def expire_if_needed(
        self, tenant_id: UUID, estimate_id: UUID, *, actor: str = "system"
    ) -> dict[str, Any] | None:
        estimate = self._load(tenant_id, estimate_id, for_update=True)
        if not is_expired(estimate):
            return None
        if estimate.status in {
            EstimateStatus.EXPIRED.value,
            EstimateStatus.CONVERTED.value,
            EstimateStatus.CANCELLED.value,
            EstimateStatus.REJECTED.value,
        }:
            return None
        return self.transitions.transition(
            tenant_id,
            estimate_id,
            to_status=EstimateStatus.EXPIRED.value,
            actor=actor,
            reason="expired",
            metadata={"event": "ESTIMATE_EXPIRED"},
        )

    def archive(
        self, tenant_id: UUID, estimate_id: UUID, *, actor: str
    ) -> dict[str, Any]:
        estimate = self._load(tenant_id, estimate_id, for_update=True)
        if estimate.archived_at is not None:
            return self.get(tenant_id, estimate_id)
        if estimate.status not in {
            EstimateStatus.DRAFT.value,
            EstimateStatus.CANCELLED.value,
            EstimateStatus.REJECTED.value,
            EstimateStatus.EXPIRED.value,
            EstimateStatus.CONVERTED.value,
        }:
            raise CrmError(
                "archive_not_allowed",
                "Only draft/terminal estimates can be archived",
            )
        estimate.archived_at = datetime.now(UTC)
        estimate.updated_by = actor
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="estimate_archived",
            resource_ids={"estimate_id": str(estimate.id)},
        )
        return self.get(tenant_id, estimate_id)

    def convert(
        self, tenant_id: UUID, estimate_id: UUID, **kwargs: Any
    ) -> dict[str, Any]:
        from callbot_platform.crm.estimates.conversion import EstimateConversionService

        return EstimateConversionService(self._session).convert(
            tenant_id, estimate_id, **kwargs
        )

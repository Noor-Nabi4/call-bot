"""Pricebook CRUD, items, components, and tenant overrides."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.services.constants import (
    COMPONENT_TYPES,
    DEFAULT_STATUS,
    PricingType,
)
from callbot_platform.crm.services.normalize import (
    is_effective_at,
    normalize_component_type,
    normalize_pricing_type,
    normalize_status,
    parse_effective_range,
    parse_money,
    parse_positive_decimal,
    ranges_overlap,
    trim,
)
from callbot_platform.crm.services.serialize import (
    serialize_component,
    serialize_item,
    serialize_override,
    serialize_pricebook,
)
from callbot_platform.db.models import ProductVariant
from callbot_platform.db.models.services import (
    Pricebook,
    PricebookItem,
    PricebookItemComponent,
    PricebookOverride,
    Service,
)
from callbot_platform.telephony.audit import write_audit


class PricebookService:
    def __init__(self, session: Session) -> None:
        self._session = session

    # --- Pricebooks ---

    def list(
        self,
        tenant_id: UUID,
        *,
        include_archived: bool = False,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        q = select(Pricebook).where(Pricebook.tenant_id == tenant_id)
        if not include_archived:
            q = q.where(Pricebook.archived_at.is_(None))
        if status:
            q = q.where(Pricebook.status == normalize_status(status))
        q = q.order_by(Pricebook.is_default.desc(), Pricebook.name.asc()).limit(
            max(1, min(limit, 200))
        )
        return [serialize_pricebook(r) for r in self._session.scalars(q).all()]

    def get(
        self, tenant_id: UUID, pricebook_id: UUID, *, include_archived: bool = True
    ) -> dict[str, Any]:
        row = self._load_pricebook(
            tenant_id, pricebook_id, require_active=not include_archived
        )
        payload = serialize_pricebook(row)
        payload["items"] = self.list_items(tenant_id, pricebook_id)
        payload["overrides"] = self.list_overrides(tenant_id, pricebook_id)
        return payload

    def create(
        self,
        tenant_id: UUID,
        *,
        name: str,
        description: str | None = None,
        status: str | None = None,
        is_default: bool = False,
        effective_from: datetime | str | None = None,
        effective_until: datetime | str | None = None,
        actor: str = "system",
    ) -> dict[str, Any]:
        cleaned = trim(name, max_len=128, field="name")
        if not cleaned:
            raise CrmError("invalid_name", "Pricebook name is required")
        start, end = parse_effective_range(effective_from, effective_until)
        if is_default:
            self._clear_default(tenant_id)
        row = Pricebook(
            tenant_id=tenant_id,
            name=cleaned,
            description=trim(description, max_len=10000, field="description"),
            status=normalize_status(status),
            is_default=bool(is_default),
            effective_from=start,
            effective_until=end,
            created_by=actor,
            updated_by=actor,
        )
        self._session.add(row)
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise self._map_pricebook_integrity(exc) from exc
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="pricebook_created",
            resource_ids={"pricebook_id": str(row.id)},
        )
        return serialize_pricebook(row)

    def update(
        self,
        tenant_id: UUID,
        pricebook_id: UUID,
        *,
        name: str | None = None,
        description: str | None = None,
        status: str | None = None,
        is_default: bool | None = None,
        effective_from: datetime | str | None = None,
        effective_until: datetime | str | None = None,
        clear_effective: bool = False,
        actor: str = "system",
    ) -> dict[str, Any]:
        row = self._load_pricebook(tenant_id, pricebook_id, require_active=False)
        if row.archived_at is not None:
            raise CrmError("pricebook_archived", "Cannot update an archived pricebook")
        if name is not None:
            cleaned = trim(name, max_len=128, field="name")
            if not cleaned:
                raise CrmError("invalid_name", "Pricebook name is required")
            row.name = cleaned
        if description is not None:
            row.description = trim(description, max_len=10000, field="description")
        if status is not None:
            row.status = normalize_status(status)
        if clear_effective:
            row.effective_from = None
            row.effective_until = None
        elif effective_from is not None or effective_until is not None:
            start, end = parse_effective_range(
                effective_from if effective_from is not None else row.effective_from,
                effective_until if effective_until is not None else row.effective_until,
            )
            row.effective_from = start
            row.effective_until = end
        if is_default is True:
            self._clear_default(tenant_id, exclude_id=row.id)
            row.is_default = True
        elif is_default is False:
            row.is_default = False
        row.updated_by = actor
        row.updated_at = datetime.now(UTC)
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise self._map_pricebook_integrity(exc) from exc
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="pricebook_updated",
            resource_ids={"pricebook_id": str(row.id)},
        )
        return serialize_pricebook(row)

    def archive(
        self, tenant_id: UUID, pricebook_id: UUID, *, actor: str = "system"
    ) -> dict[str, Any]:
        row = self._load_pricebook(tenant_id, pricebook_id, require_active=True)
        row.archived_at = datetime.now(UTC)
        row.status = "INACTIVE"
        row.is_default = False
        row.updated_by = actor
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="pricebook_archived",
            resource_ids={"pricebook_id": str(row.id)},
        )
        return serialize_pricebook(row)

    def restore(
        self, tenant_id: UUID, pricebook_id: UUID, *, actor: str = "system"
    ) -> dict[str, Any]:
        row = self._load_pricebook(tenant_id, pricebook_id, require_active=False)
        if row.archived_at is None:
            return serialize_pricebook(row)
        row.archived_at = None
        row.status = DEFAULT_STATUS
        row.updated_by = actor
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="pricebook_restored",
            resource_ids={"pricebook_id": str(row.id)},
        )
        return serialize_pricebook(row)

    # --- Items ---

    def list_items(
        self, tenant_id: UUID, pricebook_id: UUID, *, include_archived: bool = False
    ) -> list[dict[str, Any]]:
        self._load_pricebook(tenant_id, pricebook_id, require_active=False)
        q = (
            select(PricebookItem)
            .options(selectinload(PricebookItem.components))
            .where(
                PricebookItem.tenant_id == tenant_id,
                PricebookItem.pricebook_id == pricebook_id,
            )
        )
        if not include_archived:
            q = q.where(PricebookItem.archived_at.is_(None))
        q = q.order_by(PricebookItem.created_at.asc())
        rows = list(self._session.scalars(q).all())
        return self._serialize_items_batch(tenant_id, rows)

    def create_item(
        self,
        tenant_id: UUID,
        pricebook_id: UUID,
        *,
        service_id: UUID,
        pricing_type: str,
        price: object | None = None,
        starting_price: object | None = None,
        hourly_rate: object | None = None,
        effective_from: datetime | str | None = None,
        effective_until: datetime | str | None = None,
        status: str | None = None,
        components: list[dict[str, Any]] | None = None,
        actor: str = "system",
    ) -> dict[str, Any]:
        pb = self._lock_pricebook(tenant_id, pricebook_id, require_active=True)
        service = self._load_service(tenant_id, service_id, require_active=True)
        ptype = normalize_pricing_type(pricing_type)
        amounts = self._validate_pricing_amounts(
            ptype,
            price=price,
            starting_price=starting_price,
            hourly_rate=hourly_rate,
        )
        start, end = parse_effective_range(effective_from, effective_until)
        self._assert_no_item_overlap(
            tenant_id,
            pricebook_id=pb.id,
            service_id=service.id,
            effective_from=start,
            effective_until=end,
        )
        item = PricebookItem(
            tenant_id=tenant_id,
            pricebook_id=pb.id,
            service_id=service.id,
            pricing_type=ptype,
            price=amounts["price"],
            starting_price=amounts["starting_price"],
            hourly_rate=amounts["hourly_rate"],
            effective_from=start,
            effective_until=end,
            status=normalize_status(status),
            created_by=actor,
            updated_by=actor,
        )
        self._session.add(item)
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise self._map_range_integrity(exc) from exc
        self._replace_components(tenant_id, item, components or [], actor=actor)
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise self._map_range_integrity(exc) from exc
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="pricebook_item_created",
            resource_ids={
                "pricebook_id": str(pb.id),
                "item_id": str(item.id),
                "service_id": str(service.id),
                "pricing_type": ptype,
            },
        )
        loaded = self._load_item(tenant_id, pb.id, item.id, require_active=False)
        return self._serialize_items_batch(tenant_id, [loaded])[0]

    def update_item(
        self,
        tenant_id: UUID,
        pricebook_id: UUID,
        item_id: UUID,
        *,
        pricing_type: str | None = None,
        price: object | None = None,
        starting_price: object | None = None,
        hourly_rate: object | None = None,
        effective_from: datetime | str | None = None,
        effective_until: datetime | str | None = None,
        clear_effective: bool = False,
        status: str | None = None,
        components: list[dict[str, Any]] | None = None,
        actor: str = "system",
    ) -> dict[str, Any]:
        item = self._load_item(tenant_id, pricebook_id, item_id, require_active=False)
        if item.archived_at is not None:
            raise CrmError("item_archived", "Cannot update an archived pricebook item")
        self._lock_pricebook(tenant_id, pricebook_id, require_active=True)
        ptype = (
            normalize_pricing_type(pricing_type)
            if pricing_type is not None
            else item.pricing_type
        )
        amounts = self._validate_pricing_amounts(
            ptype,
            price=price if price is not None else item.price,
            starting_price=(
                starting_price if starting_price is not None else item.starting_price
            ),
            hourly_rate=hourly_rate if hourly_rate is not None else item.hourly_rate,
            allow_existing=True,
        )
        if clear_effective:
            start, end = None, None
        elif effective_from is not None or effective_until is not None:
            start, end = parse_effective_range(
                effective_from if effective_from is not None else item.effective_from,
                effective_until
                if effective_until is not None
                else item.effective_until,
            )
        else:
            start, end = item.effective_from, item.effective_until
        self._assert_no_item_overlap(
            tenant_id,
            pricebook_id=pricebook_id,
            service_id=item.service_id,
            effective_from=start,
            effective_until=end,
            exclude_item_id=item.id,
        )
        old_price = item.price
        item.pricing_type = ptype
        item.price = amounts["price"]
        item.starting_price = amounts["starting_price"]
        item.hourly_rate = amounts["hourly_rate"]
        item.effective_from = start
        item.effective_until = end
        if status is not None:
            item.status = normalize_status(status)
        item.updated_by = actor
        item.updated_at = datetime.now(UTC)
        if components is not None:
            self._replace_components(tenant_id, item, components, actor=actor)
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise self._map_range_integrity(exc) from exc
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="pricebook_item_updated",
            resource_ids={
                "pricebook_id": str(pricebook_id),
                "item_id": str(item.id),
                "price_changed": str(old_price) != str(item.price),
            },
        )
        loaded = self._load_item(tenant_id, pricebook_id, item.id, require_active=False)
        return self._serialize_items_batch(tenant_id, [loaded])[0]

    def archive_item(
        self,
        tenant_id: UUID,
        pricebook_id: UUID,
        item_id: UUID,
        *,
        actor: str = "system",
    ) -> dict[str, Any]:
        item = self._load_item(tenant_id, pricebook_id, item_id, require_active=True)
        item.archived_at = datetime.now(UTC)
        item.status = "INACTIVE"
        item.updated_by = actor
        item.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="pricebook_item_archived",
            resource_ids={"pricebook_id": str(pricebook_id), "item_id": str(item.id)},
        )
        return self._serialize_items_batch(tenant_id, [item])[0]

    # --- Overrides ---

    def list_overrides(
        self, tenant_id: UUID, pricebook_id: UUID, *, include_archived: bool = False
    ) -> list[dict[str, Any]]:
        self._load_pricebook(tenant_id, pricebook_id, require_active=False)
        q = select(PricebookOverride).where(
            PricebookOverride.tenant_id == tenant_id,
            PricebookOverride.pricebook_id == pricebook_id,
        )
        if not include_archived:
            q = q.where(PricebookOverride.archived_at.is_(None))
        q = q.order_by(PricebookOverride.created_at.asc())
        return [serialize_override(r) for r in self._session.scalars(q).all()]

    def create_override(
        self,
        tenant_id: UUID,
        pricebook_id: UUID,
        *,
        service_id: UUID,
        override_price: object | None = None,
        pricing_type: str | None = None,
        effective_from: datetime | str | None = None,
        effective_until: datetime | str | None = None,
        status: str | None = None,
        actor: str = "system",
    ) -> dict[str, Any]:
        pb = self._lock_pricebook(tenant_id, pricebook_id, require_active=True)
        service = self._load_service(tenant_id, service_id, require_active=True)
        start, end = parse_effective_range(effective_from, effective_until)
        self._assert_no_override_overlap(
            tenant_id,
            pricebook_id=pb.id,
            service_id=service.id,
            effective_from=start,
            effective_until=end,
        )
        ptype = (
            normalize_pricing_type(pricing_type) if pricing_type is not None else None
        )
        row = PricebookOverride(
            tenant_id=tenant_id,
            pricebook_id=pb.id,
            service_id=service.id,
            override_price=parse_money(override_price, field="override_price"),
            pricing_type=ptype,
            effective_from=start,
            effective_until=end,
            status=normalize_status(status),
            created_by=actor,
            updated_by=actor,
        )
        self._session.add(row)
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise self._map_range_integrity(exc) from exc
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="pricebook_override_created",
            resource_ids={
                "pricebook_id": str(pb.id),
                "override_id": str(row.id),
                "service_id": str(service.id),
            },
        )
        return serialize_override(row)

    def archive_override(
        self,
        tenant_id: UUID,
        pricebook_id: UUID,
        override_id: UUID,
        *,
        actor: str = "system",
    ) -> dict[str, Any]:
        row = self._session.scalar(
            select(PricebookOverride).where(
                PricebookOverride.id == override_id,
                PricebookOverride.tenant_id == tenant_id,
                PricebookOverride.pricebook_id == pricebook_id,
            )
        )
        if row is None or row.archived_at is not None:
            raise CrmError("not_found", "Override not found for tenant")
        row.archived_at = datetime.now(UTC)
        row.status = "INACTIVE"
        row.updated_by = actor
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="pricebook_override_archived",
            resource_ids={
                "pricebook_id": str(pricebook_id),
                "override_id": str(row.id),
            },
        )
        return serialize_override(row)

    # --- Internals ---

    def _load_pricebook(
        self, tenant_id: UUID, pricebook_id: UUID, *, require_active: bool
    ) -> Pricebook:
        row = self._session.scalar(
            select(Pricebook).where(
                Pricebook.id == pricebook_id,
                Pricebook.tenant_id == tenant_id,
            )
        )
        if row is None:
            raise CrmError("not_found", "Pricebook not found for tenant")
        if require_active and row.archived_at is not None:
            raise CrmError("not_found", "Pricebook not found for tenant")
        return row

    def _load_service(
        self, tenant_id: UUID, service_id: UUID, *, require_active: bool
    ) -> Service:
        row = self._session.scalar(
            select(Service).where(
                Service.id == service_id,
                Service.tenant_id == tenant_id,
            )
        )
        if row is None:
            raise CrmError("invalid_service", "Service not found for tenant")
        if require_active and row.archived_at is not None:
            raise CrmError("invalid_service", "Service is archived")
        return row

    def _load_item(
        self,
        tenant_id: UUID,
        pricebook_id: UUID,
        item_id: UUID,
        *,
        require_active: bool,
    ) -> PricebookItem:
        row = self._session.scalar(
            select(PricebookItem)
            .options(selectinload(PricebookItem.components))
            .execution_options(populate_existing=True)
            .where(
                PricebookItem.id == item_id,
                PricebookItem.tenant_id == tenant_id,
                PricebookItem.pricebook_id == pricebook_id,
            )
        )
        if row is None:
            raise CrmError("not_found", "Pricebook item not found for tenant")
        if require_active and row.archived_at is not None:
            raise CrmError("not_found", "Pricebook item not found for tenant")
        return row

    def _lock_pricebook(
        self, tenant_id: UUID, pricebook_id: UUID, *, require_active: bool
    ) -> Pricebook:
        """Lock pricebook row to serialize item/override mutations for the scope."""
        row = self._session.scalar(
            select(Pricebook)
            .where(
                Pricebook.id == pricebook_id,
                Pricebook.tenant_id == tenant_id,
            )
            .with_for_update()
        )
        if row is None:
            raise CrmError("not_found", "Pricebook not found for tenant")
        if require_active and row.archived_at is not None:
            raise CrmError("not_found", "Pricebook not found for tenant")
        return row

    def _clear_default(
        self, tenant_id: UUID, *, exclude_id: UUID | None = None
    ) -> None:
        # Serialize default flips across concurrent writers for this tenant.
        q = select(Pricebook).where(Pricebook.tenant_id == tenant_id).with_for_update()
        for row in self._session.scalars(q).all():
            if exclude_id is not None and row.id == exclude_id:
                continue
            if row.is_default and row.archived_at is None:
                row.is_default = False

    def _assert_no_item_overlap(
        self,
        tenant_id: UUID,
        *,
        pricebook_id: UUID,
        service_id: UUID,
        effective_from: datetime | None,
        effective_until: datetime | None,
        exclude_item_id: UUID | None = None,
    ) -> None:
        q = (
            select(PricebookItem)
            .where(
                PricebookItem.tenant_id == tenant_id,
                PricebookItem.pricebook_id == pricebook_id,
                PricebookItem.service_id == service_id,
                PricebookItem.archived_at.is_(None),
                PricebookItem.status == "ACTIVE",
            )
            .with_for_update()
        )
        if exclude_item_id is not None:
            q = q.where(PricebookItem.id != exclude_item_id)
        for existing in self._session.scalars(q).all():
            if ranges_overlap(
                effective_from,
                effective_until,
                existing.effective_from,
                existing.effective_until,
            ):
                raise CrmError(
                    "effective_overlap",
                    "Overlapping active pricebook item for this service",
                )

    def _assert_no_override_overlap(
        self,
        tenant_id: UUID,
        *,
        pricebook_id: UUID,
        service_id: UUID,
        effective_from: datetime | None,
        effective_until: datetime | None,
        exclude_id: UUID | None = None,
    ) -> None:
        q = (
            select(PricebookOverride)
            .where(
                PricebookOverride.tenant_id == tenant_id,
                PricebookOverride.pricebook_id == pricebook_id,
                PricebookOverride.service_id == service_id,
                PricebookOverride.archived_at.is_(None),
                PricebookOverride.status == "ACTIVE",
            )
            .with_for_update()
        )
        if exclude_id is not None:
            q = q.where(PricebookOverride.id != exclude_id)
        for existing in self._session.scalars(q).all():
            if ranges_overlap(
                effective_from,
                effective_until,
                existing.effective_from,
                existing.effective_until,
            ):
                raise CrmError(
                    "effective_overlap",
                    "Overlapping active override for this service",
                )

    @staticmethod
    def _map_range_integrity(exc: IntegrityError) -> CrmError:
        msg = str(getattr(exc, "orig", exc)).lower()
        if (
            "excl_pricebook_items_active_effective" in msg
            or "excl_pricebook_overrides_active_effective" in msg
            or "exclusion" in msg
        ):
            return CrmError(
                "effective_overlap",
                "Overlapping active effective range for this service",
            )
        return CrmError("conflict", "Conflicting pricebook write")

    @staticmethod
    def _map_pricebook_integrity(exc: IntegrityError) -> CrmError:
        msg = str(getattr(exc, "orig", exc)).lower()
        if "uq_pricebooks_tenant_one_default" in msg:
            return CrmError(
                "default_conflict",
                "Tenant already has a default pricebook",
            )
        if "uq_pricebooks_tenant_name" in msg or "unique" in msg:
            return CrmError(
                "name_conflict", "Pricebook name already exists for this tenant"
            )
        return CrmError("conflict", "Conflicting pricebook write")

    def _validate_pricing_amounts(
        self,
        pricing_type: str,
        *,
        price: object | None,
        starting_price: object | None,
        hourly_rate: object | None,
        allow_existing: bool = False,
    ) -> dict[str, Decimal | None]:
        p = price if isinstance(price, Decimal) else parse_money(price, field="price")
        sp = (
            starting_price
            if isinstance(starting_price, Decimal)
            else parse_money(starting_price, field="starting_price")
        )
        hr = (
            hourly_rate
            if isinstance(hourly_rate, Decimal)
            else parse_money(hourly_rate, field="hourly_rate")
        )
        if pricing_type == PricingType.FIXED.value:
            if p is None and not allow_existing:
                raise CrmError("invalid_price", "FIXED pricing requires price")
        elif pricing_type == PricingType.STARTING_AT.value:
            if sp is None and p is None:
                raise CrmError(
                    "invalid_starting_price",
                    "STARTING_AT requires starting_price (or price)",
                )
            if sp is None:
                sp = p
        elif pricing_type == PricingType.HOURLY.value:
            if hr is None and p is None:
                raise CrmError(
                    "invalid_hourly_rate",
                    "HOURLY pricing requires hourly_rate (or price)",
                )
            if hr is None:
                hr = p
        # CUSTOM_QUOTE: all amounts optional
        return {"price": p, "starting_price": sp, "hourly_rate": hr}

    def _replace_components(
        self,
        tenant_id: UUID,
        item: PricebookItem,
        components: list[dict[str, Any]],
        *,
        actor: str,
    ) -> None:
        # Clear via collection so delete-orphan cascade stays consistent.
        item.components.clear()
        self._session.flush()
        for idx, raw in enumerate(components):
            ctype = normalize_component_type(str(raw.get("component_type", "")))
            variant_id_raw = raw.get("product_variant_id")
            variant_id: UUID | None = None
            if variant_id_raw:
                variant_id = UUID(str(variant_id_raw))
            if ctype == "MATERIAL":
                if variant_id is None:
                    raise CrmError(
                        "invalid_component",
                        "MATERIAL components require product_variant_id",
                    )
                variant = self._session.scalar(
                    select(ProductVariant).where(
                        ProductVariant.id == variant_id,
                        ProductVariant.tenant_id == tenant_id,
                        ProductVariant.archived_at.is_(None),
                    )
                )
                if variant is None:
                    raise CrmError(
                        "invalid_variant",
                        "Product variant not found for tenant",
                    )
            qty = parse_positive_decimal(
                raw.get("quantity", "1"), field="quantity"
            ) or Decimal("1")
            unit = parse_money(raw.get("unit_price"), field="unit_price")
            name = trim(raw.get("name"), max_len=255, field="name")
            sort_order = int(raw.get("sort_order", (idx + 1) * 100))
            item.components.append(
                PricebookItemComponent(
                    tenant_id=tenant_id,
                    component_type=ctype,
                    name=name,
                    product_variant_id=variant_id,
                    quantity=qty,
                    unit_price=unit,
                    sort_order=sort_order,
                )
            )
        _ = actor
        _ = COMPONENT_TYPES

    def _serialize_items_batch(
        self, tenant_id: UUID, rows: list[PricebookItem]
    ) -> list[dict[str, Any]]:
        if not rows:
            return []
        service_ids = {r.service_id for r in rows}
        services = {
            s.id: s
            for s in self._session.scalars(
                select(Service).where(
                    Service.tenant_id == tenant_id,
                    Service.id.in_(service_ids),
                )
            ).all()
        }
        variant_ids = {
            c.product_variant_id
            for r in rows
            for c in (r.components or [])
            if c.product_variant_id
        }
        variants: dict[UUID, ProductVariant] = {}
        if variant_ids:
            variants = {
                v.id: v
                for v in self._session.scalars(
                    select(ProductVariant).where(
                        ProductVariant.tenant_id == tenant_id,
                        ProductVariant.id.in_(variant_ids),
                    )
                ).all()
            }
        out: list[dict[str, Any]] = []
        for row in rows:
            svc = services.get(row.service_id)
            comps = []
            for c in sorted(
                row.components or [], key=lambda x: (x.sort_order, str(x.id))
            ):
                variant = (
                    variants.get(c.product_variant_id) if c.product_variant_id else None
                )
                comps.append(
                    serialize_component(
                        c,
                        variant_sku=variant.sku if variant else None,
                        variant_name=variant.name if variant else None,
                    )
                )
            out.append(
                serialize_item(
                    row,
                    service_name=svc.name if svc else None,
                    service_code=svc.code if svc else None,
                    components=comps,
                )
            )
        return out


# Re-export helper used by resolver
def item_effective_at(item: PricebookItem, at: datetime) -> bool:
    return (
        item.archived_at is None
        and item.status == "ACTIVE"
        and is_effective_at(
            at=at,
            effective_from=item.effective_from,
            effective_until=item.effective_until,
        )
    )

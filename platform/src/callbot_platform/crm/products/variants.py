"""Product variant CRUD with attribute fingerprints and SKU registry."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.products.constants import (
    CATALOG_STATUSES,
    DEFAULT_CATALOG_STATUS,
    SKU_OWNER_VARIANT,
)
from callbot_platform.crm.products.normalize import (
    SkuRegistry,
    normalize_sku,
    parse_money,
)
from callbot_platform.crm.products.serialize import serialize_variant
from callbot_platform.db.models import (
    Product,
    ProductAttribute,
    ProductAttributeValue,
    ProductVariant,
    ProductVariantAttributeValue,
)
from callbot_platform.telephony.audit import write_audit


def _trim(value: str | None, *, max_len: int, field: str) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > max_len:
        raise CrmError(f"invalid_{field}", f"{field} is too long")
    return cleaned


def fingerprint_attribute_values(attribute_value_ids: list[UUID]) -> str:
    """Sorted UUID strings joined by '|' for unique active-variant detection."""
    return "|".join(sorted(str(v) for v in attribute_value_ids))


class ProductVariantService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._skus = SkuRegistry(session)

    def list(
        self,
        tenant_id: UUID,
        product_id: UUID,
        *,
        include_archived: bool = False,
        include_cost: bool = False,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        product = self._load_product(tenant_id, product_id, require_active=False)
        q = select(ProductVariant).where(
            ProductVariant.tenant_id == tenant_id,
            ProductVariant.product_id == product_id,
        )
        if not include_archived:
            q = q.where(ProductVariant.archived_at.is_(None))
        q = (
            q.options(
                selectinload(ProductVariant.attribute_links)
                .selectinload(ProductVariantAttributeValue.attribute_value)
                .selectinload(ProductAttributeValue.attribute)
            )
            .order_by(ProductVariant.created_at.asc())
            .limit(max(1, min(limit, 500)))
        )
        return [
            serialize_variant(v, product=product, include_cost=include_cost)
            for v in self._session.scalars(q).all()
        ]

    def get(
        self,
        tenant_id: UUID,
        product_id: UUID,
        variant_id: UUID,
        *,
        include_cost: bool = False,
        include_archived: bool = True,
    ) -> dict[str, Any]:
        product = self._load_product(tenant_id, product_id, require_active=False)
        variant = self._load_variant(
            tenant_id,
            product_id,
            variant_id,
            require_active=not include_archived,
        )
        return serialize_variant(variant, product=product, include_cost=include_cost)

    def create(
        self,
        tenant_id: UUID,
        product_id: UUID,
        *,
        sku: str,
        name: str | None = None,
        price: object | None = None,
        cost: object | None = None,
        status: str | None = None,
        stock_on_hand: int | None = None,
        inventory_item_id: UUID | None = None,
        attribute_value_ids: list[UUID] | None = None,
        actor: str = "system",
        include_cost: bool = False,
    ) -> dict[str, Any]:
        self._load_product(tenant_id, product_id, require_active=True)
        display_sku, sku_norm = normalize_sku(sku, required=True)
        assert display_sku and sku_norm

        value_ids = list(attribute_value_ids or [])
        self._validate_attribute_values(tenant_id, product_id, value_ids)
        fingerprint = fingerprint_attribute_values(value_ids)
        self._assert_fingerprint_free(tenant_id, product_id, fingerprint)

        stock = self._parse_stock(stock_on_hand)
        variant = ProductVariant(
            tenant_id=tenant_id,
            product_id=product_id,
            sku=display_sku,
            sku_normalized=sku_norm,
            name=_trim(name, max_len=255, field="name"),
            price=parse_money(price, field="price"),
            cost=parse_money(cost, field="cost"),
            status=self._normalize_status(status),
            stock_on_hand=stock,
            inventory_item_id=inventory_item_id,
            attribute_fingerprint=fingerprint,
        )
        try:
            with self._session.begin_nested():
                self._session.add(variant)
                self._session.flush()
        except IntegrityError as exc:
            raise CrmError(
                "variant_conflict",
                "An active variant with these attributes already exists",
            ) from exc

        self._skus.claim(
            tenant_id,
            sku=display_sku,
            sku_normalized=sku_norm,
            owner_kind=SKU_OWNER_VARIANT,
            owner_id=variant.id,
        )
        for value_id in value_ids:
            self._session.add(
                ProductVariantAttributeValue(
                    tenant_id=tenant_id,
                    variant_id=variant.id,
                    attribute_value_id=value_id,
                )
            )
        self._session.flush()
        # Phase 6: inventory item is authoritative for stock; provision on create.
        if variant.inventory_item_id is None:
            from callbot_platform.crm.inventory.items import InventoryItemService

            item = InventoryItemService(self._session).ensure_for_variant(
                tenant_id, variant.id, actor=actor
            )
            variant.inventory_item_id = item.id
            self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="product_variant_created",
            resource_ids={
                "product_id": str(product_id),
                "variant_id": str(variant.id),
                "inventory_item_id": str(variant.inventory_item_id)
                if variant.inventory_item_id
                else None,
            },
        )
        return self.get(tenant_id, product_id, variant.id, include_cost=include_cost)

    def update(
        self,
        tenant_id: UUID,
        product_id: UUID,
        variant_id: UUID,
        *,
        actor: str = "system",
        include_cost: bool = False,
        **fields: Any,
    ) -> dict[str, Any]:
        product = self._load_product(tenant_id, product_id, require_active=True)
        variant = self._load_variant(
            tenant_id, product_id, variant_id, require_active=True
        )

        if "sku" in fields:
            display_sku, sku_norm = normalize_sku(fields["sku"], required=True)
            assert display_sku and sku_norm
            self._skus.transfer(
                tenant_id,
                owner_kind=SKU_OWNER_VARIANT,
                owner_id=variant.id,
                sku=display_sku,
                sku_normalized=sku_norm,
            )
            variant.sku = display_sku
            variant.sku_normalized = sku_norm

        if "name" in fields:
            variant.name = _trim(fields["name"], max_len=255, field="name")
        if "price" in fields:
            variant.price = parse_money(fields["price"], field="price")
        if "cost" in fields:
            variant.cost = parse_money(fields["cost"], field="cost")
        if "status" in fields:
            variant.status = self._normalize_status(fields["status"])
        if "stock_on_hand" in fields:
            variant.stock_on_hand = self._parse_stock(fields["stock_on_hand"])
        if "inventory_item_id" in fields:
            raw = fields["inventory_item_id"]
            variant.inventory_item_id = UUID(str(raw)) if raw is not None else None

        if "attribute_value_ids" in fields:
            raw_ids = fields["attribute_value_ids"] or []
            value_ids = [UUID(str(v)) for v in raw_ids]
            self._validate_attribute_values(tenant_id, product_id, value_ids)
            fingerprint = fingerprint_attribute_values(value_ids)
            self._assert_fingerprint_free(
                tenant_id, product_id, fingerprint, exclude_id=variant.id
            )
            variant.attribute_fingerprint = fingerprint
            existing = list(
                self._session.scalars(
                    select(ProductVariantAttributeValue).where(
                        ProductVariantAttributeValue.tenant_id == tenant_id,
                        ProductVariantAttributeValue.variant_id == variant.id,
                    )
                ).all()
            )
            for link in existing:
                self._session.delete(link)
            self._session.flush()
            for value_id in value_ids:
                self._session.add(
                    ProductVariantAttributeValue(
                        tenant_id=tenant_id,
                        variant_id=variant.id,
                        attribute_value_id=value_id,
                    )
                )

        variant.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="product_variant_updated",
            resource_ids={
                "product_id": str(product_id),
                "variant_id": str(variant_id),
            },
        )
        return serialize_variant(
            self._load_variant(tenant_id, product_id, variant_id, require_active=False),
            product=product,
            include_cost=include_cost,
        )

    def archive(
        self,
        tenant_id: UUID,
        product_id: UUID,
        variant_id: UUID,
        *,
        actor: str = "system",
        include_cost: bool = False,
    ) -> dict[str, Any]:
        product = self._load_product(tenant_id, product_id, require_active=False)
        variant = self._load_variant(
            tenant_id, product_id, variant_id, require_active=False
        )
        if variant.archived_at is None:
            variant.archived_at = datetime.now(UTC)
            variant.status = "INACTIVE"
            variant.updated_at = datetime.now(UTC)
            self._skus.release(
                tenant_id, owner_kind=SKU_OWNER_VARIANT, owner_id=variant.id
            )
            self._session.flush()
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="product_variant_archived",
                resource_ids={
                    "product_id": str(product_id),
                    "variant_id": str(variant_id),
                },
            )
        return serialize_variant(variant, product=product, include_cost=include_cost)

    def _load_product(
        self, tenant_id: UUID, product_id: UUID, *, require_active: bool
    ) -> Product:
        product = self._session.scalar(
            select(Product).where(
                Product.id == product_id,
                Product.tenant_id == tenant_id,
            )
        )
        if product is None:
            raise CrmError("not_found", "Product not found for tenant")
        if require_active and product.archived_at is not None:
            raise CrmError("product_archived", "Product is archived")
        return product

    def _load_variant(
        self,
        tenant_id: UUID,
        product_id: UUID,
        variant_id: UUID,
        *,
        require_active: bool,
    ) -> ProductVariant:
        variant = self._session.scalar(
            select(ProductVariant)
            .where(
                ProductVariant.id == variant_id,
                ProductVariant.tenant_id == tenant_id,
                ProductVariant.product_id == product_id,
            )
            .options(
                selectinload(ProductVariant.attribute_links)
                .selectinload(ProductVariantAttributeValue.attribute_value)
                .selectinload(ProductAttributeValue.attribute)
            )
        )
        if variant is None:
            raise CrmError("not_found", "Variant not found for product")
        if require_active and variant.archived_at is not None:
            raise CrmError("not_found", "Variant not found for product")
        return variant

    def _validate_attribute_values(
        self,
        tenant_id: UUID,
        product_id: UUID,
        value_ids: list[UUID],
    ) -> None:
        if not value_ids:
            return
        if len(value_ids) != len(set(value_ids)):
            raise CrmError(
                "invalid_attribute_values",
                "Duplicate attribute values are not allowed",
            )
        rows = list(
            self._session.scalars(
                select(ProductAttributeValue)
                .join(
                    ProductAttribute,
                    ProductAttribute.id == ProductAttributeValue.attribute_id,
                )
                .where(
                    ProductAttributeValue.tenant_id == tenant_id,
                    ProductAttribute.tenant_id == tenant_id,
                    ProductAttribute.product_id == product_id,
                    ProductAttributeValue.id.in_(value_ids),
                )
            ).all()
        )
        if len(rows) != len(value_ids):
            raise CrmError(
                "invalid_attribute_values",
                "Attribute values must belong to this product",
            )
        # At most one value per attribute on a variant.
        attr_ids = {row.attribute_id for row in rows}
        if len(attr_ids) != len(rows):
            raise CrmError(
                "invalid_attribute_values",
                "Variant may include at most one value per attribute",
            )

    def _assert_fingerprint_free(
        self,
        tenant_id: UUID,
        product_id: UUID,
        fingerprint: str,
        *,
        exclude_id: UUID | None = None,
    ) -> None:
        q = select(ProductVariant.id).where(
            ProductVariant.tenant_id == tenant_id,
            ProductVariant.product_id == product_id,
            ProductVariant.attribute_fingerprint == fingerprint,
            ProductVariant.archived_at.is_(None),
        )
        if exclude_id is not None:
            q = q.where(ProductVariant.id != exclude_id)
        if self._session.scalar(q) is not None:
            raise CrmError(
                "variant_conflict",
                "An active variant with these attributes already exists",
            )

    def _parse_stock(self, value: int | None) -> int | None:
        if value is None:
            return None
        try:
            stock = int(value)
        except (TypeError, ValueError) as exc:
            raise CrmError(
                "invalid_stock_on_hand", "stock_on_hand must be an integer"
            ) from exc
        if stock < 0:
            raise CrmError(
                "invalid_stock_on_hand", "stock_on_hand must be non-negative"
            )
        return stock

    def _normalize_status(self, status: str | None) -> str:
        if status is None:
            return DEFAULT_CATALOG_STATUS
        normalized = str(status).strip().upper()
        if normalized not in CATALOG_STATUSES:
            raise CrmError("invalid_status", "Status must be ACTIVE or INACTIVE")
        return normalized

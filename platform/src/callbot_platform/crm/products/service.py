"""Product catalog orchestrator — products CRUD, brands, and delegates."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.products.categories import ProductCategoryService
from callbot_platform.crm.products.constants import (
    CATALOG_STATUSES,
    DEFAULT_CATALOG_STATUS,
    SKU_OWNER_PRODUCT,
    SKU_OWNER_VARIANT,
)
from callbot_platform.crm.products.images import ProductImageService
from callbot_platform.crm.products.normalize import (
    SkuRegistry,
    normalize_sku,
    parse_money,
    parse_tax_rate,
    parse_weight,
)
from callbot_platform.crm.products.search import ProductSearchService
from callbot_platform.crm.products.serialize import serialize_product
from callbot_platform.crm.products.variants import ProductVariantService
from callbot_platform.db.models import (
    CatalogSku,
    Product,
    ProductAttribute,
    ProductAttributeValue,
    ProductBrand,
    ProductCategory,
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


def _normalize_brand_name(name: str) -> str:
    return " ".join(name.strip().split()).lower()


class ProductCatalogService:
    """Application service for the product catalog (RBAC at the route layer)."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._skus = SkuRegistry(session)
        self.categories = ProductCategoryService(session)
        self.variants = ProductVariantService(session)
        self.images = ProductImageService(session)
        self._search = ProductSearchService(session)

    def get(
        self,
        tenant_id: UUID,
        product_id: UUID,
        *,
        include_cost: bool = False,
        include_variants: bool = True,
        include_attributes: bool = True,
        include_images: bool = True,
        include_archived: bool = True,
    ) -> dict[str, Any]:
        product = self._load(
            tenant_id,
            product_id,
            require_active=not include_archived,
            with_details=True,
        )
        image_urls: dict[str, str] = {}
        if include_images:
            from callbot_platform.storage import get_object_storage

            storage = get_object_storage()
            for img in product.images or []:
                if img.archived_at is not None:
                    continue
                image_urls[str(img.id)] = storage.create_download_url(
                    tenant_id=tenant_id, object_key=img.object_key
                )
        return serialize_product(
            product,
            include_cost=include_cost,
            include_variants=include_variants,
            include_attributes=include_attributes,
            include_images=include_images,
            image_urls=image_urls,
        )

    def list(
        self,
        tenant_id: UUID,
        *,
        status: str | None = None,
        category_id: UUID | None = None,
        brand_id: UUID | None = None,
        include_archived: bool = False,
        min_price: object | None = None,
        max_price: object | None = None,
        has_variants: bool | None = None,
        include_cost: bool = False,
        limit: int | None = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        return self.search(
            tenant_id,
            q=None,
            status=status,
            category_id=category_id,
            brand_id=brand_id,
            include_archived=include_archived,
            min_price=min_price,
            max_price=max_price,
            has_variants=has_variants,
            include_cost=include_cost,
            limit=limit,
            cursor=cursor,
        )

    def search(
        self,
        tenant_id: UUID,
        *,
        q: str | None = None,
        status: str | None = None,
        category_id: UUID | None = None,
        brand_id: UUID | None = None,
        include_archived: bool = False,
        min_price: object | None = None,
        max_price: object | None = None,
        has_variants: bool | None = None,
        include_cost: bool = False,
        limit: int | None = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        return self._search.search(
            tenant_id,
            q=q,
            status=status,
            category_id=category_id,
            brand_id=brand_id,
            include_archived=include_archived,
            min_price=min_price,
            max_price=max_price,
            has_variants=has_variants,
            include_cost=include_cost,
            limit=limit,
            cursor=cursor,
        )

    def create(
        self,
        tenant_id: UUID,
        *,
        name: str,
        sku: str | None = None,
        description: str | None = None,
        category_id: UUID | None = None,
        brand: str | None = None,
        brand_id: UUID | None = None,
        price: object | None = None,
        cost: object | None = None,
        tax_rate: object | None = None,
        weight: object | None = None,
        weight_unit: str | None = None,
        status: str | None = None,
        actor: str = "system",
        include_cost: bool = False,
    ) -> dict[str, Any]:
        cleaned_name = _trim(name, max_len=255, field="name")
        if not cleaned_name:
            raise CrmError("invalid_name", "Product name is required")

        display_sku, sku_norm = normalize_sku(sku, required=False)
        category = self._resolve_category(tenant_id, category_id)
        resolved_brand = self._resolve_brand(
            tenant_id, brand_id=brand_id, brand_name=brand, actor=actor
        )
        weight_val, weight_unit_val = parse_weight(weight, weight_unit)

        if sku_norm:
            existing_sku = self._session.scalar(
                select(CatalogSku).where(
                    CatalogSku.tenant_id == tenant_id,
                    CatalogSku.sku_normalized == sku_norm,
                )
            )
            if existing_sku is not None:
                raise CrmError("sku_conflict", "SKU already in use for this tenant")

        product = Product(
            tenant_id=tenant_id,
            name=cleaned_name,
            sku=display_sku,
            sku_normalized=sku_norm,
            description=_trim(description, max_len=20000, field="description"),
            category_id=category.id if category else None,
            brand_id=resolved_brand.id if resolved_brand else None,
            price=parse_money(price, field="price"),
            cost=parse_money(cost, field="cost"),
            tax_rate=parse_tax_rate(tax_rate),
            weight=weight_val,
            weight_unit=weight_unit_val,
            status=self._normalize_status(status),
            created_by=actor,
            updated_by=actor,
        )
        self._session.add(product)
        self._session.flush()

        if display_sku and sku_norm:
            self._skus.claim(
                tenant_id,
                sku=display_sku,
                sku_normalized=sku_norm,
                owner_kind=SKU_OWNER_PRODUCT,
                owner_id=product.id,
            )

        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="product_created",
            resource_ids={"product_id": str(product.id)},
        )
        return self.get(
            tenant_id, product.id, include_cost=include_cost, include_archived=True
        )

    def update(
        self,
        tenant_id: UUID,
        product_id: UUID,
        *,
        actor: str = "system",
        include_cost: bool = False,
        **fields: Any,
    ) -> dict[str, Any]:
        product = self._load(tenant_id, product_id, require_active=True)

        if "name" in fields:
            cleaned_name = _trim(fields["name"], max_len=255, field="name")
            if not cleaned_name:
                raise CrmError("invalid_name", "Product name is required")
            product.name = cleaned_name
        if "description" in fields:
            product.description = _trim(
                fields["description"], max_len=20000, field="description"
            )
        if "sku" in fields:
            display_sku, sku_norm = normalize_sku(fields["sku"], required=False)
            self._skus.transfer(
                tenant_id,
                owner_kind=SKU_OWNER_PRODUCT,
                owner_id=product.id,
                sku=display_sku,
                sku_normalized=sku_norm,
            )
            product.sku = display_sku
            product.sku_normalized = sku_norm
        if "category_id" in fields:
            raw = fields["category_id"]
            cat_id = UUID(str(raw)) if raw is not None else None
            category = self._resolve_category(tenant_id, cat_id)
            product.category_id = category.id if category else None
        if "brand" in fields or "brand_id" in fields:
            brand_name = fields.get("brand") if "brand" in fields else None
            raw_brand_id = fields.get("brand_id") if "brand_id" in fields else None
            brand_id = UUID(str(raw_brand_id)) if raw_brand_id is not None else None
            clear = (
                "brand" in fields and brand_name is None and "brand_id" not in fields
            ) or (
                "brand_id" in fields
                and fields["brand_id"] is None
                and "brand" not in fields
            )
            resolved = self._resolve_brand(
                tenant_id,
                brand_id=brand_id if "brand_id" in fields else None,
                brand_name=brand_name if "brand" in fields else None,
                actor=actor,
                clear=clear,
            )
            product.brand_id = resolved.id if resolved else None
        if "price" in fields:
            product.price = parse_money(fields["price"], field="price")
        if "cost" in fields:
            product.cost = parse_money(fields["cost"], field="cost")
        if "tax_rate" in fields:
            product.tax_rate = parse_tax_rate(fields["tax_rate"])
        if "weight" in fields or "weight_unit" in fields:
            w = fields.get("weight", product.weight)
            u = fields.get("weight_unit", product.weight_unit)
            weight_val, weight_unit_val = parse_weight(w, u)
            product.weight = weight_val
            product.weight_unit = weight_unit_val
        if "status" in fields:
            product.status = self._normalize_status(fields["status"])

        product.updated_by = actor
        product.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="product_updated",
            resource_ids={"product_id": str(product_id)},
        )
        return self.get(
            tenant_id, product_id, include_cost=include_cost, include_archived=True
        )

    def archive(
        self,
        tenant_id: UUID,
        product_id: UUID,
        *,
        actor: str = "system",
        include_cost: bool = False,
    ) -> dict[str, Any]:
        product = self._load(tenant_id, product_id, require_active=False)
        if product.archived_at is None:
            now = datetime.now(UTC)
            product.archived_at = now
            product.status = "INACTIVE"
            product.updated_by = actor
            product.updated_at = now
            # Cascade: free variant SKUs so they can be reused after product archive.
            active_variants = list(
                self._session.scalars(
                    select(ProductVariant).where(
                        ProductVariant.tenant_id == tenant_id,
                        ProductVariant.product_id == product.id,
                        ProductVariant.archived_at.is_(None),
                    )
                ).all()
            )
            for variant in active_variants:
                variant.archived_at = now
                variant.status = "INACTIVE"
                variant.updated_at = now
                self._skus.release(
                    tenant_id, owner_kind=SKU_OWNER_VARIANT, owner_id=variant.id
                )
            self._skus.release(
                tenant_id, owner_kind=SKU_OWNER_PRODUCT, owner_id=product.id
            )
            self._session.flush()
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="product_archived",
                resource_ids={
                    "product_id": str(product_id),
                    "variant_count": str(len(active_variants)),
                },
            )
        return serialize_product(product, include_cost=include_cost)

    def restore(
        self,
        tenant_id: UUID,
        product_id: UUID,
        *,
        actor: str = "system",
        include_cost: bool = False,
    ) -> dict[str, Any]:
        product = self._load(tenant_id, product_id, require_active=False)
        if product.archived_at is not None:
            now = datetime.now(UTC)
            # Claim product + variant SKUs before clearing archived_at so conflicts
            # fail closed without leaving a half-restored product.
            if product.sku and product.sku_normalized:
                self._skus.claim(
                    tenant_id,
                    sku=product.sku,
                    sku_normalized=product.sku_normalized,
                    owner_kind=SKU_OWNER_PRODUCT,
                    owner_id=product.id,
                )
            archived_variants = list(
                self._session.scalars(
                    select(ProductVariant).where(
                        ProductVariant.tenant_id == tenant_id,
                        ProductVariant.product_id == product.id,
                        ProductVariant.archived_at.is_not(None),
                    )
                ).all()
            )
            for variant in archived_variants:
                if variant.sku and variant.sku_normalized:
                    self._skus.claim(
                        tenant_id,
                        sku=variant.sku,
                        sku_normalized=variant.sku_normalized,
                        owner_kind=SKU_OWNER_VARIANT,
                        owner_id=variant.id,
                    )
                variant.archived_at = None
                variant.status = DEFAULT_CATALOG_STATUS
                variant.updated_at = now
            product.archived_at = None
            product.status = DEFAULT_CATALOG_STATUS
            product.updated_by = actor
            product.updated_at = now
            self._session.flush()
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="product_restored",
                resource_ids={
                    "product_id": str(product_id),
                    "variant_count": str(len(archived_variants)),
                },
            )
        return self.get(
            tenant_id, product_id, include_cost=include_cost, include_archived=True
        )

    def upsert_attribute(
        self,
        tenant_id: UUID,
        product_id: UUID,
        *,
        name: str,
        values: list[str],
        sort_order: int = 100,
        actor: str = "system",
    ) -> dict[str, Any]:
        """Create or replace a product option (e.g. Color) and its values."""
        from callbot_platform.crm.products.serialize import serialize_attribute

        product = self._load(tenant_id, product_id, require_active=True)
        cleaned_name = _trim(name, max_len=64, field="attribute")
        if not cleaned_name:
            raise CrmError("invalid_attribute", "Attribute name is required")
        if not values:
            raise CrmError(
                "invalid_attribute", "At least one attribute value is required"
            )
        name_norm = cleaned_name.lower()
        attr = self._session.scalar(
            select(ProductAttribute).where(
                ProductAttribute.tenant_id == tenant_id,
                ProductAttribute.product_id == product.id,
                ProductAttribute.name_normalized == name_norm,
            )
        )
        if attr is None:
            attr = ProductAttribute(
                tenant_id=tenant_id,
                product_id=product.id,
                name=cleaned_name,
                name_normalized=name_norm,
                sort_order=sort_order,
            )
            self._session.add(attr)
            self._session.flush()
        else:
            attr.name = cleaned_name
            attr.sort_order = sort_order

        existing_vals = {
            v.value_normalized: v
            for v in self._session.scalars(
                select(ProductAttributeValue).where(
                    ProductAttributeValue.tenant_id == tenant_id,
                    ProductAttributeValue.attribute_id == attr.id,
                )
            ).all()
        }
        seen: set[str] = set()
        for idx, raw in enumerate(values):
            cleaned = _trim(raw, max_len=128, field="attribute_value")
            if not cleaned:
                continue
            norm = cleaned.lower()
            if norm in seen:
                continue
            seen.add(norm)
            if norm in existing_vals:
                existing_vals[norm].value = cleaned
                existing_vals[norm].sort_order = idx * 10
            else:
                self._session.add(
                    ProductAttributeValue(
                        tenant_id=tenant_id,
                        attribute_id=attr.id,
                        value=cleaned,
                        value_normalized=norm,
                        sort_order=idx * 10,
                    )
                )
        self._session.flush()
        self._session.refresh(attr, attribute_names=["values"])
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="product_attribute_upserted",
            resource_ids={
                "product_id": str(product_id),
                "attribute_id": str(attr.id),
            },
        )
        return serialize_attribute(attr)

    def get_or_create_brand(
        self, tenant_id: UUID, name: str, *, actor: str = "system"
    ) -> ProductBrand:
        cleaned = _trim(name, max_len=128, field="brand")
        if not cleaned:
            raise CrmError("invalid_brand", "Brand name is required")
        normalized = _normalize_brand_name(cleaned)
        existing = self._session.scalar(
            select(ProductBrand).where(
                ProductBrand.tenant_id == tenant_id,
                ProductBrand.name_normalized == normalized,
            )
        )
        if existing is not None:
            if existing.archived_at is not None:
                existing.archived_at = None
                existing.updated_at = datetime.now(UTC)
                self._session.flush()
            return existing
        brand = ProductBrand(
            tenant_id=tenant_id,
            name=cleaned,
            name_normalized=normalized,
        )
        self._session.add(brand)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="product_brand_created",
            resource_ids={"brand_id": str(brand.id)},
        )
        return brand

    def _resolve_brand(
        self,
        tenant_id: UUID,
        *,
        brand_id: UUID | None,
        brand_name: str | None,
        actor: str,
        clear: bool = False,
    ) -> ProductBrand | None:
        if clear:
            return None
        if brand_name is not None:
            return self.get_or_create_brand(tenant_id, brand_name, actor=actor)
        if brand_id is None:
            return None
        brand = self._session.scalar(
            select(ProductBrand).where(
                ProductBrand.id == brand_id,
                ProductBrand.tenant_id == tenant_id,
                ProductBrand.archived_at.is_(None),
            )
        )
        if brand is None:
            raise CrmError("invalid_brand", "Brand not found for tenant")
        return brand

    def _resolve_category(
        self, tenant_id: UUID, category_id: UUID | None
    ) -> ProductCategory | None:
        if category_id is None:
            return None
        category = self._session.scalar(
            select(ProductCategory).where(
                ProductCategory.id == category_id,
                ProductCategory.tenant_id == tenant_id,
                ProductCategory.archived_at.is_(None),
            )
        )
        if category is None:
            raise CrmError("invalid_category", "Category not found or archived")
        return category

    def _load(
        self,
        tenant_id: UUID,
        product_id: UUID,
        *,
        require_active: bool,
        with_details: bool = False,
    ) -> Product:
        q = select(Product).where(
            Product.id == product_id,
            Product.tenant_id == tenant_id,
        )
        if with_details:
            q = q.options(
                selectinload(Product.category),
                selectinload(Product.brand),
                selectinload(Product.variants)
                .selectinload(ProductVariant.attribute_links)
                .selectinload(ProductVariantAttributeValue.attribute_value)
                .selectinload(ProductAttributeValue.attribute),
                selectinload(Product.attributes).selectinload(ProductAttribute.values),
                selectinload(Product.images),
            )
        product = self._session.scalar(q)
        if product is None:
            raise CrmError("not_found", "Product not found for tenant")
        if require_active and product.archived_at is not None:
            raise CrmError("product_archived", "Product is archived")
        return product

    def _normalize_status(self, status: str | None) -> str:
        if status is None:
            return DEFAULT_CATALOG_STATUS
        normalized = str(status).strip().upper()
        if normalized not in CATALOG_STATUSES:
            raise CrmError("invalid_status", "Status must be ACTIVE or INACTIVE")
        return normalized

"""Tenant-scoped product search with ranked, bounded results."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.products.constants import CATALOG_STATUSES
from callbot_platform.crm.products.cursors import ProductCursor, parse_product_page
from callbot_platform.crm.products.normalize import escape_like, normalize_sku
from callbot_platform.crm.products.serialize import serialize_product
from callbot_platform.db.models import (
    CatalogSku,
    Product,
    ProductVariant,
)

_RANK_EXACT_SKU = 1
_RANK_EXACT_NAME = 2
_RANK_SKU_PREFIX = 3
_RANK_NAME_PREFIX = 4
_RANK_CONTAINS = 5


class ProductSearchService:
    def __init__(self, session: Session) -> None:
        self._session = session

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
        try:
            page, decoded = parse_product_page(limit=limit, cursor=cursor)
        except ValueError as exc:
            raise CrmError("invalid_cursor", "Invalid pagination cursor") from exc

        query_text = (q or "").strip()
        if not query_text:
            return self._list_only(
                tenant_id,
                status=status,
                category_id=category_id,
                brand_id=brand_id,
                include_archived=include_archived,
                min_price=min_price,
                max_price=max_price,
                has_variants=has_variants,
                include_cost=include_cost,
                page_limit=page.limit,
                decoded=decoded,
            )

        ranked: dict[UUID, tuple[int, Product]] = {}
        q_lower = query_text.lower()
        sku_probe: str | None = None
        try:
            _, sku_norm = normalize_sku(query_text, required=False)
            sku_probe = sku_norm
        except CrmError:
            sku_probe = query_text.strip().upper() or None

        fetch_limit = page.limit * 3

        if sku_probe:
            # Exact SKU via registry or product / variant columns.
            registry_owner_ids = list(
                self._session.scalars(
                    select(CatalogSku.owner_id).where(
                        CatalogSku.tenant_id == tenant_id,
                        CatalogSku.sku_normalized == sku_probe,
                    )
                ).all()
            )
            product_ids_from_registry: list[UUID] = []
            if registry_owner_ids:
                product_ids_from_registry = list(
                    self._session.scalars(
                        select(Product.id).where(
                            Product.tenant_id == tenant_id,
                            or_(
                                Product.id.in_(registry_owner_ids),
                                Product.id.in_(
                                    select(ProductVariant.product_id).where(
                                        ProductVariant.tenant_id == tenant_id,
                                        ProductVariant.id.in_(registry_owner_ids),
                                    )
                                ),
                            ),
                        )
                    ).all()
                )

            exact_sku_q = self._base_product_query(
                tenant_id,
                status=status,
                category_id=category_id,
                brand_id=brand_id,
                include_archived=include_archived,
                min_price=min_price,
                max_price=max_price,
                has_variants=has_variants,
            ).where(
                or_(
                    Product.sku_normalized == sku_probe,
                    Product.id.in_(product_ids_from_registry)
                    if product_ids_from_registry
                    else Product.id.is_(None),  # no-op false when empty
                    exists(
                        select(ProductVariant.id).where(
                            ProductVariant.tenant_id == tenant_id,
                            ProductVariant.product_id == Product.id,
                            ProductVariant.sku_normalized == sku_probe,
                            ProductVariant.archived_at.is_(None),
                        )
                    ),
                )
            )
            # Fix empty registry list: avoid Product.id.in_([]) which can be problematic
            if not product_ids_from_registry:
                exact_sku_q = self._base_product_query(
                    tenant_id,
                    status=status,
                    category_id=category_id,
                    brand_id=brand_id,
                    include_archived=include_archived,
                    min_price=min_price,
                    max_price=max_price,
                    has_variants=has_variants,
                ).where(
                    or_(
                        Product.sku_normalized == sku_probe,
                        exists(
                            select(ProductVariant.id).where(
                                ProductVariant.tenant_id == tenant_id,
                                ProductVariant.product_id == Product.id,
                                ProductVariant.sku_normalized == sku_probe,
                                ProductVariant.archived_at.is_(None),
                            )
                        ),
                    )
                )

            for product in self._session.scalars(exact_sku_q.limit(fetch_limit)).all():
                ranked[product.id] = (_RANK_EXACT_SKU, product)

            prefix = f"{escape_like(sku_probe)}%"
            sku_prefix_q = self._base_product_query(
                tenant_id,
                status=status,
                category_id=category_id,
                brand_id=brand_id,
                include_archived=include_archived,
                min_price=min_price,
                max_price=max_price,
                has_variants=has_variants,
            ).where(
                or_(
                    and_(
                        Product.sku_normalized.is_not(None),
                        Product.sku_normalized.like(prefix, escape="\\"),
                    ),
                    exists(
                        select(ProductVariant.id).where(
                            ProductVariant.tenant_id == tenant_id,
                            ProductVariant.product_id == Product.id,
                            ProductVariant.sku_normalized.like(prefix, escape="\\"),
                            ProductVariant.archived_at.is_(None),
                        )
                    ),
                    exists(
                        select(CatalogSku.id).where(
                            CatalogSku.tenant_id == tenant_id,
                            CatalogSku.sku_normalized.like(prefix, escape="\\"),
                            or_(
                                and_(
                                    CatalogSku.owner_kind == "product",
                                    CatalogSku.owner_id == Product.id,
                                ),
                                and_(
                                    CatalogSku.owner_kind == "variant",
                                    CatalogSku.owner_id.in_(
                                        select(ProductVariant.id).where(
                                            ProductVariant.tenant_id == tenant_id,
                                            ProductVariant.product_id == Product.id,
                                        )
                                    ),
                                ),
                            ),
                        )
                    ),
                )
            )
            for product in self._session.scalars(sku_prefix_q.limit(fetch_limit)).all():
                ranked.setdefault(product.id, (_RANK_SKU_PREFIX, product))

        name_q = self._base_product_query(
            tenant_id,
            status=status,
            category_id=category_id,
            brand_id=brand_id,
            include_archived=include_archived,
            min_price=min_price,
            max_price=max_price,
            has_variants=has_variants,
        ).where(
            or_(
                func.lower(Product.name) == q_lower,
                func.lower(Product.name).like(f"{escape_like(q_lower)}%", escape="\\"),
                func.lower(Product.name).like(f"%{escape_like(q_lower)}%", escape="\\"),
            )
        )
        for product in self._session.scalars(name_q.limit(fetch_limit)).all():
            if product.id in ranked and ranked[product.id][0] <= _RANK_EXACT_NAME:
                continue
            name_l = (product.name or "").lower()
            if name_l == q_lower:
                ranked[product.id] = (_RANK_EXACT_NAME, product)
            elif name_l.startswith(q_lower):
                ranked.setdefault(product.id, (_RANK_NAME_PREFIX, product))
            else:
                ranked.setdefault(product.id, (_RANK_CONTAINS, product))

        items = sorted(
            ranked.values(),
            key=lambda pair: (
                pair[0],
                -(pair[1].updated_at.timestamp() if pair[1].updated_at else 0),
                str(pair[1].id),
            ),
        )
        ordered = [p for _, p in items]
        if decoded is not None:
            found = False
            after: list[Product] = []
            for product in ordered:
                if found:
                    after.append(product)
                elif product.id == decoded.id:
                    found = True
            ordered = after if found else ordered

        page_items = ordered[: page.limit]
        next_cursor = None
        if len(ordered) > page.limit and page_items:
            last = page_items[-1]
            next_cursor = ProductCursor(updated_at=last.updated_at, id=last.id).encode()

        return {
            "products": [
                serialize_product(p, include_cost=include_cost) for p in page_items
            ],
            "next_cursor": next_cursor,
            "limit": page.limit,
        }

    def _list_only(
        self,
        tenant_id: UUID,
        *,
        status: str | None,
        category_id: UUID | None,
        brand_id: UUID | None,
        include_archived: bool,
        min_price: object | None,
        max_price: object | None,
        has_variants: bool | None,
        include_cost: bool,
        page_limit: int,
        decoded: ProductCursor | None,
    ) -> dict[str, Any]:
        q = self._base_product_query(
            tenant_id,
            status=status,
            category_id=category_id,
            brand_id=brand_id,
            include_archived=include_archived,
            min_price=min_price,
            max_price=max_price,
            has_variants=has_variants,
        )
        if decoded is not None:
            q = q.where(
                or_(
                    Product.updated_at < decoded.updated_at,
                    and_(
                        Product.updated_at == decoded.updated_at,
                        Product.id < decoded.id,
                    ),
                )
            )
        q = q.order_by(Product.updated_at.desc(), Product.id.desc()).limit(
            page_limit + 1
        )
        rows = list(self._session.scalars(q).all())
        next_cursor = None
        if len(rows) > page_limit:
            last = rows[page_limit - 1]
            next_cursor = ProductCursor(updated_at=last.updated_at, id=last.id).encode()
            rows = rows[:page_limit]
        return {
            "products": [serialize_product(p, include_cost=include_cost) for p in rows],
            "next_cursor": next_cursor,
            "limit": page_limit,
        }

    def _base_product_query(
        self,
        tenant_id: UUID,
        *,
        status: str | None,
        category_id: UUID | None,
        brand_id: UUID | None,
        include_archived: bool,
        min_price: object | None,
        max_price: object | None,
        has_variants: bool | None,
    ):
        q = (
            select(Product)
            .where(Product.tenant_id == tenant_id)
            .options(
                selectinload(Product.category),
                selectinload(Product.brand),
                selectinload(Product.variants),
            )
        )
        if not include_archived:
            q = q.where(Product.archived_at.is_(None))
        if status is not None:
            normalized = status.strip().upper()
            if normalized not in CATALOG_STATUSES:
                raise CrmError("invalid_status", "Invalid product status filter")
            q = q.where(Product.status == normalized)
        if category_id is not None:
            q = q.where(Product.category_id == category_id)
        if brand_id is not None:
            q = q.where(Product.brand_id == brand_id)
        if min_price is not None:
            from callbot_platform.crm.products.normalize import parse_money

            floor = parse_money(min_price, field="min_price")
            if floor is not None:
                q = q.where(Product.price.is_not(None), Product.price >= floor)
        if max_price is not None:
            from callbot_platform.crm.products.normalize import parse_money

            ceiling = parse_money(max_price, field="max_price")
            if ceiling is not None:
                q = q.where(Product.price.is_not(None), Product.price <= ceiling)
        if has_variants is True:
            q = q.where(
                exists(
                    select(ProductVariant.id).where(
                        ProductVariant.tenant_id == tenant_id,
                        ProductVariant.product_id == Product.id,
                        ProductVariant.archived_at.is_(None),
                    )
                )
            )
        elif has_variants is False:
            q = q.where(
                ~exists(
                    select(ProductVariant.id).where(
                        ProductVariant.tenant_id == tenant_id,
                        ProductVariant.product_id == Product.id,
                        ProductVariant.archived_at.is_(None),
                    )
                )
            )
        return q

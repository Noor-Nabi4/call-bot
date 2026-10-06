"""Product category CRUD, tree, and archive safeguards."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.products.constants import (
    CATALOG_STATUSES,
    DEFAULT_CATALOG_STATUS,
)
from callbot_platform.crm.products.normalize import slugify
from callbot_platform.crm.products.serialize import serialize_category
from callbot_platform.db.models import Product, ProductCategory
from callbot_platform.telephony.audit import write_audit

_MAX_PARENT_WALK = 20


def _trim(value: str | None, *, max_len: int, field: str) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > max_len:
        raise CrmError(f"invalid_{field}", f"{field} is too long")
    return cleaned


class ProductCategoryService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(
        self,
        tenant_id: UUID,
        *,
        include_archived: bool = False,
        parent_id: UUID | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        q = select(ProductCategory).where(ProductCategory.tenant_id == tenant_id)
        if not include_archived:
            q = q.where(ProductCategory.archived_at.is_(None))
        if parent_id is not None:
            q = q.where(ProductCategory.parent_id == parent_id)
        q = q.order_by(
            ProductCategory.sort_order.asc(),
            ProductCategory.name.asc(),
        ).limit(max(1, min(limit, 500)))
        counts = self._product_counts(tenant_id)
        return [
            serialize_category(row, product_count=counts.get(row.id, 0))
            for row in self._session.scalars(q).all()
        ]

    def get(
        self, tenant_id: UUID, category_id: UUID, *, include_archived: bool = True
    ) -> dict[str, Any]:
        cat = self._load(tenant_id, category_id, require_active=not include_archived)
        counts = self._product_counts(tenant_id, category_ids=[cat.id])
        return serialize_category(cat, product_count=counts.get(cat.id, 0))

    def create(
        self,
        tenant_id: UUID,
        *,
        name: str,
        description: str | None = None,
        parent_id: UUID | None = None,
        status: str | None = None,
        sort_order: int | None = None,
        actor: str = "system",
    ) -> dict[str, Any]:
        cleaned_name = _trim(name, max_len=128, field="name")
        if not cleaned_name:
            raise CrmError("invalid_name", "Category name is required")
        parent = self._resolve_parent(tenant_id, parent_id)
        if parent is not None:
            # New category has no id yet; random sentinel only enforces max depth.
            self._assert_parent_ok(tenant_id, category_id=uuid4(), parent_id=parent.id)
        status_val = self._normalize_status(status)
        order = 100 if sort_order is None else int(sort_order)
        slug = self._unique_slug(tenant_id, cleaned_name)
        cat = ProductCategory(
            tenant_id=tenant_id,
            name=cleaned_name,
            slug=slug,
            description=_trim(description, max_len=10000, field="description"),
            parent_id=parent.id if parent else None,
            status=status_val,
            sort_order=order,
        )
        self._session.add(cat)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="product_category_created",
            resource_ids={"category_id": str(cat.id)},
        )
        return serialize_category(cat, product_count=0)

    def update(
        self,
        tenant_id: UUID,
        category_id: UUID,
        *,
        actor: str = "system",
        **fields: Any,
    ) -> dict[str, Any]:
        cat = self._load(tenant_id, category_id, require_active=True)
        if "name" in fields:
            cleaned_name = _trim(fields["name"], max_len=128, field="name")
            if not cleaned_name:
                raise CrmError("invalid_name", "Category name is required")
            if cleaned_name != cat.name:
                cat.name = cleaned_name
                cat.slug = self._unique_slug(tenant_id, cleaned_name, exclude_id=cat.id)
        if "description" in fields:
            cat.description = _trim(
                fields["description"], max_len=10000, field="description"
            )
        if "status" in fields:
            cat.status = self._normalize_status(fields["status"])
        if "sort_order" in fields and fields["sort_order"] is not None:
            cat.sort_order = int(fields["sort_order"])
        if "parent_id" in fields:
            new_parent_id = fields["parent_id"]
            if new_parent_id is not None:
                new_parent_id = UUID(str(new_parent_id))
            self._assert_parent_ok(
                tenant_id, category_id=cat.id, parent_id=new_parent_id
            )
            parent = self._resolve_parent(tenant_id, new_parent_id)
            cat.parent_id = parent.id if parent else None
        cat.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="product_category_updated",
            resource_ids={"category_id": str(category_id)},
        )
        counts = self._product_counts(tenant_id, category_ids=[cat.id])
        return serialize_category(cat, product_count=counts.get(cat.id, 0))

    def archive(
        self,
        tenant_id: UUID,
        category_id: UUID,
        *,
        reassign_to_category_id: UUID | None = None,
        reassign_products: bool = False,
        actor: str = "system",
    ) -> dict[str, Any]:
        """Archive a category.

        Active children always block. Active products block unless
        ``reassign_products=True`` (target may be ``None`` to clear category_id).
        """
        cat = self._load(tenant_id, category_id, require_active=False)
        if cat.archived_at is not None:
            return serialize_category(cat)

        active_children = self._session.scalar(
            select(func.count())
            .select_from(ProductCategory)
            .where(
                ProductCategory.tenant_id == tenant_id,
                ProductCategory.parent_id == category_id,
                ProductCategory.archived_at.is_(None),
            )
        )
        if active_children and int(active_children) > 0:
            raise CrmError(
                "category_in_use",
                "Category has active child categories; archive or reparent them first",
            )

        active_products = self._session.scalar(
            select(func.count())
            .select_from(Product)
            .where(
                Product.tenant_id == tenant_id,
                Product.category_id == category_id,
                Product.archived_at.is_(None),
            )
        )
        product_count = int(active_products or 0)
        if product_count > 0 and not reassign_products:
            raise CrmError(
                "category_in_use",
                "Category has active products; provide reassignment",
            )

        if product_count > 0:
            target: ProductCategory | None = None
            if reassign_to_category_id is not None:
                if reassign_to_category_id == category_id:
                    raise CrmError(
                        "invalid_category",
                        "Cannot reassign products to the category being archived",
                    )
                target = self._load(
                    tenant_id, reassign_to_category_id, require_active=True
                )
            now = datetime.now(UTC)
            for product in self._session.scalars(
                select(Product).where(
                    Product.tenant_id == tenant_id,
                    Product.category_id == category_id,
                    Product.archived_at.is_(None),
                )
            ).all():
                product.category_id = target.id if target else None
                product.updated_at = now

        cat.archived_at = datetime.now(UTC)
        cat.status = "INACTIVE"
        cat.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="product_category_archived",
            resource_ids={
                "category_id": str(cat.id),
                "reassign_to_category_id": (
                    str(reassign_to_category_id) if reassign_to_category_id else None
                ),
            },
        )
        return serialize_category(cat, product_count=0)

    def restore(
        self, tenant_id: UUID, category_id: UUID, *, actor: str = "system"
    ) -> dict[str, Any]:
        cat = self._load(tenant_id, category_id, require_active=False)
        if cat.archived_at is None:
            return serialize_category(cat)
        if cat.parent_id is not None:
            parent = self._session.scalar(
                select(ProductCategory).where(
                    ProductCategory.id == cat.parent_id,
                    ProductCategory.tenant_id == tenant_id,
                )
            )
            if parent is None or parent.archived_at is not None:
                raise CrmError(
                    "invalid_parent",
                    "Cannot restore category under an archived or missing parent",
                )
        cat.archived_at = None
        cat.status = DEFAULT_CATALOG_STATUS
        cat.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="product_category_restored",
            resource_ids={"category_id": str(category_id)},
        )
        counts = self._product_counts(tenant_id, category_ids=[cat.id])
        return serialize_category(cat, product_count=counts.get(cat.id, 0))

    def tree(self, tenant_id: UUID) -> list[dict[str, Any]]:
        rows = list(
            self._session.scalars(
                select(ProductCategory)
                .where(
                    ProductCategory.tenant_id == tenant_id,
                    ProductCategory.archived_at.is_(None),
                )
                .order_by(
                    ProductCategory.sort_order.asc(),
                    ProductCategory.name.asc(),
                )
            ).all()
        )
        counts = self._product_counts(tenant_id)
        by_id: dict[UUID, dict[str, Any]] = {}
        for row in rows:
            node = serialize_category(row, product_count=counts.get(row.id, 0))
            node["children"] = []
            by_id[row.id] = node
        roots: list[dict[str, Any]] = []
        for row in rows:
            node = by_id[row.id]
            if row.parent_id is not None and row.parent_id in by_id:
                by_id[row.parent_id]["children"].append(node)
            else:
                roots.append(node)
        return roots

    def _load(
        self, tenant_id: UUID, category_id: UUID, *, require_active: bool
    ) -> ProductCategory:
        cat = self._session.scalar(
            select(ProductCategory).where(
                ProductCategory.id == category_id,
                ProductCategory.tenant_id == tenant_id,
            )
        )
        if cat is None:
            raise CrmError("not_found", "Category not found for tenant")
        if require_active and cat.archived_at is not None:
            raise CrmError("not_found", "Category not found for tenant")
        return cat

    def _resolve_parent(
        self, tenant_id: UUID, parent_id: UUID | None
    ) -> ProductCategory | None:
        if parent_id is None:
            return None
        parent = self._session.scalar(
            select(ProductCategory).where(
                ProductCategory.id == parent_id,
                ProductCategory.tenant_id == tenant_id,
            )
        )
        if parent is None:
            raise CrmError("invalid_parent", "Parent category not found for tenant")
        if parent.archived_at is not None:
            raise CrmError("invalid_parent", "Parent category is archived")
        return parent

    def _assert_parent_ok(
        self,
        tenant_id: UUID,
        *,
        category_id: UUID,
        parent_id: UUID | None,
    ) -> None:
        if parent_id is None:
            return
        if parent_id == category_id:
            raise CrmError("invalid_parent", "Category cannot be its own parent")
        current: UUID | None = parent_id
        for _ in range(_MAX_PARENT_WALK):
            if current is None:
                return
            if current == category_id:
                raise CrmError(
                    "category_cycle",
                    "Category parent would create a cycle",
                )
            row = self._session.scalar(
                select(ProductCategory).where(
                    ProductCategory.id == current,
                    ProductCategory.tenant_id == tenant_id,
                )
            )
            if row is None:
                raise CrmError("invalid_parent", "Parent category not found for tenant")
            current = row.parent_id
        raise CrmError("category_cycle", "Category hierarchy exceeds maximum depth")

    def _unique_slug(
        self,
        tenant_id: UUID,
        name: str,
        *,
        exclude_id: UUID | None = None,
    ) -> str:
        base = slugify(name)
        candidate = base
        suffix = 2
        while True:
            q = select(ProductCategory.id).where(
                ProductCategory.tenant_id == tenant_id,
                ProductCategory.slug == candidate,
            )
            if exclude_id is not None:
                q = q.where(ProductCategory.id != exclude_id)
            exists = self._session.scalar(q)
            if exists is None:
                return candidate
            candidate = f"{base}-{suffix}"[:160]
            suffix += 1
            if suffix > 10_000:
                raise CrmError(
                    "invalid_slug", "Unable to allocate unique category slug"
                )

    def _normalize_status(self, status: str | None) -> str:
        if status is None:
            return DEFAULT_CATALOG_STATUS
        normalized = str(status).strip().upper()
        if normalized not in CATALOG_STATUSES:
            raise CrmError("invalid_status", "Status must be ACTIVE or INACTIVE")
        return normalized

    def _product_counts(
        self,
        tenant_id: UUID,
        *,
        category_ids: list[UUID] | None = None,
    ) -> dict[UUID, int]:
        q = (
            select(Product.category_id, func.count())
            .where(
                Product.tenant_id == tenant_id,
                Product.category_id.is_not(None),
                Product.archived_at.is_(None),
            )
            .group_by(Product.category_id)
        )
        if category_ids is not None:
            q = q.where(Product.category_id.in_(category_ids))
        return {
            cat_id: int(count)
            for cat_id, count in self._session.execute(q).all()
            if cat_id is not None
        }

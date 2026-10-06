"""Service category CRUD, tree, and archive safeguards."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.services.constants import DEFAULT_STATUS
from callbot_platform.crm.services.normalize import normalize_status, slugify, trim
from callbot_platform.crm.services.serialize import serialize_category
from callbot_platform.db.models.services import Service, ServiceCategory
from callbot_platform.telephony.audit import write_audit

_MAX_PARENT_WALK = 20


class ServiceCategoryService:
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
        q = select(ServiceCategory).where(ServiceCategory.tenant_id == tenant_id)
        if not include_archived:
            q = q.where(ServiceCategory.archived_at.is_(None))
        if parent_id is not None:
            q = q.where(ServiceCategory.parent_id == parent_id)
        q = q.order_by(
            ServiceCategory.sort_order.asc(),
            ServiceCategory.name.asc(),
        ).limit(max(1, min(limit, 500)))
        counts = self._service_counts(tenant_id)
        return [
            serialize_category(row, service_count=counts.get(row.id, 0))
            for row in self._session.scalars(q).all()
        ]

    def get(
        self, tenant_id: UUID, category_id: UUID, *, include_archived: bool = True
    ) -> dict[str, Any]:
        cat = self._load(tenant_id, category_id, require_active=not include_archived)
        counts = self._service_counts(tenant_id, category_ids=[cat.id])
        return serialize_category(cat, service_count=counts.get(cat.id, 0))

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
        cleaned_name = trim(name, max_len=128, field="name")
        if not cleaned_name:
            raise CrmError("invalid_name", "Category name is required")
        parent = self._resolve_parent(tenant_id, parent_id)
        if parent is not None:
            self._assert_parent_ok(tenant_id, category_id=uuid4(), parent_id=parent.id)
        status_val = normalize_status(status)
        order = 100 if sort_order is None else int(sort_order)
        slug = self._unique_slug(tenant_id, cleaned_name)
        cat = ServiceCategory(
            tenant_id=tenant_id,
            name=cleaned_name,
            slug=slug,
            description=trim(description, max_len=10000, field="description"),
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
            action="service_category_created",
            resource_ids={"category_id": str(cat.id)},
        )
        return serialize_category(cat, service_count=0)

    def update(
        self,
        tenant_id: UUID,
        category_id: UUID,
        *,
        name: str | None = None,
        description: str | None = None,
        parent_id: UUID | None = None,
        clear_parent: bool = False,
        status: str | None = None,
        sort_order: int | None = None,
        actor: str = "system",
    ) -> dict[str, Any]:
        cat = self._load(tenant_id, category_id, require_active=False)
        if cat.archived_at is not None:
            raise CrmError("category_archived", "Cannot update an archived category")
        if name is not None:
            cleaned = trim(name, max_len=128, field="name")
            if not cleaned:
                raise CrmError("invalid_name", "Category name is required")
            if cleaned != cat.name:
                cat.name = cleaned
                cat.slug = self._unique_slug(tenant_id, cleaned, exclude_id=cat.id)
        if description is not None:
            cat.description = trim(description, max_len=10000, field="description")
        if clear_parent:
            cat.parent_id = None
        elif parent_id is not None:
            parent = self._resolve_parent(tenant_id, parent_id)
            assert parent is not None
            self._assert_parent_ok(tenant_id, category_id=cat.id, parent_id=parent.id)
            cat.parent_id = parent.id
        if status is not None:
            cat.status = normalize_status(status)
        if sort_order is not None:
            cat.sort_order = int(sort_order)
        cat.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="service_category_updated",
            resource_ids={"category_id": str(cat.id)},
        )
        counts = self._service_counts(tenant_id, category_ids=[cat.id])
        return serialize_category(cat, service_count=counts.get(cat.id, 0))

    def archive(
        self,
        tenant_id: UUID,
        category_id: UUID,
        *,
        reassign_to_category_id: UUID | None = None,
        reassign_services: bool = False,
        actor: str = "system",
    ) -> dict[str, Any]:
        cat = self._load(tenant_id, category_id, require_active=True)
        child_count = self._session.scalar(
            select(func.count())
            .select_from(ServiceCategory)
            .where(
                ServiceCategory.tenant_id == tenant_id,
                ServiceCategory.parent_id == category_id,
                ServiceCategory.archived_at.is_(None),
            )
        )
        if child_count and child_count > 0:
            raise CrmError(
                "category_has_children",
                "Archive or reparent child categories first",
            )
        service_count = (
            self._session.scalar(
                select(func.count())
                .select_from(Service)
                .where(
                    Service.tenant_id == tenant_id,
                    Service.category_id == category_id,
                    Service.archived_at.is_(None),
                )
            )
            or 0
        )
        if service_count > 0 and not reassign_services:
            raise CrmError(
                "category_in_use",
                "Category has active services; provide reassignment",
            )
        if service_count > 0:
            target: ServiceCategory | None = None
            if reassign_to_category_id is not None:
                if reassign_to_category_id == category_id:
                    raise CrmError(
                        "invalid_category",
                        "Cannot reassign services to the category being archived",
                    )
                target = self._load(
                    tenant_id, reassign_to_category_id, require_active=True
                )
            now = datetime.now(UTC)
            for svc in self._session.scalars(
                select(Service).where(
                    Service.tenant_id == tenant_id,
                    Service.category_id == category_id,
                    Service.archived_at.is_(None),
                )
            ).all():
                svc.category_id = target.id if target else None
                svc.updated_at = now
        cat.archived_at = datetime.now(UTC)
        cat.status = "INACTIVE"
        cat.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="service_category_archived",
            resource_ids={
                "category_id": str(cat.id),
                "reassign_to_category_id": (
                    str(reassign_to_category_id) if reassign_to_category_id else None
                ),
            },
        )
        return serialize_category(cat, service_count=0)

    def restore(
        self, tenant_id: UUID, category_id: UUID, *, actor: str = "system"
    ) -> dict[str, Any]:
        cat = self._load(tenant_id, category_id, require_active=False)
        if cat.archived_at is None:
            return serialize_category(cat)
        if cat.parent_id is not None:
            parent = self._session.scalar(
                select(ServiceCategory).where(
                    ServiceCategory.id == cat.parent_id,
                    ServiceCategory.tenant_id == tenant_id,
                )
            )
            if parent is None or parent.archived_at is not None:
                raise CrmError(
                    "invalid_parent",
                    "Cannot restore category under an archived or missing parent",
                )
        cat.archived_at = None
        cat.status = DEFAULT_STATUS
        cat.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="service_category_restored",
            resource_ids={"category_id": str(category_id)},
        )
        counts = self._service_counts(tenant_id, category_ids=[cat.id])
        return serialize_category(cat, service_count=counts.get(cat.id, 0))

    def tree(self, tenant_id: UUID) -> list[dict[str, Any]]:
        rows = list(
            self._session.scalars(
                select(ServiceCategory)
                .where(
                    ServiceCategory.tenant_id == tenant_id,
                    ServiceCategory.archived_at.is_(None),
                )
                .order_by(
                    ServiceCategory.sort_order.asc(),
                    ServiceCategory.name.asc(),
                )
            ).all()
        )
        counts = self._service_counts(tenant_id)
        by_id: dict[UUID, dict[str, Any]] = {}
        for row in rows:
            node = serialize_category(row, service_count=counts.get(row.id, 0))
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
    ) -> ServiceCategory:
        cat = self._session.scalar(
            select(ServiceCategory).where(
                ServiceCategory.id == category_id,
                ServiceCategory.tenant_id == tenant_id,
            )
        )
        if cat is None:
            raise CrmError("not_found", "Category not found for tenant")
        if require_active and cat.archived_at is not None:
            raise CrmError("not_found", "Category not found for tenant")
        return cat

    def _resolve_parent(
        self, tenant_id: UUID, parent_id: UUID | None
    ) -> ServiceCategory | None:
        if parent_id is None:
            return None
        parent = self._session.scalar(
            select(ServiceCategory).where(
                ServiceCategory.id == parent_id,
                ServiceCategory.tenant_id == tenant_id,
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
                raise CrmError("category_cycle", "Category parent would create a cycle")
            row = self._session.scalar(
                select(ServiceCategory).where(
                    ServiceCategory.id == current,
                    ServiceCategory.tenant_id == tenant_id,
                )
            )
            if row is None:
                raise CrmError("invalid_parent", "Parent category not found for tenant")
            current = row.parent_id
        raise CrmError("invalid_parent", "Category hierarchy is too deep")

    def _unique_slug(
        self, tenant_id: UUID, name: str, *, exclude_id: UUID | None = None
    ) -> str:
        base = slugify(name)
        candidate = base
        n = 2
        while True:
            q = select(ServiceCategory.id).where(
                ServiceCategory.tenant_id == tenant_id,
                ServiceCategory.slug == candidate,
            )
            if exclude_id is not None:
                q = q.where(ServiceCategory.id != exclude_id)
            if self._session.scalar(q) is None:
                return candidate
            candidate = f"{base}-{n}"[:160]
            n += 1

    def _service_counts(
        self,
        tenant_id: UUID,
        *,
        category_ids: list[UUID] | None = None,
    ) -> dict[UUID, int]:
        q = (
            select(Service.category_id, func.count())
            .where(
                Service.tenant_id == tenant_id,
                Service.archived_at.is_(None),
                Service.category_id.is_not(None),
            )
            .group_by(Service.category_id)
        )
        if category_ids is not None:
            q = q.where(Service.category_id.in_(category_ids))
        return {cid: int(cnt) for cid, cnt in self._session.execute(q).all() if cid}

"""Authorization resolution — member roles → permissions → scope."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from callbot_platform.rbac.catalog import (
    AI_TOOL_PERMISSIONS,
    LEGACY_ROLE_MAP,
    SCOPE_ALL,
    SCOPE_ASSIGNED,
    SCOPE_OWN,
    SCOPE_TEAM,
    SYSTEM_ROLE_AI_AGENT,
    SYSTEM_TO_LEGACY,
    VALID_SCOPES,
)
from callbot_platform.rbac.errors import RbacError
from callbot_platform.rbac.models import (
    MemberRole,
    OrganizationRole,
    Permission,
    RolePermission,
)
from callbot_platform.rbac.seed import ensure_system_roles_for_tenant

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class GrantedPermission:
    key: str
    scope: str


@dataclass(frozen=True, slots=True)
class ResourceContext:
    """Optional resource facts for scope evaluation."""

    tenant_id: UUID
    owner_user_id: UUID | None = None
    assigned_technician_user_id: UUID | None = None
    team_user_ids: frozenset[UUID] | None = None


class AuthorizationService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._cache: dict[tuple[UUID, UUID], frozenset[GrantedPermission]] = {}

    def invalidate_member(self, tenant_user_id: UUID) -> None:
        keys = [k for k in self._cache if k[1] == tenant_user_id]
        for k in keys:
            del self._cache[k]

    def invalidate_tenant(self, tenant_id: UUID) -> None:
        keys = [k for k in self._cache if k[0] == tenant_id]
        for k in keys:
            del self._cache[k]

    def list_permissions_catalog(self) -> list[dict[str, Any]]:
        rows = self._session.scalars(
            select(Permission).order_by(Permission.resource, Permission.action)
        ).all()
        return [
            {
                "id": str(r.id),
                "key": r.key,
                "resource": r.resource,
                "action": r.action,
                "description": r.description,
            }
            for r in rows
        ]

    def resolve_member_permissions(
        self, tenant_id: UUID, tenant_user_id: UUID
    ) -> frozenset[GrantedPermission]:
        cache_key = (tenant_id, tenant_user_id)
        if cache_key in self._cache:
            return self._cache[cache_key]

        from callbot_platform.db.models.jobs import TenantUser

        user = self._session.scalar(
            select(TenantUser).where(
                TenantUser.id == tenant_user_id,
                TenantUser.tenant_id == tenant_id,
            )
        )
        if user is None or not user.is_active:
            self._cache[cache_key] = frozenset()
            return frozenset()

        rows = (
            self._session.scalars(
                select(RolePermission)
                .join(OrganizationRole, RolePermission.role_id == OrganizationRole.id)
                .join(MemberRole, MemberRole.role_id == OrganizationRole.id)
                .join(Permission, RolePermission.permission_id == Permission.id)
                .where(
                    MemberRole.tenant_user_id == tenant_user_id,
                    OrganizationRole.tenant_id == tenant_id,
                    OrganizationRole.is_active.is_(True),
                )
                .options(joinedload(RolePermission.permission))
            )
            .unique()
            .all()
        )

        granted: set[GrantedPermission] = set()
        for rp in rows:
            if rp.permission is None:
                continue
            scope = rp.scope if rp.scope in VALID_SCOPES else SCOPE_ALL
            granted.add(GrantedPermission(key=rp.permission.key, scope=scope))

        # Compatibility: if no member_roles yet, map legacy string role.
        if not granted and user.role:
            system_name = LEGACY_ROLE_MAP.get(user.role)
            if system_name:
                ensure_system_roles_for_tenant(self._session, tenant_id)
                role = self._session.scalar(
                    select(OrganizationRole).where(
                        OrganizationRole.tenant_id == tenant_id,
                        OrganizationRole.name == system_name,
                        OrganizationRole.is_active.is_(True),
                    )
                )
                if role is not None:
                    for rp in self._session.scalars(
                        select(RolePermission)
                        .where(RolePermission.role_id == role.id)
                        .options(joinedload(RolePermission.permission))
                    ).all():
                        if rp.permission is None:
                            continue
                        scope = rp.scope if rp.scope in VALID_SCOPES else SCOPE_ALL
                        granted.add(
                            GrantedPermission(key=rp.permission.key, scope=scope)
                        )

        result = frozenset(granted)
        self._cache[cache_key] = result
        return result

    def has_permission(
        self,
        tenant_id: UUID,
        tenant_user_id: UUID,
        permission_key: str,
        *,
        resource: ResourceContext | None = None,
    ) -> bool:
        grants = self.resolve_member_permissions(tenant_id, tenant_user_id)
        matching = [g for g in grants if g.key == permission_key]
        if not matching:
            return False

        has_org_wide = any(g.scope == SCOPE_ALL for g in matching)
        scoped_only = [g for g in matching if g.scope != SCOPE_ALL]

        # Organization-wide grant: allow list/create without a resource; with a
        # resource, still require matching tenant.
        if has_org_wide:
            if resource is None:
                return True
            return resource.tenant_id == tenant_id

        # Scoped grants (OWN / ASSIGNED / TEAM) fail closed without context.
        if resource is None:
            return False
        if resource.tenant_id != tenant_id:
            return False
        for g in scoped_only:
            if self._scope_allows(g.scope, tenant_user_id, resource):
                return True
        return False

    def list_access_mode(
        self,
        tenant_id: UUID,
        tenant_user_id: UUID,
        permission_key: str,
    ) -> str | None:
        """How a list endpoint should filter: ``all``, ``assigned``, or None (deny)."""
        grants = [
            g
            for g in self.resolve_member_permissions(tenant_id, tenant_user_id)
            if g.key == permission_key
        ]
        if not grants:
            return None
        if any(g.scope == SCOPE_ALL for g in grants):
            return "all"
        if any(g.scope == SCOPE_ASSIGNED for g in grants):
            return "assigned"
        # OWN/TEAM without list semantics → deny rather than over-expose.
        return None

    def require_permission(
        self,
        tenant_id: UUID,
        tenant_user_id: UUID,
        permission_key: str,
        *,
        resource: ResourceContext | None = None,
    ) -> None:
        if not self.has_permission(
            tenant_id, tenant_user_id, permission_key, resource=resource
        ):
            raise RbacError(
                "permission_denied",
                f"Missing permission: {permission_key}",
            )

    def _scope_allows(
        self, scope: str, actor_user_id: UUID, resource: ResourceContext
    ) -> bool:
        if scope == SCOPE_ALL:
            return True
        if scope == SCOPE_OWN:
            return (
                resource.owner_user_id is not None
                and resource.owner_user_id == actor_user_id
            )
        if scope == SCOPE_ASSIGNED:
            return (
                resource.assigned_technician_user_id is not None
                and resource.assigned_technician_user_id == actor_user_id
            )
        if scope == SCOPE_TEAM:
            if resource.team_user_ids is None:
                return False
            return actor_user_id in resource.team_user_ids
        return False

    def member_role_names(self, tenant_id: UUID, tenant_user_id: UUID) -> list[str]:
        rows = self._session.scalars(
            select(OrganizationRole)
            .join(MemberRole, MemberRole.role_id == OrganizationRole.id)
            .where(
                MemberRole.tenant_user_id == tenant_user_id,
                OrganizationRole.tenant_id == tenant_id,
                OrganizationRole.is_active.is_(True),
            )
            .order_by(OrganizationRole.name)
        ).all()
        return [r.name for r in rows]

    def primary_legacy_role(self, tenant_id: UUID, tenant_user_id: UUID) -> str | None:
        """Best-effort legacy string for JWT / UI during compatibility period."""
        names = self.member_role_names(tenant_id, tenant_user_id)
        priority = [
            "Owner",
            "Admin",
            "Manager",
            "Dispatcher",
            "CSR",
            "Accountant",
            "Technician",
        ]
        for name in priority:
            if name in names:
                return SYSTEM_TO_LEGACY.get(name)
        if names:
            return SYSTEM_TO_LEGACY.get(names[0], "dispatcher")
        return None

    def check_ai_tool(
        self,
        tenant_id: UUID,
        tool_group: str,
    ) -> None:
        """Authorize AI tool groups via the org AI Agent system role."""
        ensure_system_roles_for_tenant(self._session, tenant_id)
        perm_key = AI_TOOL_PERMISSIONS.get(tool_group)
        if perm_key is None:
            raise RbacError(
                "unknown_tool_group",
                f"Unknown AI tool group: {tool_group}",
            )
        role = self._session.scalar(
            select(OrganizationRole).where(
                OrganizationRole.tenant_id == tenant_id,
                OrganizationRole.name == SYSTEM_ROLE_AI_AGENT,
                OrganizationRole.is_active.is_(True),
            )
        )
        if role is None:
            raise RbacError("permission_denied", f"Missing permission: {perm_key}")
        rows = self._session.scalars(
            select(RolePermission)
            .join(Permission, RolePermission.permission_id == Permission.id)
            .where(
                RolePermission.role_id == role.id,
                Permission.resource == perm_key.split(".", 1)[0],
                Permission.action == perm_key.split(".", 1)[1],
            )
        ).all()
        if not rows:
            logger.warning(
                "ai_tool_denied tenant_id=%s tool_group=%s permission=%s",
                tenant_id,
                tool_group,
                perm_key,
            )
            raise RbacError("permission_denied", f"Missing permission: {perm_key}")

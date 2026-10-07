"""Seed and ensure org system roles / permission catalog."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from callbot_platform.rbac.catalog import (
    LEGACY_ROLE_MAP,
    PERMISSION_CATALOG,
    SOURCE_SYSTEM_DEFAULT,
    SYSTEM_ROLE_ADMIN,
    SYSTEM_ROLE_AI_AGENT,
    SYSTEM_ROLE_NAMES,
    SYSTEM_ROLE_OWNER,
    default_role_permissions,
    permission_key,
)
from callbot_platform.rbac.models import (
    MemberRole,
    OrganizationRole,
    Permission,
    RolePermission,
)

logger = logging.getLogger(__name__)


def ensure_permission_catalog(
    session: Session,
) -> tuple[dict[str, Permission], frozenset[str]]:
    """Upsert platform permissions; return (key→Permission, newly_created_keys)."""
    by_key: dict[str, Permission] = {}
    newly_created: set[str] = set()
    for resource, action, description in PERMISSION_CATALOG:
        key = permission_key(resource, action)
        row = session.scalar(
            select(Permission).where(
                Permission.resource == resource, Permission.action == action
            )
        )
        if row is None:
            row = Permission(resource=resource, action=action, description=description)
            session.add(row)
            session.flush()
            newly_created.add(key)
        elif row.description != description:
            row.description = description
        by_key[key] = row
    session.flush()
    return by_key, frozenset(newly_created)


def ensure_system_roles_for_tenant(
    session: Session, tenant_id: UUID
) -> dict[str, OrganizationRole]:
    """Create missing system roles and default permissions for one tenant."""
    perms, newly_created = ensure_permission_catalog(session)
    roles: dict[str, OrganizationRole] = {}
    for name in SYSTEM_ROLE_NAMES:
        role = session.scalar(
            select(OrganizationRole).where(
                OrganizationRole.tenant_id == tenant_id,
                OrganizationRole.name == name,
            )
        )
        if role is None:
            role = OrganizationRole(
                tenant_id=tenant_id,
                name=name,
                description=f"System role: {name}",
                is_system=True,
                is_active=True,
            )
            session.add(role)
            session.flush()
            for perm_key, scope in default_role_permissions(name):
                perm = perms.get(perm_key)
                if perm is None:
                    continue
                session.add(
                    RolePermission(
                        role_id=role.id,
                        permission_id=perm.id,
                        scope=scope,
                        source=SOURCE_SYSTEM_DEFAULT,
                    )
                )
            session.flush()
        elif newly_created:
            # Only attach brand-new catalog permissions; never restore revoked ones.
            existing = {
                rp.permission.key
                for rp in session.scalars(
                    select(RolePermission)
                    .where(RolePermission.role_id == role.id)
                    .options(joinedload(RolePermission.permission))
                ).all()
                if rp.permission is not None
            }
            added = False
            for perm_key, scope in default_role_permissions(name):
                if perm_key not in newly_created or perm_key in existing:
                    continue
                perm = perms.get(perm_key)
                if perm is None:
                    continue
                session.add(
                    RolePermission(
                        role_id=role.id,
                        permission_id=perm.id,
                        scope=scope,
                        source=SOURCE_SYSTEM_DEFAULT,
                    )
                )
                added = True
            if added:
                session.flush()
        # Additive AI Agent template keys introduced after initial seed (do not
        # re-grant keys an org intentionally revoked outside this set).
        if name == SYSTEM_ROLE_AI_AGENT:
            existing_keys = {
                rp.permission.key
                for rp in session.scalars(
                    select(RolePermission)
                    .where(RolePermission.role_id == role.id)
                    .options(joinedload(RolePermission.permission))
                ).all()
                if rp.permission is not None
            }
            template = dict(default_role_permissions(SYSTEM_ROLE_AI_AGENT))
            for perm_key in ("products.read",):
                if perm_key in existing_keys or perm_key not in template:
                    continue
                perm = perms.get(perm_key)
                if perm is None:
                    continue
                session.add(
                    RolePermission(
                        role_id=role.id,
                        permission_id=perm.id,
                        scope=template[perm_key],
                        source=SOURCE_SYSTEM_DEFAULT,
                    )
                )
                session.flush()
        roles[name] = role
    return roles


def assign_member_system_role(
    session: Session,
    *,
    tenant_id: UUID,
    tenant_user_id: UUID,
    system_role_name: str,
) -> None:
    roles = ensure_system_roles_for_tenant(session, tenant_id)
    role = roles.get(system_role_name)
    if role is None:
        return
    existing = session.scalar(
        select(MemberRole).where(
            MemberRole.tenant_user_id == tenant_user_id,
            MemberRole.role_id == role.id,
        )
    )
    if existing is None:
        session.add(MemberRole(tenant_user_id=tenant_user_id, role_id=role.id))
        session.flush()


def sync_legacy_primary_role(
    session: Session,
    *,
    tenant_id: UUID,
    tenant_user_id: UUID,
    legacy_role: str,
) -> None:
    """Replace Admin/Dispatcher/Technician assignments with the mapped system role.

    Does not add or remove Owner — Owner is managed only via RBAC role APIs.
    Custom roles are left intact.
    """
    from callbot_platform.rbac.catalog import (
        SYSTEM_ROLE_ADMIN,
        SYSTEM_ROLE_DISPATCHER,
        SYSTEM_ROLE_OWNER,
        SYSTEM_ROLE_TECHNICIAN,
    )

    target = LEGACY_ROLE_MAP.get(legacy_role)
    if target is None:
        return
    roles = ensure_system_roles_for_tenant(session, tenant_id)
    replaceable = {
        SYSTEM_ROLE_ADMIN,
        SYSTEM_ROLE_DISPATCHER,
        SYSTEM_ROLE_TECHNICIAN,
    }
    # If the member is Owner, refuse to demote via the legacy string field.
    owner_role = roles.get(SYSTEM_ROLE_OWNER)
    if owner_role is not None and target != SYSTEM_ROLE_ADMIN:
        has_owner = session.scalar(
            select(MemberRole).where(
                MemberRole.tenant_user_id == tenant_user_id,
                MemberRole.role_id == owner_role.id,
            )
        )
        if has_owner is not None:
            from callbot_platform.rbac.errors import RbacError

            raise RbacError(
                "owner_protected",
                "Cannot demote an Owner via legacy role; remove Owner via role assignment",
            )

    for name in replaceable:
        role = roles.get(name)
        if role is None:
            continue
        link = session.scalar(
            select(MemberRole).where(
                MemberRole.tenant_user_id == tenant_user_id,
                MemberRole.role_id == role.id,
            )
        )
        if link is not None and name != target:
            session.delete(link)
    session.flush()
    assign_member_system_role(
        session,
        tenant_id=tenant_id,
        tenant_user_id=tenant_user_id,
        system_role_name=target,
    )


def migrate_legacy_user_role(
    session: Session,
    *,
    tenant_id: UUID,
    tenant_user_id: UUID,
    legacy_role: str,
    promote_to_owner: bool = False,
) -> None:
    system_name = (
        SYSTEM_ROLE_OWNER
        if promote_to_owner
        else LEGACY_ROLE_MAP.get(legacy_role, SYSTEM_ROLE_ADMIN)
    )
    assign_member_system_role(
        session,
        tenant_id=tenant_id,
        tenant_user_id=tenant_user_id,
        system_role_name=system_name,
    )


def backfill_tenant_rbac(session: Session, tenant_id: UUID) -> None:
    """Ensure system roles and migrate all tenant_users for one tenant."""
    from callbot_platform.db.models.jobs import TenantUser

    ensure_system_roles_for_tenant(session, tenant_id)
    users = list(
        session.scalars(
            select(TenantUser)
            .where(TenantUser.tenant_id == tenant_id)
            .order_by(TenantUser.created_at.asc())
        )
    )
    owner_assigned = False
    for user in users:
        # Earliest active admin becomes Owner (protected); others keep Admin.
        promote = False
        if not owner_assigned and user.role == "admin" and user.is_active:
            promote = True
            owner_assigned = True
        migrate_legacy_user_role(
            session,
            tenant_id=tenant_id,
            tenant_user_id=user.id,
            legacy_role=user.role,
            promote_to_owner=promote,
        )
    # Ensure AI Agent system role exists even with no members.
    ensure_system_roles_for_tenant(session, tenant_id)
    from callbot_platform.rbac.reconcile import reconcile_system_roles_for_tenant

    reconcile_system_roles_for_tenant(session, tenant_id, actor="rbac_backfill")
    logger.info(
        "rbac_backfill_complete tenant_id=%s members=%s owner_assigned=%s",
        tenant_id,
        len(users),
        owner_assigned,
    )


def backfill_all_tenants(session: Session) -> int:
    from callbot_platform.db.models.tenant import Tenant

    ensure_permission_catalog(session)
    tenants = list(session.scalars(select(Tenant)))
    for tenant in tenants:
        backfill_tenant_rbac(session, tenant.id)
    return len(tenants)

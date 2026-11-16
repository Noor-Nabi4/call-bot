"""Idempotent system-role RBAC reconciliation.

Adds missing SYSTEM_DEFAULT grants for system roles only.
Never restores tombstoned (intentionally revoked) defaults.
Never modifies custom roles or ORG_CUSTOM grant scopes.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from callbot_platform.rbac.catalog import (
    SOURCE_SYSTEM_DEFAULT,
    SYSTEM_ROLE_NAMES,
    default_role_permissions,
)
from callbot_platform.rbac.models import (
    OrganizationRole,
    RolePermission,
    RolePermissionTombstone,
)
from callbot_platform.rbac.seed import (
    ensure_permission_catalog,
    ensure_system_roles_for_tenant,
)
from callbot_platform.telephony.audit import write_audit

logger = logging.getLogger(__name__)


def freeze_system_role_gaps_for_tenant(
    session: Session,
    tenant_id: UUID,
    *,
    skip_permission_keys: frozenset[str] | set[str] | None = None,
) -> int:
    """Tombstone missing system defaults so they are not restored by reconcile.

    Used once during upgrades so pre-tombstone customizations survive.
    Permissions in ``skip_permission_keys`` (typically newly created catalog
    entries) are left without tombstones so reconcile can grant them.
    """
    skip = frozenset(skip_permission_keys or ())
    perms, _ = ensure_permission_catalog(session)
    ensure_system_roles_for_tenant(session, tenant_id)
    frozen = 0
    roles = list(
        session.scalars(
            select(OrganizationRole).where(
                OrganizationRole.tenant_id == tenant_id,
                OrganizationRole.is_system.is_(True),
            )
        ).all()
    )
    for role in roles:
        if role.name not in SYSTEM_ROLE_NAMES:
            continue
        existing_keys = {
            rp.permission.key
            for rp in session.scalars(
                select(RolePermission)
                .where(RolePermission.role_id == role.id)
                .options(joinedload(RolePermission.permission))
            ).all()
            if rp.permission is not None
        }
        tombstoned = {
            t.permission_id
            for t in session.scalars(
                select(RolePermissionTombstone).where(
                    RolePermissionTombstone.role_id == role.id
                )
            ).all()
        }
        for perm_key, _scope in default_role_permissions(role.name):
            if perm_key in skip or perm_key in existing_keys:
                continue
            perm = perms.get(perm_key)
            if perm is None or perm.id in tombstoned:
                continue
            session.add(
                RolePermissionTombstone(
                    role_id=role.id,
                    permission_id=perm.id,
                )
            )
            frozen += 1
            tombstoned.add(perm.id)
    if frozen:
        session.flush()
        logger.info(
            "rbac_gaps_frozen tenant_id=%s tombstones=%s",
            tenant_id,
            frozen,
        )
    return frozen


def reconcile_system_roles_for_tenant(
    session: Session,
    tenant_id: UUID,
    *,
    actor: str = "system",
) -> dict[str, Any]:
    """Ensure system roles exist and receive only legitimate missing defaults."""
    perms, _newly = ensure_permission_catalog(session)
    ensure_system_roles_for_tenant(session, tenant_id)

    added: list[dict[str, str]] = []
    roles = list(
        session.scalars(
            select(OrganizationRole).where(
                OrganizationRole.tenant_id == tenant_id,
                OrganizationRole.is_system.is_(True),
            )
        ).all()
    )

    for role in roles:
        if role.name not in SYSTEM_ROLE_NAMES:
            continue
        tombstoned_ids = {
            t.permission_id
            for t in session.scalars(
                select(RolePermissionTombstone).where(
                    RolePermissionTombstone.role_id == role.id
                )
            ).all()
        }
        existing = {
            rp.permission.key: rp
            for rp in session.scalars(
                select(RolePermission)
                .where(RolePermission.role_id == role.id)
                .options(joinedload(RolePermission.permission))
            ).all()
            if rp.permission is not None
        }

        for perm_key, scope in default_role_permissions(role.name):
            if perm_key in existing:
                # Preserve existing scopes and sources (custom or default).
                continue
            perm = perms.get(perm_key)
            if perm is None:
                continue
            if perm.id in tombstoned_ids:
                continue
            session.add(
                RolePermission(
                    role_id=role.id,
                    permission_id=perm.id,
                    scope=scope,
                    source=SOURCE_SYSTEM_DEFAULT,
                )
            )
            added.append(
                {
                    "role": role.name,
                    "permission": perm_key,
                    "scope": scope,
                }
            )
            write_audit(
                session,
                tenant_id=tenant_id,
                actor=actor,
                action="ROLE_PERMISSION_GRANTED",
                resource_ids={
                    "role_id": str(role.id),
                    "permission": perm_key,
                    "scope": scope,
                    "source": SOURCE_SYSTEM_DEFAULT,
                    "reconcile": True,
                },
            )

    if added:
        session.flush()
        from callbot_platform.rbac.service import AuthorizationService

        AuthorizationService(session).invalidate_tenant(tenant_id)
        logger.info(
            "rbac_reconcile_applied tenant_id=%s added=%s actor=%s",
            tenant_id,
            len(added),
            actor,
        )
    else:
        logger.debug(
            "rbac_reconcile_noop tenant_id=%s actor=%s",
            tenant_id,
            actor,
        )

    return {
        "tenant_id": str(tenant_id),
        "added": added,
        "added_count": len(added),
    }


def reconcile_all_tenants(
    session: Session,
    *,
    actor: str = "system",
    freeze_existing_gaps: bool = False,
) -> dict[str, Any]:
    """Reconcile every tenant. Optionally freeze gaps before granting."""
    # Raw SQL avoids ORM Tenant maps that expect columns from later migrations.
    from sqlalchemy import text

    _perms, newly = ensure_permission_catalog(session)
    newly_keys = frozenset(newly)
    tenant_ids = list(session.scalars(text("SELECT id FROM tenants")))
    results = []
    total_added = 0
    total_frozen = 0
    for tenant_id in tenant_ids:
        if freeze_existing_gaps:
            total_frozen += freeze_system_role_gaps_for_tenant(
                session,
                tenant_id,
                skip_permission_keys=newly_keys,
            )
        result = reconcile_system_roles_for_tenant(session, tenant_id, actor=actor)
        results.append(result)
        total_added += int(result["added_count"])
    return {
        "tenants": len(tenant_ids),
        "added_count": total_added,
        "frozen_count": total_frozen,
        "results": results,
    }

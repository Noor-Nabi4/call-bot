"""Organization-managed RBAC package."""

from __future__ import annotations

from callbot_platform.rbac.catalog import (
    AI_TOOL_PERMISSIONS,
    LEGACY_ROLE_MAP,
    PERMISSION_CATALOG,
    SYSTEM_ROLE_NAMES,
    VALID_SCOPES,
)
from callbot_platform.rbac.errors import RbacError
from callbot_platform.rbac.models import RolePermissionTombstone
from callbot_platform.rbac.reconcile import (
    reconcile_all_tenants,
    reconcile_system_roles_for_tenant,
)
from callbot_platform.rbac.repos import RoleRepository
from callbot_platform.rbac.seed import (
    backfill_all_tenants,
    backfill_tenant_rbac,
    ensure_permission_catalog,
    ensure_system_roles_for_tenant,
)
from callbot_platform.rbac.service import AuthorizationService, ResourceContext

__all__ = [
    "AI_TOOL_PERMISSIONS",
    "LEGACY_ROLE_MAP",
    "PERMISSION_CATALOG",
    "SYSTEM_ROLE_NAMES",
    "VALID_SCOPES",
    "AuthorizationService",
    "RbacError",
    "ResourceContext",
    "RolePermissionTombstone",
    "RoleRepository",
    "backfill_all_tenants",
    "backfill_tenant_rbac",
    "ensure_permission_catalog",
    "ensure_system_roles_for_tenant",
    "reconcile_all_tenants",
    "reconcile_system_roles_for_tenant",
]

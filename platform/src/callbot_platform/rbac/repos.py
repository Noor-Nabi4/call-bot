"""Organization role management repository."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from callbot_platform.db.models.jobs import TenantUser
from callbot_platform.rbac.catalog import (
    OWNER_ONLY_PERMISSIONS,
    PROTECTED_SYSTEM_ROLES,
    SCOPE_ALL,
    SYSTEM_ROLE_OWNER,
    VALID_SCOPES,
    all_permission_keys,
)
from callbot_platform.rbac.errors import RbacError
from callbot_platform.rbac.models import (
    MemberRole,
    OrganizationRole,
    Permission,
    RolePermission,
)
from callbot_platform.rbac.seed import ensure_system_roles_for_tenant
from callbot_platform.telephony.audit import write_audit

logger = logging.getLogger(__name__)


class RoleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_roles(self, tenant_id: UUID) -> list[dict[str, Any]]:
        ensure_system_roles_for_tenant(self._session, tenant_id)
        rows = self._session.scalars(
            select(OrganizationRole)
            .where(OrganizationRole.tenant_id == tenant_id)
            .order_by(OrganizationRole.is_system.desc(), OrganizationRole.name)
        ).all()
        return [self._serialize_role(r, include_permissions=False) for r in rows]

    def get_role(self, tenant_id: UUID, role_id: UUID) -> dict[str, Any]:
        role = self._require_role(tenant_id, role_id)
        return self._serialize_role(role, include_permissions=True)

    def create_role(
        self,
        tenant_id: UUID,
        *,
        name: str,
        description: str | None,
        permissions: list[dict[str, str]] | None,
        actor: str,
        actor_user_id: UUID,
    ) -> dict[str, Any]:
        cleaned = name.strip()
        if not cleaned or len(cleaned) > 128:
            raise RbacError("invalid_name", "Role name is required (max 128)")
        if cleaned in PROTECTED_SYSTEM_ROLES or cleaned in {
            "Owner",
            "Admin",
            "Manager",
            "Dispatcher",
            "Technician",
            "CSR",
            "Accountant",
            "AI Agent",
        }:
            raise RbacError(
                "reserved_role_name",
                "Cannot create a role with a reserved system name",
            )
        existing = self._session.scalar(
            select(OrganizationRole).where(
                OrganizationRole.tenant_id == tenant_id,
                OrganizationRole.name == cleaned,
            )
        )
        if existing is not None:
            raise RbacError("role_name_taken", "A role with that name already exists")

        role = OrganizationRole(
            tenant_id=tenant_id,
            name=cleaned,
            description=(description or "").strip() or None,
            is_system=False,
            is_active=True,
        )
        self._session.add(role)
        self._session.flush()
        if permissions:
            self._replace_permissions(
                tenant_id,
                role,
                permissions,
                actor_user_id=actor_user_id,
                allow_owner_only=False,
            )
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="ROLE_CREATED",
            resource_ids={"role_id": str(role.id), "name": role.name},
        )
        return self._serialize_role(role, include_permissions=True)

    def update_role(
        self,
        tenant_id: UUID,
        role_id: UUID,
        *,
        actor: str,
        actor_user_id: UUID,
        name: str | None = None,
        description: str | None = None,
        is_active: bool | None = None,
        permissions: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        role = self._require_role(tenant_id, role_id)
        changed: list[str] = []

        if role.is_system and name is not None and name.strip() != role.name:
            raise RbacError(
                "system_role_protected",
                "System role names cannot be changed",
            )
        if role.name == SYSTEM_ROLE_OWNER and (
            is_active is False or permissions is not None
        ):
            raise RbacError(
                "owner_protected",
                "Owner role permissions and status cannot be modified",
            )
        if (
            role.is_system
            and role.name in PROTECTED_SYSTEM_ROLES
            and is_active is False
        ):
            raise RbacError(
                "system_role_protected",
                "Protected system roles cannot be deactivated",
            )

        if name is not None and not role.is_system:
            cleaned = name.strip()
            if not cleaned:
                raise RbacError("invalid_name", "Role name is required")
            other = self._session.scalar(
                select(OrganizationRole).where(
                    OrganizationRole.tenant_id == tenant_id,
                    OrganizationRole.name == cleaned,
                    OrganizationRole.id != role.id,
                )
            )
            if other is not None:
                raise RbacError(
                    "role_name_taken", "A role with that name already exists"
                )
            if cleaned != role.name:
                role.name = cleaned
                changed.append("name")

        if description is not None:
            role.description = description.strip() or None
            changed.append("description")

        if is_active is not None and is_active != role.is_active:
            if not is_active and role.is_system:
                raise RbacError(
                    "system_role_protected",
                    "System roles cannot be deactivated; remove member assignments instead",
                )
            role.is_active = is_active
            changed.append("is_active")

        if permissions is not None:
            if role.name == SYSTEM_ROLE_OWNER:
                raise RbacError("owner_protected", "Owner permissions are fixed")
            self._replace_permissions(
                tenant_id,
                role,
                permissions,
                actor_user_id=actor_user_id,
                allow_owner_only=self._actor_is_owner(tenant_id, actor_user_id),
            )
            changed.append("permissions")

        if not changed:
            return self._serialize_role(role, include_permissions=True)

        role.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="ROLE_UPDATED" if is_active is not False else "ROLE_DEACTIVATED",
            resource_ids={
                "role_id": str(role.id),
                "changed_fields": changed,
            },
        )
        return self._serialize_role(role, include_permissions=True)

    def delete_role(
        self, tenant_id: UUID, role_id: UUID, *, actor: str
    ) -> dict[str, Any]:
        role = self._require_role(tenant_id, role_id)
        if role.is_system:
            raise RbacError(
                "system_role_protected",
                "System roles cannot be deleted",
            )
        role_id_str = str(role.id)
        name = role.name
        self._session.delete(role)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="ROLE_DELETED",
            resource_ids={"role_id": role_id_str, "name": name},
        )
        return {"deleted": True, "id": role_id_str}

    def assign_role(
        self,
        tenant_id: UUID,
        *,
        member_id: UUID,
        role_id: UUID,
        actor: str,
        actor_user_id: UUID,
    ) -> dict[str, Any]:
        member = self._require_member(tenant_id, member_id)
        role = self._require_role(tenant_id, role_id)
        if not role.is_active:
            raise RbacError("role_inactive", "Cannot assign an inactive role")

        if role.name == SYSTEM_ROLE_OWNER:
            if not self._actor_is_owner(tenant_id, actor_user_id):
                raise RbacError(
                    "owner_protected",
                    "Only an Owner can assign the Owner role",
                )
            if actor_user_id == member_id and not self._member_has_role(
                member_id, role.id
            ):
                raise RbacError(
                    "privilege_escalation",
                    "Cannot grant yourself Owner",
                )

        existing = self._session.scalar(
            select(MemberRole).where(
                MemberRole.tenant_user_id == member_id,
                MemberRole.role_id == role.id,
            )
        )
        if existing is not None:
            return self._member_roles_payload(tenant_id, member)

        self._session.add(MemberRole(tenant_user_id=member_id, role_id=role.id))
        self._session.flush()
        self._sync_legacy_role_string(member)
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="MEMBER_ROLE_ASSIGNED",
            resource_ids={
                "member_id": str(member_id),
                "role_id": str(role.id),
                "role_name": role.name,
            },
        )
        return self._member_roles_payload(tenant_id, member)

    def remove_role(
        self,
        tenant_id: UUID,
        *,
        member_id: UUID,
        role_id: UUID,
        actor: str,
        actor_user_id: UUID,
    ) -> dict[str, Any]:
        member = self._require_member(tenant_id, member_id)
        role = self._require_role(tenant_id, role_id)

        if role.name == SYSTEM_ROLE_OWNER:
            if not self._actor_is_owner(tenant_id, actor_user_id):
                raise RbacError(
                    "owner_protected",
                    "Only an Owner can remove the Owner role",
                )
            owner_count = self._count_active_owners(tenant_id)
            if owner_count <= 1:
                raise RbacError(
                    "last_owner",
                    "Cannot remove the last Owner from the organization",
                )

        link = self._session.scalar(
            select(MemberRole).where(
                MemberRole.tenant_user_id == member_id,
                MemberRole.role_id == role.id,
            )
        )
        if link is None:
            raise RbacError("assignment_not_found", "Role is not assigned to member")
        self._session.delete(link)
        self._session.flush()
        self._sync_legacy_role_string(member)
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="MEMBER_ROLE_REMOVED",
            resource_ids={
                "member_id": str(member_id),
                "role_id": str(role.id),
                "role_name": role.name,
            },
        )
        return self._member_roles_payload(tenant_id, member)

    def list_member_roles(self, tenant_id: UUID, member_id: UUID) -> dict[str, Any]:
        member = self._require_member(tenant_id, member_id)
        return self._member_roles_payload(tenant_id, member)

    def _replace_permissions(
        self,
        tenant_id: UUID,
        role: OrganizationRole,
        permissions: list[dict[str, str]],
        *,
        actor_user_id: UUID,
        allow_owner_only: bool,
    ) -> None:
        valid_keys = all_permission_keys()
        desired: dict[str, str] = {}
        for item in permissions:
            key = (item.get("key") or "").strip()
            scope = (item.get("scope") or SCOPE_ALL).strip()
            if key not in valid_keys:
                raise RbacError(
                    "unknown_permission",
                    f"Permission is not defined by the platform: {key}",
                )
            if scope not in VALID_SCOPES:
                raise RbacError("invalid_scope", f"Invalid scope: {scope}")
            if key in OWNER_ONLY_PERMISSIONS and not allow_owner_only:
                raise RbacError(
                    "privilege_escalation",
                    f"Cannot grant restricted permission: {key}",
                )
            # Actor must hold permission to delegate it (except Owner)
            if not allow_owner_only:
                from callbot_platform.rbac.service import AuthorizationService

                if not AuthorizationService(self._session).has_permission(
                    tenant_id, actor_user_id, key
                ):
                    raise RbacError(
                        "privilege_escalation",
                        f"Cannot grant a permission you do not hold: {key}",
                    )
            desired[key] = scope

        existing = list(
            self._session.scalars(
                select(RolePermission)
                .where(RolePermission.role_id == role.id)
                .options(joinedload(RolePermission.permission))
            ).all()
        )
        existing_by_key = {
            rp.permission.key: rp for rp in existing if rp.permission is not None
        }

        for key, rp in list(existing_by_key.items()):
            if key not in desired:
                self._session.delete(rp)
                write_audit(
                    self._session,
                    tenant_id=tenant_id,
                    actor=str(actor_user_id),
                    action="ROLE_PERMISSION_REVOKED",
                    resource_ids={"role_id": str(role.id), "permission": key},
                )

        for key, scope in desired.items():
            perm = self._session.scalar(
                select(Permission).where(
                    Permission.resource == key.split(".", 1)[0],
                    Permission.action == key.split(".", 1)[1],
                )
            )
            if perm is None:
                continue
            if key in existing_by_key:
                rp = existing_by_key[key]
                if rp.scope != scope:
                    rp.scope = scope
                    write_audit(
                        self._session,
                        tenant_id=tenant_id,
                        actor=str(actor_user_id),
                        action="ROLE_PERMISSION_GRANTED",
                        resource_ids={
                            "role_id": str(role.id),
                            "permission": key,
                            "scope": scope,
                        },
                    )
            else:
                self._session.add(
                    RolePermission(role_id=role.id, permission_id=perm.id, scope=scope)
                )
                write_audit(
                    self._session,
                    tenant_id=tenant_id,
                    actor=str(actor_user_id),
                    action="ROLE_PERMISSION_GRANTED",
                    resource_ids={
                        "role_id": str(role.id),
                        "permission": key,
                        "scope": scope,
                    },
                )
        self._session.flush()

    def _sync_legacy_role_string(self, member: TenantUser) -> None:
        from callbot_platform.rbac.service import AuthorizationService

        legacy = AuthorizationService(self._session).primary_legacy_role(
            member.tenant_id, member.id
        )
        if legacy and legacy != member.role:
            member.role = legacy
            member.updated_at = datetime.now(UTC)
            self._session.flush()

    def _actor_is_owner(self, tenant_id: UUID, actor_user_id: UUID) -> bool:
        owner = self._session.scalar(
            select(OrganizationRole).where(
                OrganizationRole.tenant_id == tenant_id,
                OrganizationRole.name == SYSTEM_ROLE_OWNER,
            )
        )
        if owner is None:
            return False
        return self._member_has_role(actor_user_id, owner.id)

    def _member_has_role(self, member_id: UUID, role_id: UUID) -> bool:
        return (
            self._session.scalar(
                select(MemberRole).where(
                    MemberRole.tenant_user_id == member_id,
                    MemberRole.role_id == role_id,
                )
            )
            is not None
        )

    def _count_active_owners(self, tenant_id: UUID) -> int:
        return int(
            self._session.scalar(
                select(func.count())
                .select_from(MemberRole)
                .join(OrganizationRole, MemberRole.role_id == OrganizationRole.id)
                .join(TenantUser, MemberRole.tenant_user_id == TenantUser.id)
                .where(
                    OrganizationRole.tenant_id == tenant_id,
                    OrganizationRole.name == SYSTEM_ROLE_OWNER,
                    TenantUser.is_active.is_(True),
                )
            )
            or 0
        )

    def _require_role(self, tenant_id: UUID, role_id: UUID) -> OrganizationRole:
        role = self._session.scalar(
            select(OrganizationRole).where(
                OrganizationRole.id == role_id,
                OrganizationRole.tenant_id == tenant_id,
            )
        )
        if role is None:
            raise RbacError("role_not_found", "Role not found")
        return role

    def _require_member(self, tenant_id: UUID, member_id: UUID) -> TenantUser:
        member = self._session.scalar(
            select(TenantUser).where(
                TenantUser.id == member_id,
                TenantUser.tenant_id == tenant_id,
            )
        )
        if member is None:
            raise RbacError("member_not_found", "Member not found")
        return member

    def _member_roles_payload(
        self, tenant_id: UUID, member: TenantUser
    ) -> dict[str, Any]:
        roles = self._session.scalars(
            select(OrganizationRole)
            .join(MemberRole, MemberRole.role_id == OrganizationRole.id)
            .where(
                MemberRole.tenant_user_id == member.id,
                OrganizationRole.tenant_id == tenant_id,
            )
            .order_by(OrganizationRole.name)
        ).all()
        return {
            "member_id": str(member.id),
            "roles": [
                {
                    "id": str(r.id),
                    "name": r.name,
                    "is_system": r.is_system,
                    "is_active": r.is_active,
                }
                for r in roles
            ],
        }

    def _serialize_role(
        self, role: OrganizationRole, *, include_permissions: bool
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": str(role.id),
            "organization_id": str(role.tenant_id),
            "tenant_id": str(role.tenant_id),
            "name": role.name,
            "description": role.description,
            "is_system": role.is_system,
            "is_active": role.is_active,
            "created_at": role.created_at.isoformat() if role.created_at else None,
            "updated_at": role.updated_at.isoformat() if role.updated_at else None,
        }
        if include_permissions:
            rps = self._session.scalars(
                select(RolePermission)
                .where(RolePermission.role_id == role.id)
                .options(joinedload(RolePermission.permission))
            ).all()
            payload["permissions"] = [
                {
                    "key": rp.permission.key,
                    "scope": rp.scope,
                    "resource": rp.permission.resource,
                    "action": rp.permission.action,
                }
                for rp in rps
                if rp.permission is not None
            ]
        return payload

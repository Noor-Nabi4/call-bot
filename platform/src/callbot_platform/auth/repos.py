"""Tenant user authentication repository."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from callbot_platform.billing.entitlements import EntitlementError, EntitlementGuard
from callbot_platform.db.models import Technician, Tenant, TenantUser
from callbot_platform.organization.membership import (
    MEMBERSHIP_ACTIVE,
    VALID_MEMBERSHIP_STATUSES,
    is_active_for_status,
    status_for_is_active,
)
from callbot_platform.security.session import (
    ROLE_ADMIN,
    ROLE_TECHNICIAN,
    VALID_ROLES,
    hash_password,
    verify_password,
)
from callbot_platform.telephony.audit import write_audit


class AuthError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class AuthRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def authenticate(
        self, *, tenant_slug: str, email: str, password: str
    ) -> dict[str, Any]:
        tenant = self._session.scalar(
            select(Tenant).where(Tenant.slug == tenant_slug.strip().lower())
        )
        if tenant is None:
            raise AuthError("invalid_credentials", "Invalid email or password")
        user = self._session.scalar(
            select(TenantUser).where(
                TenantUser.tenant_id == tenant.id,
                TenantUser.email == email.strip().lower(),
            )
        )
        if user is None or not user.is_active:
            raise AuthError("invalid_credentials", "Invalid email or password")
        if not verify_password(password, user.password_hash):
            raise AuthError("invalid_credentials", "Invalid email or password")
        return self._serialize_user(user, tenant)

    def get_user(self, tenant_id: UUID, user_id: UUID) -> dict[str, Any] | None:
        user = self._session.scalar(
            select(TenantUser).where(
                TenantUser.id == user_id, TenantUser.tenant_id == tenant_id
            )
        )
        if user is None or not user.is_active:
            return None
        tenant = self._session.get(Tenant, tenant_id)
        if tenant is None:
            return None
        return self._serialize_user(user, tenant)

    def bootstrap_admin(
        self,
        *,
        tenant_id: UUID,
        email: str,
        password: str,
        name: str,
        actor: str = "bootstrap",
    ) -> dict[str, Any]:
        tenant = self._session.get(Tenant, tenant_id)
        if tenant is None:
            raise AuthError("tenant_not_found", "Tenant not found")
        existing_count = self._session.scalar(
            select(func.count())
            .select_from(TenantUser)
            .where(TenantUser.tenant_id == tenant_id)
        )
        if existing_count and int(existing_count) > 0:
            raise AuthError(
                "already_bootstrapped",
                "Tenant already has users; bootstrap is only for the first admin",
            )
        if len(password) < 8:
            raise AuthError("weak_password", "Password must be at least 8 characters")
        user = TenantUser(
            tenant_id=tenant_id,
            email=email.strip().lower(),
            password_hash=hash_password(password),
            name=name.strip(),
            role=ROLE_ADMIN,
            status=MEMBERSHIP_ACTIVE,
            is_active=True,
        )
        self._session.add(user)
        self._session.flush()
        from callbot_platform.rbac.catalog import SYSTEM_ROLE_OWNER
        from callbot_platform.rbac.seed import assign_member_system_role

        assign_member_system_role(
            self._session,
            tenant_id=tenant_id,
            tenant_user_id=user.id,
            system_role_name=SYSTEM_ROLE_OWNER,
        )
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="user_bootstrapped",
            resource_ids={"user_id": str(user.id), "email": user.email},
        )
        return self._serialize_user(user, tenant)

    def create_user(
        self,
        tenant_id: UUID,
        *,
        email: str,
        password: str,
        name: str,
        role: str,
        phone: str | None = None,
        actor: str = "admin",
        status: str | None = None,
    ) -> dict[str, Any]:
        if role not in VALID_ROLES:
            raise AuthError(
                "invalid_role", f"Role must be one of {sorted(VALID_ROLES)}"
            )
        membership_status = (status or MEMBERSHIP_ACTIVE).strip().lower()
        if membership_status not in VALID_MEMBERSHIP_STATUSES:
            raise AuthError(
                "invalid_membership_status",
                f"Status must be one of {sorted(VALID_MEMBERSHIP_STATUSES)}",
            )
        if len(password) < 8:
            raise AuthError("weak_password", "Password must be at least 8 characters")
        tenant = self._session.get(Tenant, tenant_id)
        if tenant is None:
            raise AuthError("tenant_not_found", "Tenant not found")
        existing = self._session.scalar(
            select(TenantUser).where(
                TenantUser.tenant_id == tenant_id,
                TenantUser.email == email.strip().lower(),
            )
        )
        if existing is not None:
            raise AuthError("email_taken", "A user with that email already exists")
        if is_active_for_status(membership_status):
            try:
                EntitlementGuard(self._session).require_capacity(
                    tenant_id, "team_users"
                )
            except EntitlementError as exc:
                raise AuthError(exc.code, str(exc)) from exc
        user = TenantUser(
            tenant_id=tenant_id,
            email=email.strip().lower(),
            password_hash=hash_password(password),
            name=name.strip(),
            role=role,
            status=membership_status,
            is_active=is_active_for_status(membership_status),
        )
        self._session.add(user)
        self._session.flush()
        from callbot_platform.rbac.catalog import LEGACY_ROLE_MAP
        from callbot_platform.rbac.seed import assign_member_system_role

        system_name = LEGACY_ROLE_MAP.get(role)
        if system_name:
            assign_member_system_role(
                self._session,
                tenant_id=tenant_id,
                tenant_user_id=user.id,
                system_role_name=system_name,
            )
        tech = None
        if role == ROLE_TECHNICIAN:
            tech = Technician(
                tenant_id=tenant_id,
                user_id=user.id,
                display_name=name.strip(),
                phone=phone,
                is_active=True,
            )
            self._session.add(tech)
            self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="user_created",
            resource_ids={"user_id": str(user.id), "role": role},
        )
        result = self._serialize_user(user, tenant)
        if tech is not None:
            result["technician_id"] = str(tech.id)
        return result

    def update_user_admin(
        self,
        tenant_id: UUID,
        user_id: UUID,
        *,
        actor_user_id: UUID,
        actor_email: str,
        role: str | None = None,
        is_active: bool | None = None,
        name: str | None = None,
        password: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        """Admin update: role, membership status, name, or temporary password reset."""
        user = self._session.scalar(
            select(TenantUser).where(
                TenantUser.id == user_id, TenantUser.tenant_id == tenant_id
            )
        )
        if user is None:
            raise AuthError("user_not_found", "User not found")
        tenant = self._session.get(Tenant, tenant_id)
        if tenant is None:
            raise AuthError("tenant_not_found", "Tenant not found")

        if role is not None and role not in VALID_ROLES:
            raise AuthError(
                "invalid_role",
                f"Role must be one of {sorted(VALID_ROLES)}",
            )
        if status is not None and status not in VALID_MEMBERSHIP_STATUSES:
            raise AuthError(
                "invalid_membership_status",
                f"Status must be one of {sorted(VALID_MEMBERSHIP_STATUSES)}",
            )
        if (
            status is not None
            and is_active is not None
            and is_active_for_status(status) != is_active
        ):
            raise AuthError(
                "status_conflict",
                "status and is_active disagree; send only one",
            )

        changed: list[str] = []
        if status is not None:
            is_active = is_active_for_status(status)
        elif is_active is not None:
            status = status_for_is_active(is_active)

        if is_active is False and user.id == actor_user_id:
            raise AuthError(
                "cannot_deactivate_self",
                "You cannot deactivate your own account",
            )

        if (
            is_active is False
            and user.is_active
            and self._is_privileged_member(tenant_id, user.id)
            and self._count_privileged_members(tenant_id) <= 1
        ):
            raise AuthError(
                "last_admin",
                "Cannot deactivate the last active Owner/Admin",
            )

        if (
            role is not None
            and role != ROLE_ADMIN
            and user.is_active
            and self._is_privileged_member(tenant_id, user.id)
            and self._count_privileged_members(tenant_id) <= 1
        ):
            raise AuthError(
                "last_admin",
                "Cannot demote the last active Owner/Admin",
            )

        if is_active is True and not user.is_active:
            try:
                EntitlementGuard(self._session).require_capacity(
                    tenant_id, "team_users"
                )
            except EntitlementError as exc:
                raise AuthError(exc.code, str(exc)) from exc

        if name is not None:
            cleaned = name.strip()
            if not cleaned:
                raise AuthError("invalid_name", "Name is required")
            if len(cleaned) > 255:
                raise AuthError("invalid_name", "Name must be 255 characters or fewer")
            if cleaned != user.name:
                user.name = cleaned
                changed.append("name")

        if role is not None and role != user.role:
            from callbot_platform.rbac.errors import RbacError
            from callbot_platform.rbac.seed import sync_legacy_primary_role

            try:
                sync_legacy_primary_role(
                    self._session,
                    tenant_id=tenant_id,
                    tenant_user_id=user.id,
                    legacy_role=role,
                )
            except RbacError as exc:
                raise AuthError(exc.code, str(exc)) from exc
            user.role = role
            changed.append("role")
            if role == ROLE_TECHNICIAN:
                tech = self._session.scalar(
                    select(Technician).where(Technician.user_id == user.id)
                )
                if tech is None:
                    self._session.add(
                        Technician(
                            tenant_id=tenant_id,
                            user_id=user.id,
                            display_name=user.name,
                            is_active=True,
                        )
                    )
                    changed.append("technician_created")

        if is_active is not None and is_active != user.is_active:
            user.is_active = is_active
            changed.append("is_active")
            tech = self._session.scalar(
                select(Technician).where(Technician.user_id == user.id)
            )
            if tech is not None:
                tech.is_active = is_active
                changed.append("technician_is_active")

        if status is not None and status != user.status:
            user.status = status
            changed.append("status")

        if password is not None:
            if len(password) < 8:
                raise AuthError(
                    "weak_password", "Password must be at least 8 characters"
                )
            user.password_hash = hash_password(password)
            changed.append("password")

        if not changed:
            return self._serialize_user(user, tenant)

        user.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor_email,
            action="user_admin_updated",
            resource_ids={
                "user_id": str(user.id),
                "changed_fields": changed,
            },
        )
        return self._serialize_user(user, tenant)

    def update_profile(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        name: str | None = None,
        current_password: str | None = None,
        new_password: str | None = None,
        actor: str | None = None,
    ) -> dict[str, Any]:
        user = self._session.scalar(
            select(TenantUser).where(
                TenantUser.id == user_id, TenantUser.tenant_id == tenant_id
            )
        )
        if user is None or not user.is_active:
            raise AuthError("user_not_found", "User not found or inactive")
        tenant = self._session.get(Tenant, tenant_id)
        if tenant is None:
            raise AuthError("tenant_not_found", "Tenant not found")

        changed: list[str] = []
        if name is not None:
            cleaned = name.strip()
            if not cleaned:
                raise AuthError("invalid_name", "Name is required")
            if len(cleaned) > 255:
                raise AuthError("invalid_name", "Name must be 255 characters or fewer")
            if cleaned != user.name:
                user.name = cleaned
                changed.append("name")
                tech = self._session.scalar(
                    select(Technician).where(Technician.user_id == user.id)
                )
                if tech is not None:
                    tech.display_name = cleaned
                    changed.append("technician_display_name")

        if new_password is not None:
            if not current_password:
                raise AuthError(
                    "current_password_required",
                    "Current password is required to set a new password",
                )
            if not verify_password(current_password, user.password_hash):
                raise AuthError("invalid_credentials", "Current password is incorrect")
            if len(new_password) < 8:
                raise AuthError(
                    "weak_password", "Password must be at least 8 characters"
                )
            if verify_password(new_password, user.password_hash):
                raise AuthError(
                    "password_unchanged",
                    "New password must be different from the current password",
                )
            user.password_hash = hash_password(new_password)
            changed.append("password")

        if not changed:
            return self._serialize_user(user, tenant)

        user.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor or user.email,
            action="user_profile_updated",
            resource_ids={
                "user_id": str(user.id),
                "changed_fields": changed,
            },
        )
        return self._serialize_user(user, tenant)

    def _serialize_user(self, user: TenantUser, tenant: Tenant) -> dict[str, Any]:
        tech_id = None
        if user.technician is not None:
            tech_id = str(user.technician.id)
        else:
            tech = self._session.scalar(
                select(Technician).where(Technician.user_id == user.id)
            )
            if tech is not None:
                tech_id = str(tech.id)
        return {
            "id": str(user.id),
            "tenant_id": str(user.tenant_id),
            "organization_id": str(user.tenant_id),
            "tenant_slug": tenant.slug,
            "tenant_name": tenant.name,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "status": user.status,
            "technician_id": tech_id,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }

    def _is_privileged_member(self, tenant_id: UUID, user_id: UUID) -> bool:
        from callbot_platform.rbac.catalog import SYSTEM_ROLE_ADMIN, SYSTEM_ROLE_OWNER
        from callbot_platform.rbac.models import MemberRole, OrganizationRole

        return (
            self._session.scalar(
                select(MemberRole.id)
                .join(OrganizationRole, MemberRole.role_id == OrganizationRole.id)
                .where(
                    MemberRole.tenant_user_id == user_id,
                    OrganizationRole.tenant_id == tenant_id,
                    OrganizationRole.name.in_([SYSTEM_ROLE_OWNER, SYSTEM_ROLE_ADMIN]),
                    OrganizationRole.is_active.is_(True),
                )
                .limit(1)
            )
            is not None
        )

    def _count_privileged_members(self, tenant_id: UUID) -> int:
        from callbot_platform.rbac.catalog import SYSTEM_ROLE_ADMIN, SYSTEM_ROLE_OWNER
        from callbot_platform.rbac.models import MemberRole, OrganizationRole

        return int(
            self._session.scalar(
                select(func.count(func.distinct(MemberRole.tenant_user_id)))
                .select_from(MemberRole)
                .join(OrganizationRole, MemberRole.role_id == OrganizationRole.id)
                .join(TenantUser, MemberRole.tenant_user_id == TenantUser.id)
                .where(
                    OrganizationRole.tenant_id == tenant_id,
                    OrganizationRole.name.in_([SYSTEM_ROLE_OWNER, SYSTEM_ROLE_ADMIN]),
                    OrganizationRole.is_active.is_(True),
                    TenantUser.is_active.is_(True),
                )
            )
            or 0
        )

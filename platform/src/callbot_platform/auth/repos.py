"""Tenant user authentication repository."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from callbot_platform.billing.entitlements import EntitlementError, EntitlementGuard
from callbot_platform.db.models import Technician, Tenant, TenantUser
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
            is_active=True,
        )
        self._session.add(user)
        self._session.flush()
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
    ) -> dict[str, Any]:
        if role not in VALID_ROLES:
            raise AuthError("invalid_role", f"Role must be one of {sorted(VALID_ROLES)}")
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
            is_active=True,
        )
        self._session.add(user)
        self._session.flush()
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
    ) -> dict[str, Any]:
        """Admin update: role, active flag, name, or temporary password reset."""
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

        changed: list[str] = []

        if is_active is False and user.id == actor_user_id:
            raise AuthError(
                "cannot_deactivate_self",
                "You cannot deactivate your own account",
            )

        if is_active is False and user.role == ROLE_ADMIN and user.is_active:
            active_admins = int(
                self._session.scalar(
                    select(func.count())
                    .select_from(TenantUser)
                    .where(
                        TenantUser.tenant_id == tenant_id,
                        TenantUser.role == ROLE_ADMIN,
                        TenantUser.is_active.is_(True),
                    )
                )
                or 0
            )
            if active_admins <= 1:
                raise AuthError(
                    "last_admin",
                    "Cannot deactivate the last active admin",
                )

        if (
            role is not None
            and user.role == ROLE_ADMIN
            and role != ROLE_ADMIN
            and user.is_active
        ):
            active_admins = int(
                self._session.scalar(
                    select(func.count())
                    .select_from(TenantUser)
                    .where(
                        TenantUser.tenant_id == tenant_id,
                        TenantUser.role == ROLE_ADMIN,
                        TenantUser.is_active.is_(True),
                    )
                )
                or 0
            )
            if active_admins <= 1:
                raise AuthError(
                    "last_admin",
                    "Cannot demote the last active admin",
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
            "tenant_slug": tenant.slug,
            "tenant_name": tenant.name,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "technician_id": tech_id,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }

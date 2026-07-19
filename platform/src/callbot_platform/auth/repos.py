"""Tenant user authentication repository."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from callbot_platform.db.models import Tenant, TenantUser, Technician
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

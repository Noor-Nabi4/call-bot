"""Tenant-scoped organization membership repository."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.db.models.jobs import TenantUser
from callbot_platform.organization.errors import OrganizationError
from callbot_platform.organization.membership import (
    VALID_MEMBERSHIP_STATUSES,
    serialize_membership,
)

logger = logging.getLogger(__name__)


class MembershipRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _auth(self):
        from callbot_platform.auth.repos import AuthRepository

        return AuthRepository(self._session)

    def list(self, organization_id: UUID) -> list[dict[str, Any]]:
        rows = self._session.scalars(
            select(TenantUser)
            .where(TenantUser.tenant_id == organization_id)
            .order_by(TenantUser.created_at.desc())
        ).all()
        return [serialize_membership(row) for row in rows]

    def get(self, organization_id: UUID, member_id: UUID) -> dict[str, Any]:
        row = self._session.scalar(
            select(TenantUser).where(
                TenantUser.id == member_id,
                TenantUser.tenant_id == organization_id,
            )
        )
        if row is None:
            raise OrganizationError("member_not_found", "Member not found")
        return serialize_membership(row)

    def create(
        self,
        organization_id: UUID,
        *,
        email: str,
        password: str,
        name: str,
        role: str,
        status: str | None = None,
        phone: str | None = None,
        actor: str,
    ) -> dict[str, Any]:
        from callbot_platform.auth.repos import AuthError

        try:
            created = self._auth().create_user(
                organization_id,
                email=email,
                password=password,
                name=name,
                role=role,
                phone=phone,
                actor=actor,
                status=status,
            )
        except AuthError as exc:
            raise OrganizationError(exc.code, str(exc)) from exc
        member_id = UUID(str(created["id"]))
        return self.get(organization_id, member_id)

    def update(
        self,
        organization_id: UUID,
        member_id: UUID,
        *,
        actor_user_id: UUID,
        actor_email: str,
        role: str | None = None,
        status: str | None = None,
        is_active: bool | None = None,
        name: str | None = None,
        password: str | None = None,
    ) -> dict[str, Any]:
        from callbot_platform.auth.repos import AuthError

        if status is not None and status not in VALID_MEMBERSHIP_STATUSES:
            raise OrganizationError(
                "invalid_membership_status",
                f"Status must be one of {sorted(VALID_MEMBERSHIP_STATUSES)}",
            )
        self.get(organization_id, member_id)
        try:
            self._auth().update_user_admin(
                organization_id,
                member_id,
                actor_user_id=actor_user_id,
                actor_email=actor_email,
                role=role,
                is_active=is_active,
                name=name,
                password=password,
                status=status,
            )
        except AuthError as exc:
            raise OrganizationError(exc.code, str(exc)) from exc
        logger.info(
            "membership_updated organization_id=%s member_id=%s actor=%s",
            organization_id,
            member_id,
            actor_email,
        )
        return self.get(organization_id, member_id)

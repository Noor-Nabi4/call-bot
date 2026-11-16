"""Organization application service."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from callbot_platform.organization.membership_repos import MembershipRepository
from callbot_platform.organization.repos import OrganizationRepository


class OrganizationService:
    def __init__(self, session: Session) -> None:
        self._repo = OrganizationRepository(session)
        self.memberships = MembershipRepository(session)

    def get(self, tenant_id: UUID) -> dict[str, Any]:
        return self._repo.get(tenant_id)

    def create(self, **kwargs: Any) -> dict[str, Any]:
        return self._repo.create(**kwargs)

    def update(self, tenant_id: UUID, *, actor: str, **fields: Any) -> dict[str, Any]:
        return self._repo.update(tenant_id, actor=actor, **fields)

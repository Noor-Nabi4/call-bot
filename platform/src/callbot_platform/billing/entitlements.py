"""Hard entitlement checks against plan resource limits.

Voice minutes are soft (tracked + overage estimated). Seats, phone numbers, and
knowledge documents are hard limits for entitled SaaS tenants. Tenants without a
subscription row (legacy/bootstrap) are not capped here — ops access is gated by
``BillingService.tenant_is_entitled`` instead.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from callbot_platform.billing.plans import entitlements_for_plan
from callbot_platform.billing.repos import BillingRepository
from callbot_platform.db.models import KnowledgeArticle, TenantPhoneNumber, TenantUser

ResourceKey = Literal["team_users", "phone_numbers", "knowledge_documents"]


class EntitlementError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class EntitlementGuard:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._billing = BillingRepository(session)

    def require_capacity(
        self,
        tenant_id: UUID,
        resource: ResourceKey,
        *,
        additional: int = 1,
    ) -> None:
        """Raise ``EntitlementError`` when adding ``additional`` would exceed the plan."""
        sub = self._billing.get_by_tenant(tenant_id)
        if sub is None:
            return
        entitlements = entitlements_for_plan(sub.plan_key)
        if entitlements is None or resource not in entitlements:
            return
        limit = int(entitlements[resource])
        used = self._used(tenant_id, resource)
        if used + additional > limit:
            raise EntitlementError(
                "plan_limit_exceeded",
                (
                    f"Plan limit reached for {resource}: "
                    f"{used} used of {limit} included. "
                    "Upgrade your plan or free capacity first."
                ),
            )

    def _used(self, tenant_id: UUID, resource: ResourceKey) -> int:
        if resource == "team_users":
            count = self._session.scalar(
                select(func.count())
                .select_from(TenantUser)
                .where(
                    TenantUser.tenant_id == tenant_id,
                    TenantUser.is_active.is_(True),
                )
            )
        elif resource == "phone_numbers":
            count = self._session.scalar(
                select(func.count())
                .select_from(TenantPhoneNumber)
                .where(TenantPhoneNumber.tenant_id == tenant_id)
            )
        else:
            count = self._session.scalar(
                select(func.count())
                .select_from(KnowledgeArticle)
                .where(
                    KnowledgeArticle.tenant_id == tenant_id,
                    KnowledgeArticle.is_active.is_(True),
                )
            )
        return int(count or 0)

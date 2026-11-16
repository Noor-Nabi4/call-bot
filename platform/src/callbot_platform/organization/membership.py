"""Organization membership — tenant_users is the membership row.

Do not add a parallel organization_members table. Task 1.3 will attach
normalized roles to these same membership ids.
"""

from __future__ import annotations

from typing import Any

from callbot_platform.db.models.jobs import TenantUser

MEMBERSHIP_ACTIVE = "active"
MEMBERSHIP_INVITED = "invited"
MEMBERSHIP_DISABLED = "disabled"

VALID_MEMBERSHIP_STATUSES = frozenset(
    {MEMBERSHIP_ACTIVE, MEMBERSHIP_INVITED, MEMBERSHIP_DISABLED}
)


def is_active_for_status(status: str) -> bool:
    return status == MEMBERSHIP_ACTIVE


def status_for_is_active(is_active: bool) -> str:
    return MEMBERSHIP_ACTIVE if is_active else MEMBERSHIP_DISABLED


def serialize_membership(user: TenantUser, *, roles: list[dict] | None = None) -> dict[str, Any]:
    payload = {
        "id": str(user.id),
        "organization_id": str(user.tenant_id),
        "tenant_id": str(user.tenant_id),
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "status": user.status,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }
    if roles is not None:
        payload["roles"] = roles
    return payload

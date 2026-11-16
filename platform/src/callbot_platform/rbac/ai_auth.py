"""AI tool authorization helpers for internal voice routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from callbot_platform.rbac.errors import RbacError
from callbot_platform.rbac.service import AuthorizationService


def require_ai_tool_permission(
    session: Session, tenant_id: UUID, tool_group: str
) -> None:
    """Enforce org AI Agent role permissions for a voice tool group.

    Call-scope still binds tenant/call identity; this check prevents the AI from
    executing tools the organization has not authorized.
    """
    try:
        AuthorizationService(session).check_ai_tool(tenant_id, tool_group)
    except RbacError as exc:
        status = 403 if exc.code == "permission_denied" else 400
        raise HTTPException(
            status_code=status,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc

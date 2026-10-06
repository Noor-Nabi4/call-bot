"""Organization roles and permission catalog APIs."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from callbot_platform.api.deps import (
    CurrentUser,
    db_dep,
    require_entitled_permission,
)
from callbot_platform.rbac.errors import RbacError
from callbot_platform.rbac.repos import RoleRepository
from callbot_platform.rbac.service import AuthorizationService

router = APIRouter(prefix="/api/admin/organization", tags=["organization-rbac"])

_require_roles_read = require_entitled_permission("roles.read")
_require_roles_create = require_entitled_permission("roles.create")
_require_roles_update = require_entitled_permission("roles.update")
_require_roles_delete = require_entitled_permission("roles.delete")
_require_roles_assign = require_entitled_permission("roles.assign")


class PermissionGrantBody(BaseModel):
    model_config = {"extra": "forbid"}

    key: str = Field(min_length=3, max_length=128)
    scope: str = Field(default="ALL_ORGANIZATION", max_length=32)


class CreateRoleBody(BaseModel):
    model_config = {"extra": "forbid"}

    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    permissions: list[PermissionGrantBody] | None = None


class UpdateRoleBody(BaseModel):
    model_config = {"extra": "forbid"}

    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None
    permissions: list[PermissionGrantBody] | None = None


class AssignRoleBody(BaseModel):
    model_config = {"extra": "forbid"}

    role_id: UUID


def _http(exc: RbacError) -> HTTPException:
    status = 400
    if exc.code in {"role_not_found", "member_not_found", "assignment_not_found"}:
        status = 404
    elif exc.code in {"role_name_taken"}:
        status = 409
    elif exc.code in {
        "permission_denied",
        "privilege_escalation",
        "owner_protected",
        "system_role_protected",
        "last_owner",
    }:
        status = 403
    return HTTPException(
        status_code=status, detail={"code": exc.code, "message": str(exc)}
    )


@router.get("/permissions")
def list_platform_permissions(
    user: CurrentUser = Depends(_require_roles_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    return {"permissions": AuthorizationService(session).list_permissions_catalog()}


@router.get("/roles")
def list_roles(
    user: CurrentUser = Depends(_require_roles_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    return {"roles": RoleRepository(session).list_roles(user.tenant_id)}


@router.post("/roles")
def create_role(
    body: CreateRoleBody,
    user: CurrentUser = Depends(_require_roles_create),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        role = RoleRepository(session).create_role(
            user.tenant_id,
            name=body.name,
            description=body.description,
            permissions=(
                [p.model_dump() for p in body.permissions]
                if body.permissions is not None
                else None
            ),
            actor=user.email,
            actor_user_id=user.user_id,
        )
        return {"role": role}
    except RbacError as exc:
        raise _http(exc) from exc


@router.get("/roles/{role_id}")
def get_role(
    role_id: UUID,
    user: CurrentUser = Depends(_require_roles_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {"role": RoleRepository(session).get_role(user.tenant_id, role_id)}
    except RbacError as exc:
        raise _http(exc) from exc


@router.patch("/roles/{role_id}")
def patch_role(
    role_id: UUID,
    body: UpdateRoleBody,
    user: CurrentUser = Depends(_require_roles_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(
            status_code=400,
            detail={"code": "nothing_to_update", "message": "No role fields provided"},
        )
    perms = fields.pop("permissions", None)
    try:
        role = RoleRepository(session).update_role(
            user.tenant_id,
            role_id,
            actor=user.email,
            actor_user_id=user.user_id,
            permissions=perms,
            **fields,
        )
        return {"role": role}
    except RbacError as exc:
        raise _http(exc) from exc


@router.delete("/roles/{role_id}")
def delete_role(
    role_id: UUID,
    user: CurrentUser = Depends(_require_roles_delete),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return RoleRepository(session).delete_role(
            user.tenant_id, role_id, actor=user.email
        )
    except RbacError as exc:
        raise _http(exc) from exc


@router.get("/members/{member_id}/roles")
def list_member_roles(
    member_id: UUID,
    user: CurrentUser = Depends(_require_roles_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return RoleRepository(session).list_member_roles(user.tenant_id, member_id)
    except RbacError as exc:
        raise _http(exc) from exc


@router.post("/members/{member_id}/roles")
def assign_member_role(
    member_id: UUID,
    body: AssignRoleBody,
    user: CurrentUser = Depends(_require_roles_assign),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return RoleRepository(session).assign_role(
            user.tenant_id,
            member_id=member_id,
            role_id=body.role_id,
            actor=user.email,
            actor_user_id=user.user_id,
        )
    except RbacError as exc:
        raise _http(exc) from exc


@router.delete("/members/{member_id}/roles/{role_id}")
def remove_member_role(
    member_id: UUID,
    role_id: UUID,
    user: CurrentUser = Depends(_require_roles_assign),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return RoleRepository(session).remove_role(
            user.tenant_id,
            member_id=member_id,
            role_id=role_id,
            actor=user.email,
            actor_user_id=user.user_id,
        )
    except RbacError as exc:
        raise _http(exc) from exc

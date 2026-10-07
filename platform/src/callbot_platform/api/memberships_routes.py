"""Membership plan + customer membership APIs (Phase 20)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from callbot_platform.api.deps import CurrentUser, db_dep, require_entitled_permission
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.memberships import MembershipService
from callbot_platform.rbac.errors import RbacError

router = APIRouter(prefix="/api/admin/crm", tags=["memberships"])

_require_read = require_entitled_permission("memberships.read")
_require_create = require_entitled_permission("memberships.create")
_require_update = require_entitled_permission("memberships.update")
_require_delete = require_entitled_permission("memberships.delete")


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, RbacError):
        return HTTPException(
            status_code=403, detail={"code": exc.code, "message": str(exc)}
        )
    if isinstance(exc, CrmError):
        status = (
            404 if exc.code == "not_found" or exc.code.endswith("_not_found") else 400
        )
        if exc.code in {
            "idempotency_conflict",
            "membership_already_active",
            "plan_name_conflict",
        }:
            status = 409
        return HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        )
    return HTTPException(
        status_code=500, detail={"code": "internal", "message": "Internal error"}
    )


def _actor(user: CurrentUser) -> str:
    return user.email or str(user.user_id)


class IncludedServiceBody(BaseModel):
    model_config = {"extra": "forbid"}
    service_id: UUID
    included_quantity: int = Field(default=1, ge=1, le=10_000)


class PlanCreateBody(BaseModel):
    model_config = {"extra": "forbid"}
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    monthly_price: str = "0"
    annual_price: str = "0"
    currency: str | None = None
    priority_scheduling: bool = False
    discount_type: str | None = None
    discount_value: str | None = None
    included_services: list[IncludedServiceBody] = Field(default_factory=list)
    status: str | None = None


class PlanUpdateBody(BaseModel):
    model_config = {"extra": "forbid"}
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    monthly_price: str | None = None
    annual_price: str | None = None
    currency: str | None = None
    priority_scheduling: bool | None = None
    discount_type: str | None = None
    discount_value: str | None = None
    clear_discount: bool = False
    included_services: list[IncludedServiceBody] | None = None


class SubscribeBody(BaseModel):
    model_config = {"extra": "forbid"}
    plan_id: UUID
    billing_interval: str = Field(min_length=1, max_length=16)
    create_payment_link: bool = True


class CancelBody(BaseModel):
    model_config = {"extra": "forbid"}
    immediate: bool = False


class PlanChangeBody(BaseModel):
    model_config = {"extra": "forbid"}
    target_plan_id: UUID
    billing_interval: str | None = None


@router.get("/membership-plans")
def list_plans(
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    try:
        return MembershipService(session).list_plans(
            user.tenant_id, status=status, limit=limit, offset=offset
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/membership-plans", status_code=201)
def create_plan(
    body: PlanCreateBody,
    user: CurrentUser = Depends(_require_create),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        plan = MembershipService(session).create_plan(
            user.tenant_id,
            actor=_actor(user),
            name=body.name,
            description=body.description,
            monthly_price=body.monthly_price,
            annual_price=body.annual_price,
            currency=body.currency,
            priority_scheduling=body.priority_scheduling,
            discount_type=body.discount_type,
            discount_value=body.discount_value,
            included_services=[s.model_dump() for s in body.included_services],
            status=body.status,
        )
        session.commit()
        return {"plan": plan}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.get("/membership-plans/{plan_id}")
def get_plan(
    plan_id: UUID,
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {"plan": MembershipService(session).get_plan(user.tenant_id, plan_id)}
    except Exception as exc:
        raise _http(exc) from exc


@router.patch("/membership-plans/{plan_id}")
def update_plan(
    plan_id: UUID,
    body: PlanUpdateBody,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        kwargs: dict[str, Any] = {
            "name": body.name,
            "description": body.description,
            "monthly_price": body.monthly_price,
            "annual_price": body.annual_price,
            "currency": body.currency,
            "priority_scheduling": body.priority_scheduling,
            "included_services": (
                [s.model_dump() for s in body.included_services]
                if body.included_services is not None
                else None
            ),
        }
        if body.clear_discount:
            kwargs["discount_type"] = None
            kwargs["discount_value"] = None
        else:
            if body.discount_type is not None or body.discount_value is not None:
                kwargs["discount_type"] = body.discount_type
                kwargs["discount_value"] = body.discount_value
        plan = MembershipService(session).update_plan(
            user.tenant_id, plan_id, actor=_actor(user), **kwargs
        )
        session.commit()
        return {"plan": plan}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.post("/membership-plans/{plan_id}/activate")
def activate_plan(
    plan_id: UUID,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        plan = MembershipService(session).activate_plan(
            user.tenant_id, plan_id, actor=_actor(user)
        )
        session.commit()
        return {"plan": plan}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.post("/membership-plans/{plan_id}/deactivate")
def deactivate_plan(
    plan_id: UUID,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        plan = MembershipService(session).deactivate_plan(
            user.tenant_id, plan_id, actor=_actor(user)
        )
        session.commit()
        return {"plan": plan}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.post("/membership-plans/{plan_id}/archive")
def archive_plan(
    plan_id: UUID,
    user: CurrentUser = Depends(_require_delete),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        plan = MembershipService(session).archive_plan(
            user.tenant_id, plan_id, actor=_actor(user)
        )
        session.commit()
        return {"plan": plan}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.get("/memberships")
def list_memberships(
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    customer_id: UUID | None = Query(default=None),  # noqa: B008
    plan_id: UUID | None = Query(default=None),  # noqa: B008
    status: str | None = Query(default=None),
    billing_interval: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    try:
        return MembershipService(session).list_memberships(
            user.tenant_id,
            customer_id=customer_id,
            plan_id=plan_id,
            status=status,
            billing_interval=billing_interval,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/customers/{customer_id}/membership")
def get_customer_membership(
    customer_id: UUID,
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        membership = MembershipService(session).get_customer_membership(
            user.tenant_id, customer_id
        )
        return {"membership": membership}
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/customers/{customer_id}/memberships", status_code=201)
def subscribe(
    customer_id: UUID,
    body: SubscribeBody,
    user: CurrentUser = Depends(_require_create),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    try:
        result = MembershipService(session).subscribe(
            user.tenant_id,
            customer_id=customer_id,
            plan_id=body.plan_id,
            billing_interval=body.billing_interval,
            actor=_actor(user),
            idempotency_key=idempotency_key,
            create_payment_link=body.create_payment_link,
        )
        session.commit()
        return result
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.get("/memberships/{membership_id}")
def get_membership(
    membership_id: UUID,
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "membership": MembershipService(session).get_membership(
                user.tenant_id, membership_id, include_history=True
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/memberships/{membership_id}/history")
def membership_history(
    membership_id: UUID,
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "history": MembershipService(session).history(user.tenant_id, membership_id)
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/memberships/{membership_id}/cancel")
def cancel_membership(
    membership_id: UUID,
    body: CancelBody,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    try:
        membership = MembershipService(session).cancel(
            user.tenant_id,
            membership_id,
            actor=_actor(user),
            immediate=body.immediate,
            idempotency_key=idempotency_key,
        )
        session.commit()
        return {"membership": membership}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.post("/memberships/{membership_id}/renew")
def renew_membership(
    membership_id: UUID,
    user: CurrentUser = Depends(_require_create),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        result = MembershipService(session).renew(
            user.tenant_id, membership_id, actor=_actor(user)
        )
        session.commit()
        return result
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.post("/memberships/{membership_id}/upgrade")
def upgrade_membership(
    membership_id: UUID,
    body: PlanChangeBody,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    try:
        membership = MembershipService(session).upgrade(
            user.tenant_id,
            membership_id,
            target_plan_id=body.target_plan_id,
            actor=_actor(user),
            billing_interval=body.billing_interval,
            idempotency_key=idempotency_key,
        )
        session.commit()
        return {"membership": membership}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.post("/memberships/{membership_id}/downgrade")
def downgrade_membership(
    membership_id: UUID,
    body: PlanChangeBody,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    try:
        membership = MembershipService(session).downgrade(
            user.tenant_id,
            membership_id,
            target_plan_id=body.target_plan_id,
            actor=_actor(user),
            billing_interval=body.billing_interval,
            idempotency_key=idempotency_key,
        )
        session.commit()
        return {"membership": membership}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc

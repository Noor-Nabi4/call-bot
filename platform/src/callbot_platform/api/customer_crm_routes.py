"""Admin Customer CRM APIs (Phase 4 Tasks 4.1-4.4)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from callbot_platform.api.deps import CurrentUser, db_dep, require_entitled_permission
from callbot_platform.crm.customers import CustomerService
from callbot_platform.crm.customers.timeline import TIMELINE_PERMISSIONS
from callbot_platform.crm.errors import CrmError
from callbot_platform.domain.phone import PhoneNumberError
from callbot_platform.rbac.errors import RbacError
from callbot_platform.rbac.service import AuthorizationService

router = APIRouter(prefix="/api/admin/crm/customers", tags=["customer-crm"])

_require_read = require_entitled_permission("customers.read")
_require_create = require_entitled_permission("customers.create")
_require_update = require_entitled_permission("customers.update")
_require_delete = require_entitled_permission("customers.delete")


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, CrmError):
        status = 404 if exc.code == "not_found" else 400
        if exc.code in {"customer_archived", "location_archived"}:
            status = 409
        return HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        )
    if isinstance(exc, PhoneNumberError):
        return HTTPException(
            status_code=400, detail={"code": "invalid_phone", "message": str(exc)}
        )
    return HTTPException(
        status_code=500, detail={"code": "internal", "message": str(exc)}
    )


def _actor(user: CurrentUser) -> str:
    return user.email or str(user.user_id)


class CustomerCreateBody(BaseModel):
    model_config = {"extra": "forbid"}
    name: str | None = Field(default=None, max_length=255)
    display_name: str | None = Field(default=None, max_length=255)
    first_name: str | None = Field(default=None, max_length=128)
    last_name: str | None = Field(default=None, max_length=128)
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    status: str | None = None
    notes: str | None = None
    tags: list[str] | None = None


class CustomerUpdateBody(BaseModel):
    model_config = {"extra": "forbid"}
    name: str | None = Field(default=None, max_length=255)
    display_name: str | None = Field(default=None, max_length=255)
    first_name: str | None = Field(default=None, max_length=128)
    last_name: str | None = Field(default=None, max_length=128)
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    status: str | None = None
    notes: str | None = None
    tags: list[str] | None = None


class LocationBody(BaseModel):
    model_config = {"extra": "forbid"}
    label: str | None = Field(default=None, max_length=64)
    address_line_1: str = Field(min_length=1, max_length=255)
    address_line_2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=128)
    state: str | None = Field(default=None, max_length=64)
    postal_code: str | None = Field(default=None, max_length=32)
    country: str | None = Field(default=None, max_length=2)
    latitude: float | None = None
    longitude: float | None = None
    access_instructions: str | None = None
    is_primary: bool | None = None


class LocationUpdateBody(BaseModel):
    model_config = {"extra": "forbid"}
    label: str | None = Field(default=None, max_length=64)
    address_line_1: str | None = Field(default=None, max_length=255)
    address_line_2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=128)
    state: str | None = Field(default=None, max_length=64)
    postal_code: str | None = Field(default=None, max_length=32)
    country: str | None = Field(default=None, max_length=2)
    latitude: float | None = None
    longitude: float | None = None
    access_instructions: str | None = None
    is_primary: bool | None = None


class TagBody(BaseModel):
    model_config = {"extra": "forbid"}
    name: str = Field(min_length=1, max_length=64)


class NoteBody(BaseModel):
    model_config = {"extra": "forbid"}
    body: str = Field(min_length=1, max_length=10000)


@router.get("")
def list_customers(
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    q: str | None = Query(default=None, max_length=256),
    search: str | None = Query(default=None, max_length=256),
    status: str | None = Query(default=None, max_length=32),
    include_archived: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
) -> dict[str, Any]:
    try:
        return CustomerService(session).search(
            user.tenant_id,
            q=q or search,
            status=status,
            include_archived=include_archived,
            limit=limit,
            cursor=cursor,
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/search")
def search_customers(
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    q: str = Query(min_length=1, max_length=256),
    status: str | None = Query(default=None, max_length=32),
    include_archived: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
) -> dict[str, Any]:
    try:
        return CustomerService(session).search(
            user.tenant_id,
            q=q,
            status=status,
            include_archived=include_archived,
            limit=limit,
            cursor=cursor,
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/tags")
def list_tags(
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    return {"tags": CustomerService(session).list_tags(user.tenant_id)}


@router.post("")
def create_customer(
    body: CustomerCreateBody,
    user: CurrentUser = Depends(_require_create),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        customer = CustomerService(session).create(
            user.tenant_id,
            name=body.name,
            display_name=body.display_name,
            first_name=body.first_name,
            last_name=body.last_name,
            phone=body.phone,
            email=body.email,
            address=body.address,
            status=body.status,
            notes=body.notes,
            tags=body.tags,
            actor=_actor(user),
        )
        session.commit()
        return {"customer": customer}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.get("/{customer_id}")
def get_customer(
    customer_id: UUID,
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        customer = CustomerService(session).get(
            user.tenant_id, customer_id, include_locations=True
        )
        return {"customer": customer}
    except Exception as exc:
        raise _http(exc) from exc


@router.patch("/{customer_id}")
def update_customer(
    customer_id: UUID,
    body: CustomerUpdateBody,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        payload = body.model_dump(exclude_unset=True)
        customer = CustomerService(session).update(
            user.tenant_id, customer_id, actor=_actor(user), **payload
        )
        session.commit()
        return {"customer": customer}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.delete("/{customer_id}")
def archive_customer(
    customer_id: UUID,
    user: CurrentUser = Depends(_require_delete),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        customer = CustomerService(session).archive(
            user.tenant_id, customer_id, actor=_actor(user)
        )
        session.commit()
        return {"customer": customer}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.post("/{customer_id}/restore")
def restore_customer(
    customer_id: UUID,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        customer = CustomerService(session).restore(
            user.tenant_id, customer_id, actor=_actor(user)
        )
        session.commit()
        return {"customer": customer}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.get("/{customer_id}/locations")
def list_locations(
    customer_id: UUID,
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    include_archived: bool = Query(default=False),
) -> dict[str, Any]:
    try:
        locations = CustomerService(session).locations.list_locations(
            user.tenant_id, customer_id, include_archived=include_archived
        )
        return {"locations": locations}
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/{customer_id}/locations")
def create_location(
    customer_id: UUID,
    body: LocationBody,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        location = CustomerService(session).locations.create_location(
            user.tenant_id,
            customer_id,
            address_line_1=body.address_line_1,
            address_line_2=body.address_line_2,
            city=body.city,
            state=body.state,
            postal_code=body.postal_code,
            country=body.country,
            latitude=body.latitude,
            longitude=body.longitude,
            access_instructions=body.access_instructions,
            label=body.label,
            is_primary=body.is_primary,
            actor=_actor(user),
        )
        session.commit()
        return {"location": location}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.patch("/{customer_id}/locations/{location_id}")
def update_location(
    customer_id: UUID,
    location_id: UUID,
    body: LocationUpdateBody,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        payload = body.model_dump(exclude_unset=True)
        location = CustomerService(session).locations.update_location(
            user.tenant_id,
            customer_id,
            location_id,
            actor=_actor(user),
            **payload,
        )
        session.commit()
        return {"location": location}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.post("/{customer_id}/locations/{location_id}/primary")
def set_primary_location(
    customer_id: UUID,
    location_id: UUID,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        location = CustomerService(session).locations.set_primary(
            user.tenant_id, customer_id, location_id, actor=_actor(user)
        )
        session.commit()
        return {"location": location}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.delete("/{customer_id}/locations/{location_id}")
def archive_location(
    customer_id: UUID,
    location_id: UUID,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        location = CustomerService(session).locations.archive_location(
            user.tenant_id, customer_id, location_id, actor=_actor(user)
        )
        session.commit()
        return {"location": location}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.post("/{customer_id}/tags")
def add_tag(
    customer_id: UUID,
    body: TagBody,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        customer = CustomerService(session).add_tag(
            user.tenant_id, customer_id, body.name, actor=_actor(user)
        )
        session.commit()
        return {"customer": customer}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.delete("/{customer_id}/tags/{tag_id}")
def remove_tag(
    customer_id: UUID,
    tag_id: UUID,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        customer = CustomerService(session).remove_tag(
            user.tenant_id, customer_id, tag_id, actor=_actor(user)
        )
        session.commit()
        return {"customer": customer}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.post("/{customer_id}/notes")
def add_note(
    customer_id: UUID,
    body: NoteBody,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        note = CustomerService(session).add_note(
            user.tenant_id,
            customer_id,
            body.body,
            author_user_id=user.user_id,
            actor=_actor(user),
        )
        session.commit()
        return {"note": note}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.get("/{customer_id}/timeline")
def customer_timeline(
    customer_id: UUID,
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    event_type: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    since: datetime | None = None,
    until: datetime | None = None,
) -> dict[str, Any]:
    authz = AuthorizationService(session)
    allowed: set[str] = set()
    for _etype, perm in TIMELINE_PERMISSIONS.items():
        try:
            authz.require_permission(user.tenant_id, user.user_id, perm)
            allowed.add(perm)
        except RbacError:
            continue
    allowed.add("customers.read")
    try:
        return CustomerService(session).timeline(
            user.tenant_id,
            customer_id,
            allowed_permission_keys=frozenset(allowed),
            event_type=event_type,
            limit=limit,
            cursor=cursor,
            since=since,
            until=until,
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/{customer_id}/duplicates")
def potential_duplicates(
    customer_id: UUID,
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "duplicates": CustomerService(session).find_potential_duplicates(
                user.tenant_id, customer_id
            )
        }
    except Exception as exc:
        raise _http(exc) from exc

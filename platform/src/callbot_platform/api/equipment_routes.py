"""Equipment / assets APIs (Phase 21)."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from callbot_platform.api.deps import CurrentUser, db_dep, require_entitled_permission
from callbot_platform.crm.equipment import EquipmentService
from callbot_platform.crm.errors import CrmError
from callbot_platform.rbac.errors import RbacError

router = APIRouter(prefix="/api/admin/crm", tags=["equipment"])

_require_read = require_entitled_permission("equipment.read")
_require_create = require_entitled_permission("equipment.create")
_require_update = require_entitled_permission("equipment.update")
_require_delete = require_entitled_permission("equipment.delete")


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, RbacError):
        return HTTPException(
            status_code=403, detail={"code": exc.code, "message": str(exc)}
        )
    if isinstance(exc, CrmError):
        status = (
            404 if exc.code == "not_found" or exc.code.endswith("_not_found") else 400
        )
        if exc.code in {"serial_conflict", "idempotency_conflict"}:
            status = 409
        return HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        )
    return HTTPException(
        status_code=500, detail={"code": "internal", "message": "Internal error"}
    )


def _actor(user: CurrentUser) -> str:
    return user.email or str(user.user_id)


class EquipmentCreateBody(BaseModel):
    model_config = {"extra": "forbid"}
    customer_id: UUID
    manufacturer: str = Field(min_length=1, max_length=255)
    model: str = Field(min_length=1, max_length=255)
    location_id: UUID | None = None
    serial_number: str | None = Field(default=None, max_length=128)
    installation_date: date | None = None
    warranty_start_date: date | None = None
    warranty_end_date: date | None = None
    warranty_provider: str | None = Field(default=None, max_length=255)
    warranty_notes: str | None = Field(default=None, max_length=5000)
    status: str | None = Field(default=None, max_length=32)
    notes: str | None = Field(default=None, max_length=8000)


class EquipmentUpdateBody(BaseModel):
    model_config = {"extra": "forbid"}
    manufacturer: str | None = Field(default=None, max_length=255)
    model: str | None = Field(default=None, max_length=255)
    serial_number: str | None = Field(default=None, max_length=128)
    location_id: UUID | None = None
    clear_location: bool = False
    installation_date: date | None = None
    warranty_start_date: date | None = None
    warranty_end_date: date | None = None
    warranty_provider: str | None = Field(default=None, max_length=255)
    warranty_notes: str | None = Field(default=None, max_length=5000)
    status: str | None = Field(default=None, max_length=32)
    notes: str | None = Field(default=None, max_length=8000)


@router.get("/equipment")
def list_equipment(
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    q: str | None = Query(default=None),
    customer_id: UUID | None = Query(default=None),  # noqa: B008
    location_id: UUID | None = Query(default=None),  # noqa: B008
    status: str | None = Query(default=None),
    manufacturer: str | None = Query(default=None),
    model: str | None = Query(default=None),
    serial_number: str | None = Query(default=None),
    warranty_status: str | None = Query(default=None),
    include_archived: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    try:
        return EquipmentService(session).list(
            user.tenant_id,
            q=q,
            customer_id=customer_id,
            location_id=location_id,
            status=status,
            manufacturer=manufacturer,
            model=model,
            serial_number=serial_number,
            warranty_status=warranty_status,
            include_archived=include_archived,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/equipment", status_code=201)
def create_equipment(
    body: EquipmentCreateBody,
    user: CurrentUser = Depends(_require_create),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        row = EquipmentService(session).create(
            user.tenant_id,
            customer_id=body.customer_id,
            manufacturer=body.manufacturer,
            model=body.model,
            actor=_actor(user),
            location_id=body.location_id,
            serial_number=body.serial_number,
            installation_date=body.installation_date,
            warranty_start_date=body.warranty_start_date,
            warranty_end_date=body.warranty_end_date,
            warranty_provider=body.warranty_provider,
            warranty_notes=body.warranty_notes,
            status=body.status,
            notes=body.notes,
        )
        session.commit()
        return {"equipment": row}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.get("/equipment/{equipment_id}")
def get_equipment(
    equipment_id: UUID,
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {"equipment": EquipmentService(session).get(user.tenant_id, equipment_id)}
    except Exception as exc:
        raise _http(exc) from exc


@router.patch("/equipment/{equipment_id}")
def update_equipment(
    equipment_id: UUID,
    body: EquipmentUpdateBody,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        fields = body.model_dump(exclude_unset=True)
        fields.pop("clear_location", None)
        row = EquipmentService(session).update(
            user.tenant_id,
            equipment_id,
            actor=_actor(user),
            clear_location=body.clear_location,
            **fields,
        )
        session.commit()
        return {"equipment": row}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.delete("/equipment/{equipment_id}")
def delete_equipment(
    equipment_id: UUID,
    user: CurrentUser = Depends(_require_delete),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        result = EquipmentService(session).delete(
            user.tenant_id, equipment_id, actor=_actor(user)
        )
        session.commit()
        return result
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.get("/equipment/{equipment_id}/history")
def equipment_history(
    equipment_id: UUID,
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    try:
        return EquipmentService(session).history.history(
            user.tenant_id, equipment_id, limit=limit, offset=offset
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/equipment/{equipment_id}/attachments")
def list_attachments(
    equipment_id: UUID,
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "attachments": EquipmentService(session).attachments.list(
                user.tenant_id, equipment_id
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/equipment/{equipment_id}/attachments", status_code=201)
async def upload_attachment(
    equipment_id: UUID,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    file: UploadFile = File(...),  # noqa: B008
    kind: str = Form(default="PHOTO"),
) -> dict[str, Any]:
    try:
        data = await file.read()
        att = EquipmentService(session).attachments.upload(
            user.tenant_id,
            equipment_id,
            filename=file.filename or "upload",
            content_type=file.content_type or "application/octet-stream",
            data=data,
            actor=_actor(user),
            kind=kind,
        )
        session.commit()
        return {"attachment": att}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.delete("/equipment/{equipment_id}/attachments/{attachment_id}")
def archive_attachment(
    equipment_id: UUID,
    attachment_id: UUID,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        att = EquipmentService(session).attachments.archive(
            user.tenant_id,
            equipment_id,
            attachment_id,
            actor=_actor(user),
        )
        session.commit()
        return {"attachment": att}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc

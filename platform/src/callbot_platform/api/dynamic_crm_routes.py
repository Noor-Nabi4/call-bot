"""Admin APIs for the Dynamic CRM Engine (modules, fields, objects, relationships)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from callbot_platform.api.deps import CurrentUser, db_dep, require_permission
from callbot_platform.dynamic_crm import (
    CustomObjectService,
    DynamicCrmError,
    EffectiveCrmConfigurationService,
    FieldDefinitionService,
    ModuleConfigService,
    RelationshipService,
)
from callbot_platform.dynamic_crm.types import OWNER_SCOPE_MODULE, OWNER_SCOPE_OBJECT

router = APIRouter(prefix="/api/admin/crm", tags=["dynamic-crm"])

_require_org_read = require_permission("organization.read")
_require_crm_configure = require_permission("crm.configure")
_require_custom_objects_read = require_permission("custom_objects.read")
_require_custom_objects_manage = require_permission("custom_objects.manage")


def _http(exc: DynamicCrmError) -> HTTPException:
    status = 400
    if exc.code == "not_found":
        status = 404
    if exc.code in {"module_disabled", "object_disabled", "relationship_disabled"}:
        status = 403
    return HTTPException(
        status_code=status, detail={"code": exc.code, "message": str(exc)}
    )


class ModuleEnableBody(BaseModel):
    model_config = {"extra": "forbid"}
    enabled: bool


class ModuleReorderBody(BaseModel):
    model_config = {"extra": "forbid"}
    module_keys: list[str] = Field(min_length=1)


class FieldCreateBody(BaseModel):
    model_config = {"extra": "forbid"}
    field_key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=128)
    field_type: str = Field(min_length=1, max_length=32)
    description: str = ""
    required: bool = False
    enabled: bool = True
    display_order: int = 100
    default_value: Any = None
    configuration: dict[str, Any] | None = None
    validation_rules: dict[str, Any] | None = None


class FieldUpdateBody(BaseModel):
    model_config = {"extra": "forbid"}
    label: str | None = None
    description: str | None = None
    required: bool | None = None
    enabled: bool | None = None
    display_order: int | None = None
    default_value: Any = None
    configuration: dict[str, Any] | None = None
    validation_rules: dict[str, Any] | None = None


class ObjectCreateBody(BaseModel):
    model_config = {"extra": "forbid"}
    object_key: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    plural_name: str | None = None
    description: str = ""
    icon: str = "box"
    display_order: int = 100


class ObjectUpdateBody(BaseModel):
    model_config = {"extra": "forbid"}
    name: str | None = None
    plural_name: str | None = None
    description: str | None = None
    icon: str | None = None
    enabled: bool | None = None
    display_order: int | None = None


class RecordBody(BaseModel):
    model_config = {"extra": "forbid"}
    values: dict[str, Any] = Field(default_factory=dict)


class RelationshipCreateBody(BaseModel):
    model_config = {"extra": "forbid"}
    relationship_key: str
    source_type: str
    source_key: str
    target_type: str
    target_key: str
    cardinality: str
    label: str = ""
    inverse_label: str = ""
    required: bool = False


class RelationshipUpdateBody(BaseModel):
    model_config = {"extra": "forbid"}
    label: str | None = None
    inverse_label: str | None = None
    enabled: bool | None = None
    required: bool | None = None


class LinkBody(BaseModel):
    model_config = {"extra": "forbid"}
    target_record_id: UUID


class FilterBody(BaseModel):
    model_config = {"extra": "forbid"}
    filters: list[dict[str, Any]] = Field(default_factory=list)
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    include_archived: bool = False


@router.get("/configuration")
def get_effective_configuration(
    user: CurrentUser = Depends(_require_org_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    return {
        "configuration": EffectiveCrmConfigurationService(session).get(user.tenant_id)
    }


@router.get("/modules")
def list_modules(
    user: CurrentUser = Depends(_require_org_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    return {"modules": ModuleConfigService(session).list_modules(user.tenant_id)}


@router.patch("/modules/{module_key}")
def patch_module(
    module_key: str,
    body: ModuleEnableBody,
    user: CurrentUser = Depends(_require_crm_configure),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        module = ModuleConfigService(session).set_enabled(
            user.tenant_id, module_key, enabled=body.enabled, actor=user.email
        )
        return {"module": module}
    except DynamicCrmError as exc:
        raise _http(exc) from exc


@router.put("/modules/order")
def reorder_modules(
    body: ModuleReorderBody,
    user: CurrentUser = Depends(_require_crm_configure),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        modules = ModuleConfigService(session).reorder(
            user.tenant_id, body.module_keys, actor=user.email
        )
        return {"modules": modules}
    except DynamicCrmError as exc:
        raise _http(exc) from exc


@router.get("/modules/{module_key}/fields")
def list_module_fields(
    module_key: str,
    user: CurrentUser = Depends(_require_org_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        ModuleConfigService(session).require_enabled(user.tenant_id, module_key)
        fields = FieldDefinitionService(session).list_fields(
            user.tenant_id,
            owner_scope=OWNER_SCOPE_MODULE,
            owner_key=module_key.upper(),
            include_disabled=True,
        )
        return {"fields": fields}
    except DynamicCrmError as exc:
        raise _http(exc) from exc


@router.post("/modules/{module_key}/fields")
def create_module_field(
    module_key: str,
    body: FieldCreateBody,
    user: CurrentUser = Depends(_require_crm_configure),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        ModuleConfigService(session).require_enabled(user.tenant_id, module_key)
        field = FieldDefinitionService(session).create_field(
            user.tenant_id,
            owner_scope=OWNER_SCOPE_MODULE,
            owner_key=module_key.upper(),
            field_key=body.field_key,
            label=body.label,
            field_type=body.field_type,
            actor=user.email,
            description=body.description,
            required=body.required,
            enabled=body.enabled,
            display_order=body.display_order,
            default_value=body.default_value,
            configuration=body.configuration,
            validation_rules=body.validation_rules,
        )
        return {"field": field}
    except DynamicCrmError as exc:
        raise _http(exc) from exc


@router.patch("/modules/{module_key}/fields/{field_id}")
def update_module_field(
    module_key: str,
    field_id: UUID,
    body: FieldUpdateBody,
    user: CurrentUser = Depends(_require_crm_configure),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        FieldDefinitionService(session).require_field_for_owner(
            user.tenant_id,
            field_id,
            owner_scope=OWNER_SCOPE_MODULE,
            owner_key=module_key.upper(),
        )
        field = FieldDefinitionService(session).update_field(
            user.tenant_id,
            field_id,
            actor=user.email,
            **body.model_dump(exclude_unset=True),
        )
        return {"field": field}
    except DynamicCrmError as exc:
        raise _http(exc) from exc


@router.delete("/modules/{module_key}/fields/{field_id}")
def disable_module_field(
    module_key: str,
    field_id: UUID,
    user: CurrentUser = Depends(_require_crm_configure),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        FieldDefinitionService(session).require_field_for_owner(
            user.tenant_id,
            field_id,
            owner_scope=OWNER_SCOPE_MODULE,
            owner_key=module_key.upper(),
        )
        field = FieldDefinitionService(session).disable_field(
            user.tenant_id, field_id, actor=user.email
        )
        return {"field": field}
    except DynamicCrmError as exc:
        raise _http(exc) from exc


@router.get("/objects")
def list_objects(
    user: CurrentUser = Depends(_require_custom_objects_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    return {"objects": CustomObjectService(session).list_definitions(user.tenant_id)}


@router.post("/objects")
def create_object(
    body: ObjectCreateBody,
    user: CurrentUser = Depends(_require_custom_objects_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        obj = CustomObjectService(session).create_definition(
            user.tenant_id,
            object_key=body.object_key,
            name=body.name,
            actor=user.email,
            plural_name=body.plural_name,
            description=body.description,
            icon=body.icon,
            display_order=body.display_order,
        )
        return {"object": obj}
    except DynamicCrmError as exc:
        raise _http(exc) from exc


@router.patch("/objects/{object_id}")
def update_object(
    object_id: UUID,
    body: ObjectUpdateBody,
    user: CurrentUser = Depends(_require_custom_objects_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        obj = CustomObjectService(session).update_definition(
            user.tenant_id,
            object_id,
            actor=user.email,
            **body.model_dump(exclude_unset=True),
        )
        return {"object": obj}
    except DynamicCrmError as exc:
        raise _http(exc) from exc


@router.delete("/objects/{object_id}")
def archive_object(
    object_id: UUID,
    user: CurrentUser = Depends(_require_custom_objects_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        obj = CustomObjectService(session).archive_definition(
            user.tenant_id, object_id, actor=user.email
        )
        return {"object": obj}
    except DynamicCrmError as exc:
        raise _http(exc) from exc


@router.get("/objects/{object_id}/fields")
def list_object_fields(
    object_id: UUID,
    user: CurrentUser = Depends(_require_custom_objects_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        obj = next(
            o
            for o in CustomObjectService(session).list_definitions(user.tenant_id)
            if o["id"] == str(object_id)
        )
        fields = FieldDefinitionService(session).list_fields(
            user.tenant_id,
            owner_scope=OWNER_SCOPE_OBJECT,
            owner_key=obj["object_key"],
            include_disabled=True,
        )
        return {"fields": fields, "object": obj}
    except StopIteration as exc:
        raise HTTPException(
            status_code=404, detail={"code": "not_found", "message": "Not found"}
        ) from exc
    except DynamicCrmError as e:
        raise _http(e) from e


@router.post("/objects/{object_id}/fields")
def create_object_field(
    object_id: UUID,
    body: FieldCreateBody,
    user: CurrentUser = Depends(_require_custom_objects_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        obj = next(
            o
            for o in CustomObjectService(session).list_definitions(user.tenant_id)
            if o["id"] == str(object_id)
        )
        field = FieldDefinitionService(session).create_field(
            user.tenant_id,
            owner_scope=OWNER_SCOPE_OBJECT,
            owner_key=obj["object_key"],
            field_key=body.field_key,
            label=body.label,
            field_type=body.field_type,
            actor=user.email,
            description=body.description,
            required=body.required,
            enabled=body.enabled,
            display_order=body.display_order,
            default_value=body.default_value,
            configuration=body.configuration,
            validation_rules=body.validation_rules,
        )
        return {"field": field}
    except StopIteration as exc:
        raise HTTPException(
            status_code=404, detail={"code": "not_found", "message": "Not found"}
        ) from exc
    except DynamicCrmError as e:
        raise _http(e) from e


@router.post("/objects/{object_id}/records")
def create_object_record(
    object_id: UUID,
    body: RecordBody,
    user: CurrentUser = Depends(_require_custom_objects_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        record = CustomObjectService(session).create_record(
            user.tenant_id, object_id, actor=user.email, values=body.values
        )
        return {"record": record}
    except DynamicCrmError as exc:
        raise _http(exc) from exc


@router.get("/objects/{object_id}/records")
def list_object_records(
    object_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(_require_custom_objects_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return CustomObjectService(session).list_records(
            user.tenant_id, object_id, limit=limit, offset=offset
        )
    except DynamicCrmError as exc:
        raise _http(exc) from exc


@router.post("/objects/{object_id}/records/search")
def search_object_records(
    object_id: UUID,
    body: FilterBody,
    user: CurrentUser = Depends(_require_custom_objects_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return CustomObjectService(session).list_records(
            user.tenant_id,
            object_id,
            limit=body.limit,
            offset=body.offset,
            include_archived=body.include_archived,
            filters=body.filters or None,
        )
    except DynamicCrmError as exc:
        raise _http(exc) from exc


@router.get("/objects/{object_id}/records/{record_id}")
def get_object_record(
    object_id: UUID,
    record_id: UUID,
    user: CurrentUser = Depends(_require_custom_objects_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "record": CustomObjectService(session).get_record(
                user.tenant_id, object_id, record_id
            )
        }
    except DynamicCrmError as exc:
        raise _http(exc) from exc


@router.patch("/objects/{object_id}/records/{record_id}")
def update_object_record(
    object_id: UUID,
    record_id: UUID,
    body: RecordBody,
    user: CurrentUser = Depends(_require_custom_objects_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        record = CustomObjectService(session).update_record(
            user.tenant_id,
            object_id,
            record_id,
            actor=user.email,
            values=body.values,
        )
        return {"record": record}
    except DynamicCrmError as exc:
        raise _http(exc) from exc


@router.delete("/objects/{object_id}/records/{record_id}")
def archive_object_record(
    object_id: UUID,
    record_id: UUID,
    user: CurrentUser = Depends(_require_custom_objects_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        record = CustomObjectService(session).archive_record(
            user.tenant_id, object_id, record_id, actor=user.email
        )
        return {"record": record}
    except DynamicCrmError as exc:
        raise _http(exc) from exc


@router.get("/relationships")
def list_relationships(
    user: CurrentUser = Depends(_require_org_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    return {
        "relationships": RelationshipService(session).list_definitions(user.tenant_id)
    }


@router.post("/relationships")
def create_relationship(
    body: RelationshipCreateBody,
    user: CurrentUser = Depends(_require_crm_configure),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        rel = RelationshipService(session).create_definition(
            user.tenant_id,
            relationship_key=body.relationship_key,
            source_type=body.source_type,
            source_key=body.source_key,
            target_type=body.target_type,
            target_key=body.target_key,
            cardinality=body.cardinality,
            actor=user.email,
            label=body.label,
            inverse_label=body.inverse_label,
            required=body.required,
        )
        return {"relationship": rel}
    except DynamicCrmError as exc:
        raise _http(exc) from exc


@router.patch("/relationships/{relationship_id}")
def update_relationship(
    relationship_id: UUID,
    body: RelationshipUpdateBody,
    user: CurrentUser = Depends(_require_crm_configure),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        rel = RelationshipService(session).update_definition(
            user.tenant_id,
            relationship_id,
            actor=user.email,
            **body.model_dump(exclude_unset=True),
        )
        return {"relationship": rel}
    except DynamicCrmError as exc:
        raise _http(exc) from exc


@router.delete("/relationships/{relationship_id}")
def disable_relationship(
    relationship_id: UUID,
    user: CurrentUser = Depends(_require_crm_configure),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        RelationshipService(session).delete_definition(
            user.tenant_id, relationship_id, actor=user.email
        )
        return {"ok": True}
    except DynamicCrmError as exc:
        raise _http(exc) from exc


@router.get("/{entity_type}/{entity_key}/{record_id}/relationships")
def list_record_relationships(
    entity_type: str,
    entity_key: str,
    record_id: UUID,
    user: CurrentUser = Depends(_require_org_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        links = RelationshipService(session).list_links_for_record(
            user.tenant_id,
            entity_type=entity_type,
            entity_key=entity_key,
            record_id=record_id,
        )
        return {"relationships": links}
    except DynamicCrmError as exc:
        raise _http(exc) from exc


@router.post("/{entity_type}/{entity_key}/{record_id}/relationships/{relationship_key}")
def create_record_relationship_link(
    entity_type: str,
    entity_key: str,
    record_id: UUID,
    relationship_key: str,
    body: LinkBody,
    user: CurrentUser = Depends(_require_crm_configure),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        RelationshipService(session).assert_path_matches_definition(
            user.tenant_id,
            relationship_key=relationship_key,
            entity_type=entity_type,
            entity_key=entity_key,
            record_id=record_id,
        )
        link = RelationshipService(session).link(
            user.tenant_id,
            relationship_key=relationship_key,
            source_record_id=record_id,
            target_record_id=body.target_record_id,
            actor=user.email,
        )
        return {"link": link}
    except DynamicCrmError as exc:
        raise _http(exc) from exc


@router.delete(
    "/{entity_type}/{entity_key}/{record_id}/relationships/"
    "{relationship_key}/{target_id}"
)
def delete_record_relationship_link(
    entity_type: str,
    entity_key: str,
    record_id: UUID,
    relationship_key: str,
    target_id: UUID,
    user: CurrentUser = Depends(_require_crm_configure),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        RelationshipService(session).assert_path_matches_definition(
            user.tenant_id,
            relationship_key=relationship_key,
            entity_type=entity_type,
            entity_key=entity_key,
            record_id=record_id,
        )
        RelationshipService(session).unlink(
            user.tenant_id,
            relationship_key=relationship_key,
            source_record_id=record_id,
            target_record_id=target_id,
            actor=user.email,
        )
        return {"ok": True}
    except DynamicCrmError as exc:
        raise _http(exc) from exc

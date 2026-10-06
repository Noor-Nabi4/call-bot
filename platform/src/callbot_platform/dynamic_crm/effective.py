"""Resolve effective CRM configuration for an organization."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from callbot_platform.business_config.modules import list_modules, module_permission_map
from callbot_platform.dynamic_crm.config_cache import (
    get_cached_effective,
    set_cached_effective,
)
from callbot_platform.dynamic_crm.fields import FieldDefinitionService
from callbot_platform.dynamic_crm.modules import ModuleConfigService
from callbot_platform.dynamic_crm.objects import CustomObjectService
from callbot_platform.dynamic_crm.relationships import RelationshipService
from callbot_platform.dynamic_crm.types import FIELD_TYPES, OWNER_SCOPE_MODULE
from callbot_platform.organization import OrganizationService


class EffectiveCrmConfigurationService:
    """Authoritative effective schema for APIs, UI navigation, and AI tools."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(
        self,
        tenant_id: UUID,
        *,
        include_fields: bool = True,
        include_objects: bool = True,
        include_relationships: bool = True,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        # Full payloads only — partial projections skip cache to avoid stale subsets.
        cacheable = include_fields and include_objects and include_relationships
        if use_cache and cacheable:
            cached = get_cached_effective(tenant_id)
            if cached is not None:
                return cached

        payload = self._build(
            tenant_id,
            include_fields=include_fields,
            include_objects=include_objects,
            include_relationships=include_relationships,
        )
        if cacheable:
            set_cached_effective(tenant_id, payload)
        return payload

    def _build(
        self,
        tenant_id: UUID,
        *,
        include_fields: bool,
        include_objects: bool,
        include_relationships: bool,
    ) -> dict[str, Any]:
        from callbot_platform.crm_config import CrmSetupService

        org = OrganizationService(self._session).get(tenant_id)
        cfg = CrmSetupService(self._session).get(tenant_id)
        modules = ModuleConfigService(self._session).list_modules(tenant_id)
        enabled_modules = [m for m in modules if m.get("enabled")]

        navigation = [
            {
                "key": m["key"],
                "label": m["name"],
                "href": m.get("href") or f"/crm/{m['key'].lower()}",
                "icon": m.get("icon"),
                "permission": m.get("read_permission"),
                "display_order": m.get("display_order"),
                "category": m.get("category"),
            }
            for m in enabled_modules
        ]
        navigation.sort(key=lambda n: (n["display_order"] or 100, n["label"]))

        fields_by_module: dict[str, list[dict[str, Any]]] = {}
        if include_fields:
            field_svc = FieldDefinitionService(self._session)
            for m in enabled_modules:
                if not m.get("supports_custom_fields", True):
                    continue
                fields_by_module[m["key"]] = field_svc.list_fields(
                    tenant_id,
                    owner_scope=OWNER_SCOPE_MODULE,
                    owner_key=m["key"],
                )

        objects: list[dict[str, Any]] = []
        if include_objects:
            objects = [
                o
                for o in CustomObjectService(self._session).list_definitions(tenant_id)
                if o.get("enabled") and not o.get("archived_at")
            ]
            for obj in objects:
                navigation.append(
                    {
                        "key": f"OBJECT:{obj['object_key']}",
                        "label": obj["plural_name"] or obj["name"],
                        "href": f"/crm/objects/{obj['id']}",
                        "icon": obj.get("icon") or "box",
                        "permission": "custom_objects.read",
                        "display_order": obj.get("display_order", 200),
                        "category": "custom",
                    }
                )
            navigation.sort(key=lambda n: (n["display_order"] or 100, n["label"]))

        relationships: list[dict[str, Any]] = []
        if include_relationships:
            relationships = [
                r
                for r in RelationshipService(self._session).list_definitions(tenant_id)
                if r.get("enabled")
            ]

        return {
            "organization": {
                "industry_key": org.get("industry_key"),
                "business_model": org.get("business_type"),
                "timezone": org.get("timezone"),
                "currency": org.get("currency"),
            },
            "setup_completed": bool(cfg and cfg.get("setup_completed")),
            "template_key": cfg.get("template_key") if cfg else None,
            "platform_modules": list_modules(),
            "modules": modules,
            "enabled_modules": enabled_modules,
            "navigation": navigation,
            "fields_by_module": fields_by_module,
            "custom_objects": objects,
            "relationships": relationships,
            "permission_map": module_permission_map(),
            "field_types": sorted(FIELD_TYPES),
        }

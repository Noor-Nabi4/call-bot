"""Agent profile repository (multi-profile per tenant)."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.agent_templates import get_template
from callbot_platform.crm.errors import CrmError, as_str_list
from callbot_platform.db.models import AgentProfile, KnowledgeArticle, Tenant
from callbot_platform.db.models.agent_profile import (
    default_business_hours,
    default_enabled_tools,
)
from callbot_platform.telephony.audit import write_audit

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_VALID_TYPES = frozenset(
    {
        "receptionist",
        "support",
        "sales",
        "booking",
        "help_desk",
        "call_center",
        "custom",
    }
)
_VALID_STATUS = frozenset({"active", "archived"})


def _slugify(name: str) -> str:
    base = _SLUG_RE.sub("-", (name or "").strip().lower()).strip("-")
    return base or "agent"


class AgentProfileRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(
        self, tenant_id: UUID, *, include_archived: bool = False
    ) -> list[dict[str, Any]]:
        stmt = select(AgentProfile).where(AgentProfile.tenant_id == tenant_id)
        if not include_archived:
            stmt = stmt.where(AgentProfile.status == "active")
        stmt = stmt.order_by(AgentProfile.is_default.desc(), AgentProfile.name.asc())
        return [self._serialize(row) for row in self._session.scalars(stmt).all()]

    def get(self, tenant_id: UUID, profile_id: UUID) -> dict[str, Any] | None:
        row = self._owned(tenant_id, profile_id)
        return None if row is None else self._serialize(row)

    def get_default(self, tenant_id: UUID) -> dict[str, Any] | None:
        row = self._default_row(tenant_id)
        return None if row is None else self._serialize(row)

    def get_voice_profile(
        self,
        tenant_id: UUID,
        *,
        business_name: str,
        profile_id: UUID | None = None,
    ) -> dict[str, Any] | None:
        if profile_id is not None:
            row = self._owned(tenant_id, profile_id)
        else:
            row = self._default_row(tenant_id)
        if row is None or row.status != "active":
            return None
        return self._to_agent_profile(row, business_name=business_name)

    def get_voice_profile_meta(
        self, tenant_id: UUID, *, profile_id: UUID | None = None
    ) -> dict[str, Any] | None:
        if profile_id is not None:
            row = self._owned(tenant_id, profile_id)
        else:
            row = self._default_row(tenant_id)
        if row is None:
            return None
        return {
            "tenant_id": str(row.tenant_id),
            "agent_profile_id": str(row.id),
            "profile_version": int(row.profile_version or 1),
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "status": row.status,
        }

    def resolve_profile_id(
        self,
        tenant_id: UUID,
        *,
        explicit_profile_id: UUID | None = None,
        phone_profile_id: UUID | None = None,
    ) -> UUID | None:
        """Resolve agent profile: explicit → phone assignment → tenant default."""
        if explicit_profile_id is not None:
            row = self._owned(tenant_id, explicit_profile_id)
            if row is not None and row.status == "active":
                return row.id
            return None
        if phone_profile_id is not None:
            row = self._owned(tenant_id, phone_profile_id)
            if row is not None and row.status == "active":
                return row.id
        default = self._default_row(tenant_id)
        if default is not None and default.status == "active":
            return default.id
        return None

    def create(
        self,
        tenant_id: UUID,
        *,
        name: str,
        agent_type: str = "receptionist",
        industry_key: str | None = None,
        is_default: bool = False,
        actor: str = "tenant_user",
        **fields: Any,
    ) -> dict[str, Any]:
        clean_name = (name or "").strip()
        if not clean_name:
            raise CrmError("invalid_name", "Profile name is required")
        atype = (agent_type or "custom").strip().lower()
        if atype not in _VALID_TYPES:
            raise CrmError("invalid_agent_type", f"Unsupported agent_type: {atype}")

        slug = self._unique_slug(tenant_id, _slugify(clean_name))
        if is_default:
            self._clear_defaults(tenant_id)

        tools = fields.pop("enabled_tools", None) or default_enabled_tools()
        hours = fields.pop("business_hours", None) or default_business_hours()
        langs = as_str_list(fields.pop("supported_languages", None))
        language = str(fields.get("language") or "en")
        if not langs:
            langs = [language]

        row = AgentProfile(
            tenant_id=tenant_id,
            name=clean_name,
            slug=slug,
            agent_type=atype,
            industry_key=industry_key,
            status="active",
            is_default=is_default,
            business_prompt_facts=fields.get("business_prompt_facts") or {},
            voice=fields.get("voice") or "marin",
            language=language,
            greeting=fields.get("greeting"),
            assistant_name=fields.get("assistant_name"),
            business_description=fields.get("business_description"),
            tone=fields.get("tone"),
            supported_languages=langs,
            response_style=fields.get("response_style") or "concise",
            service_areas=as_str_list(fields.get("service_areas")),
            business_hours_summary=fields.get("business_hours_summary"),
            business_hours=hours,
            booking_rules=fields.get("booking_rules"),
            pricing_disclosure_policy=fields.get("pricing_disclosure_policy"),
            handoff_rules_text=fields.get("handoff_rules_text"),
            restricted_topics=as_str_list(fields.get("restricted_topics")),
            custom_instructions=fields.get("custom_instructions"),
            enabled_tools=tools,
            profile_version=1,
        )
        self._session.add(row)
        self._session.flush()

        if is_default or self._default_row(tenant_id) is None:
            self._set_tenant_default(tenant_id, row.id)
            row.is_default = True
            self._session.flush()

        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="agent_profile_created",
            resource_ids={"agent_profile_id": str(row.id)},
            payload_summary={"name": row.name, "slug": row.slug},
        )
        return self._serialize(row)

    def update(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        *,
        actor: str = "tenant_user",
        **fields: Any,
    ) -> dict[str, Any]:
        row = self._owned(tenant_id, profile_id)
        if row is None:
            raise CrmError("not_found", "Agent profile not found for tenant")

        before = int(row.profile_version or 1)
        changed: list[str] = []

        def _set(field: str, value: Any) -> None:
            if getattr(row, field) != value:
                setattr(row, field, value)
                changed.append(field)

        if "name" in fields and fields["name"] is not None:
            clean = str(fields["name"]).strip()
            if not clean:
                raise CrmError("invalid_name", "Profile name is required")
            _set("name", clean)
        if "agent_type" in fields and fields["agent_type"] is not None:
            atype = str(fields["agent_type"]).strip().lower()
            if atype not in _VALID_TYPES:
                raise CrmError("invalid_agent_type", f"Unsupported agent_type: {atype}")
            _set("agent_type", atype)
        if "status" in fields and fields["status"] is not None:
            status = str(fields["status"]).strip().lower()
            if status not in _VALID_STATUS:
                raise CrmError("invalid_status", f"Unsupported status: {status}")
            if status == "archived" and row.is_default:
                raise CrmError(
                    "cannot_archive_default",
                    "Set another default profile before archiving this one",
                )
            _set("status", status)
        if "industry_key" in fields:
            _set("industry_key", fields["industry_key"])

        mapping = {
            "business_prompt_facts": "business_prompt_facts",
            "voice": "voice",
            "language": "language",
            "greeting": "greeting",
            "assistant_name": "assistant_name",
            "business_description": "business_description",
            "tone": "tone",
            "response_style": "response_style",
            "business_hours_summary": "business_hours_summary",
            "business_hours": "business_hours",
            "booking_rules": "booking_rules",
            "pricing_disclosure_policy": "pricing_disclosure_policy",
            "handoff_rules_text": "handoff_rules_text",
            "custom_instructions": "custom_instructions",
            "enabled_tools": "enabled_tools",
        }
        for key, attr in mapping.items():
            if key in fields and fields[key] is not None:
                _set(attr, fields[key])
        if (
            "supported_languages" in fields
            and fields["supported_languages"] is not None
        ):
            _set("supported_languages", as_str_list(fields["supported_languages"]))
        if "service_areas" in fields and fields["service_areas"] is not None:
            _set("service_areas", as_str_list(fields["service_areas"]))
        if "restricted_topics" in fields and fields["restricted_topics"] is not None:
            _set("restricted_topics", as_str_list(fields["restricted_topics"]))

        if changed:
            row.profile_version = before + 1
            row.updated_at = datetime.now(UTC)
            self._session.flush()
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="agent_profile_updated",
                resource_ids={
                    "agent_profile_id": str(row.id),
                    "profile_version": str(row.profile_version),
                },
                payload_summary={"changed_fields": changed},
            )
        return self._serialize(row)

    def set_default(
        self, tenant_id: UUID, profile_id: UUID, *, actor: str = "tenant_user"
    ) -> dict[str, Any]:
        row = self._owned(tenant_id, profile_id)
        if row is None:
            raise CrmError("not_found", "Agent profile not found for tenant")
        if row.status != "active":
            raise CrmError("inactive_profile", "Only active profiles can be default")
        self._clear_defaults(tenant_id)
        row.is_default = True
        self._set_tenant_default(tenant_id, row.id)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="agent_profile_set_default",
            resource_ids={"agent_profile_id": str(row.id)},
        )
        return self._serialize(row)

    def apply_template(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        *,
        industry_key: str,
        actor: str = "tenant_user",
        seed_knowledge: bool = True,
    ) -> dict[str, Any]:
        template = get_template(industry_key)
        if template is None:
            raise CrmError(
                "unknown_template", f"Unknown industry template: {industry_key}"
            )
        defaults = template.profile_defaults()
        updated = self.update(
            tenant_id,
            profile_id,
            actor=actor,
            **defaults,
        )
        tenant = self._session.get(Tenant, tenant_id)
        if tenant is not None and tenant.industry_key is None:
            tenant.industry_key = template.key

        if seed_knowledge and template.suggested_articles:
            existing = self._session.scalars(
                select(KnowledgeArticle).where(
                    KnowledgeArticle.tenant_id == tenant_id,
                    KnowledgeArticle.agent_profile_id == profile_id,
                )
            ).all()
            titles = {a.title for a in existing}
            for article in template.suggested_articles:
                if article.title in titles:
                    continue
                self._session.add(
                    KnowledgeArticle(
                        tenant_id=tenant_id,
                        agent_profile_id=profile_id,
                        category=article.category,
                        title=article.title,
                        body=article.body,
                        tags=list(article.tags),
                        is_active=True,
                    )
                )
            self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="agent_profile_template_applied",
            resource_ids={"agent_profile_id": str(profile_id)},
            payload_summary={"industry_key": template.key},
        )
        return updated

    def archive(
        self, tenant_id: UUID, profile_id: UUID, *, actor: str = "tenant_user"
    ) -> dict[str, Any]:
        return self.update(tenant_id, profile_id, actor=actor, status="archived")

    def ensure_default_from_legacy_or_create(
        self, tenant_id: UUID, *, actor: str = "system"
    ) -> dict[str, Any]:
        existing = self.get_default(tenant_id)
        if existing is not None:
            return existing
        return self.create(
            tenant_id,
            name="Main Receptionist",
            agent_type="receptionist",
            is_default=True,
            actor=actor,
        )

    def _default_row(self, tenant_id: UUID) -> AgentProfile | None:
        tenant = self._session.get(Tenant, tenant_id)
        if tenant is not None and tenant.default_agent_profile_id is not None:
            row = self._owned(tenant_id, tenant.default_agent_profile_id)
            if row is not None:
                return row
        return self._session.scalar(
            select(AgentProfile).where(
                AgentProfile.tenant_id == tenant_id,
                AgentProfile.is_default.is_(True),
                AgentProfile.status == "active",
            )
        )

    def _owned(self, tenant_id: UUID, profile_id: UUID) -> AgentProfile | None:
        return self._session.scalar(
            select(AgentProfile).where(
                AgentProfile.id == profile_id,
                AgentProfile.tenant_id == tenant_id,
            )
        )

    def _clear_defaults(self, tenant_id: UUID) -> None:
        for row in self._session.scalars(
            select(AgentProfile).where(
                AgentProfile.tenant_id == tenant_id,
                AgentProfile.is_default.is_(True),
            )
        ).all():
            row.is_default = False

    def _set_tenant_default(self, tenant_id: UUID, profile_id: UUID) -> None:
        tenant = self._session.get(Tenant, tenant_id)
        if tenant is None:
            raise CrmError("tenant_not_found", "Tenant not found")
        tenant.default_agent_profile_id = profile_id

    def _unique_slug(self, tenant_id: UUID, base: str) -> str:
        candidate = base
        n = 2
        while self._session.scalar(
            select(AgentProfile.id).where(
                AgentProfile.tenant_id == tenant_id,
                AgentProfile.slug == candidate,
            )
        ):
            candidate = f"{base}-{n}"
            n += 1
        return candidate

    def _serialize(self, row: AgentProfile) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "tenant_id": str(row.tenant_id),
            "name": row.name,
            "slug": row.slug,
            "agent_type": row.agent_type,
            "industry_key": row.industry_key,
            "status": row.status,
            "is_default": bool(row.is_default),
            "business_prompt_facts": row.business_prompt_facts or {},
            "voice": row.voice,
            "language": row.language,
            "greeting": row.greeting,
            "assistant_name": row.assistant_name,
            "business_description": row.business_description,
            "tone": row.tone,
            "supported_languages": as_str_list(row.supported_languages),
            "response_style": row.response_style,
            "service_areas": as_str_list(row.service_areas),
            "business_hours_summary": row.business_hours_summary,
            "business_hours": row.business_hours or default_business_hours(),
            "booking_rules": row.booking_rules,
            "pricing_disclosure_policy": row.pricing_disclosure_policy,
            "handoff_rules_text": row.handoff_rules_text,
            "restricted_topics": as_str_list(row.restricted_topics),
            "custom_instructions": row.custom_instructions,
            "enabled_tools": row.enabled_tools or default_enabled_tools(),
            "profile_version": int(row.profile_version or 1),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    def _to_agent_profile(
        self, row: AgentProfile, *, business_name: str
    ) -> dict[str, Any]:
        settings = self._serialize(row)
        facts = settings.get("business_prompt_facts") or {}
        hours = settings.get("business_hours_summary") or facts.get("hours")
        hours_summary = hours.strip() or None if isinstance(hours, str) else None
        service_areas = as_str_list(settings.get("service_areas"))
        if not service_areas and facts.get("service_area"):
            service_areas = as_str_list(facts.get("service_area"))
        default_language = str(settings.get("language") or "en").strip() or "en"
        supported = as_str_list(settings.get("supported_languages"))
        if not supported:
            supported = [default_language]
        return {
            "id": settings["id"],
            "tenant_id": settings["tenant_id"],
            "agent_profile_id": settings["id"],
            "name": settings["name"],
            "slug": settings["slug"],
            "agent_type": settings["agent_type"],
            "industry_key": settings.get("industry_key"),
            "business_name": business_name.strip(),
            "assistant_name": settings.get("assistant_name"),
            "business_description": settings.get("business_description"),
            "greeting": settings.get("greeting"),
            "tone": settings.get("tone"),
            "default_language": default_language,
            "supported_languages": supported,
            "response_style": settings.get("response_style") or "concise",
            "service_areas": service_areas,
            "business_hours_summary": hours_summary,
            "business_hours": settings.get("business_hours")
            or default_business_hours(),
            "booking_rules": settings.get("booking_rules"),
            "pricing_disclosure_policy": settings.get("pricing_disclosure_policy"),
            "handoff_rules": settings.get("handoff_rules_text"),
            "restricted_topics": as_str_list(settings.get("restricted_topics")),
            "custom_instructions": settings.get("custom_instructions"),
            "enabled_tools": settings.get("enabled_tools") or default_enabled_tools(),
            "profile_version": int(settings.get("profile_version") or 1),
            "updated_at": settings.get("updated_at"),
            "voice": settings.get("voice"),
        }

"""Agent settings repository."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.crm.errors import as_str_list
from callbot_platform.db.models import TenantAgentSettings
from callbot_platform.telephony.audit import write_audit


class AgentSettingsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, tenant_id: UUID) -> dict[str, Any] | None:
        row = self._session.scalar(
            select(TenantAgentSettings).where(
                TenantAgentSettings.tenant_id == tenant_id
            )
        )
        if row is None:
            return None
        return self._serialize(row)

    def get_profile(
        self, tenant_id: UUID, *, business_name: str
    ) -> dict[str, Any] | None:
        """Return the voice-agent Agent Profile, or None when unset."""
        settings = self.get(tenant_id)
        if settings is None:
            return None
        return self._to_agent_profile(settings, business_name=business_name)

    def get_profile_meta(self, tenant_id: UUID) -> dict[str, Any] | None:
        row = self._session.scalar(
            select(TenantAgentSettings).where(
                TenantAgentSettings.tenant_id == tenant_id
            )
        )
        if row is None:
            return None
        return {
            "tenant_id": str(row.tenant_id),
            "profile_version": int(row.profile_version or 1),
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    def upsert(
        self,
        tenant_id: UUID,
        *,
        business_prompt_facts: dict[str, Any] | None = None,
        voice: str | None = None,
        language: str | None = None,
        greeting: str | None = None,
        assistant_name: str | None = None,
        business_description: str | None = None,
        tone: str | None = None,
        supported_languages: list[str] | None = None,
        response_style: str | None = None,
        service_areas: list[str] | None = None,
        business_hours_summary: str | None = None,
        booking_rules: str | None = None,
        pricing_disclosure_policy: str | None = None,
        handoff_rules_text: str | None = None,
        restricted_topics: list[str] | None = None,
        custom_instructions: str | None = None,
        actor: str = "tenant_user",
    ) -> dict[str, Any]:
        row = self._session.scalar(
            select(TenantAgentSettings).where(
                TenantAgentSettings.tenant_id == tenant_id
            )
        )
        changed_fields: list[str] = []
        before_version = int(row.profile_version or 1) if row is not None else 0

        def _set(field: str, new_value: Any) -> None:
            nonlocal changed_fields
            current = getattr(row, field)
            if current != new_value:
                setattr(row, field, new_value)
                changed_fields.append(field)

        if row is None:
            langs = as_str_list(supported_languages)
            if not langs and language:
                langs = [language]
            row = TenantAgentSettings(
                tenant_id=tenant_id,
                business_prompt_facts=business_prompt_facts or {},
                voice=voice or "marin",
                language=language or "en",
                greeting=greeting,
                assistant_name=assistant_name,
                business_description=business_description,
                tone=tone,
                supported_languages=langs,
                response_style=response_style or "concise",
                service_areas=as_str_list(service_areas),
                business_hours_summary=business_hours_summary,
                booking_rules=booking_rules,
                pricing_disclosure_policy=pricing_disclosure_policy,
                handoff_rules_text=handoff_rules_text,
                restricted_topics=as_str_list(restricted_topics),
                custom_instructions=custom_instructions,
                profile_version=1,
            )
            self._session.add(row)
            changed_fields = ["created"]
        else:
            if business_prompt_facts is not None:
                _set("business_prompt_facts", business_prompt_facts)
            if voice is not None:
                _set("voice", voice)
            if language is not None:
                _set("language", language)
            if greeting is not None:
                _set("greeting", greeting)
            if assistant_name is not None:
                _set("assistant_name", assistant_name)
            if business_description is not None:
                _set("business_description", business_description)
            if tone is not None:
                _set("tone", tone)
            if supported_languages is not None:
                _set("supported_languages", as_str_list(supported_languages))
            if response_style is not None:
                _set("response_style", response_style)
            if service_areas is not None:
                _set("service_areas", as_str_list(service_areas))
            if business_hours_summary is not None:
                _set("business_hours_summary", business_hours_summary)
            if booking_rules is not None:
                _set("booking_rules", booking_rules)
            if pricing_disclosure_policy is not None:
                _set("pricing_disclosure_policy", pricing_disclosure_policy)
            if handoff_rules_text is not None:
                _set("handoff_rules_text", handoff_rules_text)
            if restricted_topics is not None:
                _set("restricted_topics", as_str_list(restricted_topics))
            if custom_instructions is not None:
                _set("custom_instructions", custom_instructions)
            if changed_fields:
                row.profile_version = before_version + 1
                row.updated_at = datetime.now(UTC)
        self._session.flush()
        now = datetime.now(UTC)
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="agent_settings_upserted",
            resource_ids={
                "tenant_id": str(tenant_id),
                "profile_version": str(row.profile_version),
            },
            payload_summary={
                "changed_fields": changed_fields,
                "previous_profile_version": before_version,
                "profile_version": int(row.profile_version or 1),
                "timestamp": now.isoformat(),
            },
        )
        return self._serialize(row)

    def _serialize(self, row: TenantAgentSettings) -> dict[str, Any]:
        return {
            "tenant_id": str(row.tenant_id),
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
            "booking_rules": row.booking_rules,
            "pricing_disclosure_policy": row.pricing_disclosure_policy,
            "handoff_rules_text": row.handoff_rules_text,
            "restricted_topics": as_str_list(row.restricted_topics),
            "custom_instructions": row.custom_instructions,
            "profile_version": int(row.profile_version or 1),
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    def _to_agent_profile(
        self, settings: dict[str, Any], *, business_name: str
    ) -> dict[str, Any]:
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
            "tenant_id": settings["tenant_id"],
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
            "booking_rules": settings.get("booking_rules"),
            "pricing_disclosure_policy": settings.get("pricing_disclosure_policy"),
            "handoff_rules": settings.get("handoff_rules_text"),
            "restricted_topics": as_str_list(settings.get("restricted_topics")),
            "custom_instructions": settings.get("custom_instructions"),
            "profile_version": int(settings.get("profile_version") or 1),
            "updated_at": settings.get("updated_at"),
            "voice": settings.get("voice"),
        }

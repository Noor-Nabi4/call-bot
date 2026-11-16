"""Agent settings repository — back-compat shim over AgentProfileRepository."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from callbot_platform.crm.repos.agent_profile_repo import AgentProfileRepository
from callbot_platform.db.models import Tenant


class AgentSettingsRepository:
    """Legacy 1:1 settings API mapped to the tenant default AgentProfile."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._profiles = AgentProfileRepository(session)

    def get(self, tenant_id: UUID) -> dict[str, Any] | None:
        profile = self._profiles.get_default(tenant_id)
        if profile is None:
            return None
        return self._as_settings(profile)

    def get_profile(
        self, tenant_id: UUID, *, business_name: str
    ) -> dict[str, Any] | None:
        return self._profiles.get_voice_profile(tenant_id, business_name=business_name)

    def get_profile_meta(self, tenant_id: UUID) -> dict[str, Any] | None:
        return self._profiles.get_voice_profile_meta(tenant_id)

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
        fields: dict[str, Any] = {}
        if business_prompt_facts is not None:
            fields["business_prompt_facts"] = business_prompt_facts
        if voice is not None:
            fields["voice"] = voice
        if language is not None:
            fields["language"] = language
        if greeting is not None:
            fields["greeting"] = greeting
        if assistant_name is not None:
            fields["assistant_name"] = assistant_name
        if business_description is not None:
            fields["business_description"] = business_description
        if tone is not None:
            fields["tone"] = tone
        if supported_languages is not None:
            fields["supported_languages"] = supported_languages
        if response_style is not None:
            fields["response_style"] = response_style
        if service_areas is not None:
            fields["service_areas"] = service_areas
        if business_hours_summary is not None:
            fields["business_hours_summary"] = business_hours_summary
        if booking_rules is not None:
            fields["booking_rules"] = booking_rules
        if pricing_disclosure_policy is not None:
            fields["pricing_disclosure_policy"] = pricing_disclosure_policy
        if handoff_rules_text is not None:
            fields["handoff_rules_text"] = handoff_rules_text
        if restricted_topics is not None:
            fields["restricted_topics"] = restricted_topics
        if custom_instructions is not None:
            fields["custom_instructions"] = custom_instructions

        default = self._profiles.get_default(tenant_id)
        if default is None:
            tenant = self._session.get(Tenant, tenant_id)
            name = "Main Receptionist"
            if tenant is not None and tenant.name:
                name = f"{tenant.name} Receptionist"
            created = self._profiles.create(
                tenant_id,
                name=name,
                agent_type="receptionist",
                is_default=True,
                actor=actor,
                **fields,
            )
            return self._as_settings(created)

        updated = self._profiles.update(
            tenant_id,
            UUID(default["id"]),
            actor=actor,
            **fields,
        )
        return self._as_settings(updated)

    def _as_settings(self, profile: dict[str, Any]) -> dict[str, Any]:
        return {
            "tenant_id": profile["tenant_id"],
            "agent_profile_id": profile["id"],
            "business_prompt_facts": profile.get("business_prompt_facts") or {},
            "voice": profile.get("voice"),
            "language": profile.get("language"),
            "greeting": profile.get("greeting"),
            "assistant_name": profile.get("assistant_name"),
            "business_description": profile.get("business_description"),
            "tone": profile.get("tone"),
            "supported_languages": profile.get("supported_languages") or [],
            "response_style": profile.get("response_style"),
            "service_areas": profile.get("service_areas") or [],
            "business_hours_summary": profile.get("business_hours_summary"),
            "booking_rules": profile.get("booking_rules"),
            "pricing_disclosure_policy": profile.get("pricing_disclosure_policy"),
            "handoff_rules_text": profile.get("handoff_rules_text"),
            "restricted_topics": profile.get("restricted_topics") or [],
            "custom_instructions": profile.get("custom_instructions"),
            "profile_version": int(profile.get("profile_version") or 1),
            "updated_at": profile.get("updated_at"),
        }

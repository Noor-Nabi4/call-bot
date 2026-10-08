"""Agent configuration service — profile + capabilities on existing agent_profiles."""

from __future__ import annotations

import logging
import re
import secrets
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from callbot_platform.agent_config.capabilities import (
    CAPABILITY_BY_KEY,
    CAPABILITY_KEYS,
    capabilities_from_enabled_tools,
    list_capabilities,
    normalize_capabilities,
    sync_enabled_tools_from_capabilities,
)
from callbot_platform.agent_config.errors import AgentConfigError
from callbot_platform.agent_config.languages import (
    assert_language,
    list_languages,
    normalize_language,
)
from callbot_platform.agent_config.rules import (
    AFTER_HOURS_BEHAVIORS,
    ESCALATION_RULE_KEYS,
    TRANSFER_RULE_KEYS,
    default_escalation_rules,
    default_transfer_rules,
    list_rule_catalogs,
    normalize_after_hours,
    normalize_bool_rules,
)
from callbot_platform.agent_config.tones import assert_tone, list_tones, normalize_tone
from callbot_platform.agent_config.voices import (
    assert_voice,
    list_voices,
    normalize_voice,
    voice_supports_language,
)
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.repos.agent_profile_repo import AgentProfileRepository
from callbot_platform.crm_config import CrmSetupService
from callbot_platform.telephony.audit import write_audit

logger = logging.getLogger(__name__)

FACTS_CAPABILITIES = "capabilities"
FACTS_TRANSFER = "transfer_rules"
FACTS_ESCALATION = "escalation_rules"
FACTS_AFTER_HOURS = "after_hours_behavior"
_NAME_RE = re.compile(r"^[\w\s\-'.&]{1,64}$", re.UNICODE)
_MAX_GREETING = 500
_MAX_CUSTOM = 2000


class AgentConfigService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._profiles = AgentProfileRepository(session)

    def catalog(self) -> dict[str, Any]:
        return {
            "voices": list_voices(),
            "languages": list_languages(),
            "tones": list_tones(),
            "capabilities": list_capabilities(),
            **list_rule_catalogs(),
        }

    def get_config(self, tenant_id: UUID, profile_id: UUID) -> dict[str, Any]:
        profile = self._profiles.get(tenant_id, profile_id)
        if profile is None:
            raise AgentConfigError("not_found", "Agent profile not found")
        return self._enrich(tenant_id, profile)

    def update_config(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        *,
        actor: str,
        operation_id: str | None = None,
        **fields: Any,
    ) -> dict[str, Any]:
        op_id = (operation_id or secrets.token_urlsafe(12)).strip()
        profile = self._profiles.get(tenant_id, profile_id)
        if profile is None:
            raise AgentConfigError("not_found", "Agent profile not found")

        patch = self._validate_patch(tenant_id, fields)
        facts = dict(profile.get("business_prompt_facts") or {})
        changed: list[str] = []

        if "capabilities" in patch:
            facts[FACTS_CAPABILITIES] = patch.pop("capabilities")
            patch["enabled_tools"] = sync_enabled_tools_from_capabilities(
                facts[FACTS_CAPABILITIES]
            )
            changed.append("capabilities")
        if "transfer_rules" in patch:
            facts[FACTS_TRANSFER] = patch.pop("transfer_rules")
            changed.append("transfer_rules")
        if "escalation_rules" in patch:
            facts[FACTS_ESCALATION] = patch.pop("escalation_rules")
            changed.append("escalation_rules")
        if "after_hours_behavior" in patch:
            facts[FACTS_AFTER_HOURS] = patch.pop("after_hours_behavior")
            changed.append("after_hours_behavior")

        if any(
            k in fields
            for k in (
                "capabilities",
                "transfer_rules",
                "escalation_rules",
                "after_hours_behavior",
            )
        ):
            patch["business_prompt_facts"] = facts

        try:
            updated = self._profiles.update(tenant_id, profile_id, actor=actor, **patch)
        except CrmError as exc:
            raise AgentConfigError(exc.code, str(exc)) from exc

        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="AGENT_CONFIG_UPDATED",
            resource_ids={
                "agent_profile_id": str(profile_id),
                "operation_id": op_id,
            },
            payload_summary={
                "changed_fields": sorted(set(changed + list(patch.keys()))),
                "status": updated.get("status"),
            },
        )
        for key in ("capabilities",):
            if key in changed:
                write_audit(
                    self._session,
                    tenant_id=tenant_id,
                    actor=actor,
                    action="AGENT_CAPABILITY_ENABLED"
                    if any((facts.get(FACTS_CAPABILITIES) or {}).values())
                    else "AGENT_CAPABILITY_DISABLED",
                    resource_ids={"agent_profile_id": str(profile_id)},
                    payload_summary={"operation_id": op_id},
                )
        if "transfer_rules" in changed:
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="AGENT_TRANSFER_RULE_UPDATED",
                resource_ids={"agent_profile_id": str(profile_id)},
                payload_summary={"operation_id": op_id},
            )
        if "escalation_rules" in changed:
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="AGENT_ESCALATION_RULE_UPDATED",
                resource_ids={"agent_profile_id": str(profile_id)},
                payload_summary={"operation_id": op_id},
            )
        return self._enrich(tenant_id, updated)

    def activate(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        *,
        actor: str,
        operation_id: str | None = None,
    ) -> dict[str, Any]:
        op_id = (operation_id or secrets.token_urlsafe(12)).strip()
        enriched = self.get_config(tenant_id, profile_id)
        self._assert_activatable(enriched)
        try:
            updated = self._profiles.update(
                tenant_id, profile_id, actor=actor, status="active"
            )
        except CrmError as exc:
            raise AgentConfigError(exc.code, str(exc)) from exc
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="AGENT_CONFIG_ACTIVATED",
            resource_ids={
                "agent_profile_id": str(profile_id),
                "operation_id": op_id,
                "profile_version": str(updated.get("profile_version")),
            },
            payload_summary={"status": "active"},
        )
        logger.info(
            "agent_config_activated tenant_id=%s profile_id=%s version=%s",
            tenant_id,
            profile_id,
            updated.get("profile_version"),
        )
        return self._enrich(tenant_id, updated)

    def save_draft(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        *,
        actor: str,
        **fields: Any,
    ) -> dict[str, Any]:
        fields = dict(fields)
        fields["status"] = "draft"
        return self.update_config(tenant_id, profile_id, actor=actor, **fields)

    def _enabled_modules(self, tenant_id: UUID) -> set[str]:
        cfg = CrmSetupService(self._session).get(tenant_id)
        if not cfg:
            return set()
        return {
            str(m["key"]).upper()
            for m in (cfg.get("modules") or [])
            if m.get("enabled")
        }

    def _enrich(self, tenant_id: UUID, profile: dict[str, Any]) -> dict[str, Any]:
        facts = dict(profile.get("business_prompt_facts") or {})
        caps_raw = facts.get(FACTS_CAPABILITIES)
        if isinstance(caps_raw, dict) and caps_raw:
            capabilities = normalize_capabilities(caps_raw)
        else:
            capabilities = capabilities_from_enabled_tools(profile.get("enabled_tools"))
        transfer = normalize_bool_rules(
            facts.get(FACTS_TRANSFER)
            if isinstance(facts.get(FACTS_TRANSFER), dict)
            else None,
            allowed=TRANSFER_RULE_KEYS,
            defaults=default_transfer_rules(),
        )
        escalation = normalize_bool_rules(
            facts.get(FACTS_ESCALATION)
            if isinstance(facts.get(FACTS_ESCALATION), dict)
            else None,
            allowed=ESCALATION_RULE_KEYS,
            defaults=default_escalation_rules(),
        )
        after_hours = normalize_after_hours(
            facts.get(FACTS_AFTER_HOURS)
            if isinstance(facts.get(FACTS_AFTER_HOURS), str)
            else None
        )
        modules = self._enabled_modules(tenant_id)
        capability_states = []
        for key, enabled in capabilities.items():
            cap = CAPABILITY_BY_KEY[key]
            missing = [m for m in cap.required_modules if m not in modules]
            available = len(missing) == 0
            capability_states.append(
                {
                    "key": key,
                    "display_name": cap.display_name,
                    "description": cap.description,
                    "risk_level": cap.risk_level,
                    "category": cap.category,
                    "enabled": bool(enabled) and available,
                    "requested": bool(enabled),
                    "available": available,
                    "missing_modules": missing,
                    "unavailable_reason": (
                        f"Requires module(s): {', '.join(missing)}" if missing else None
                    ),
                }
            )
        return {
            **profile,
            "capabilities": capabilities,
            "capability_states": capability_states,
            "transfer_rules": transfer,
            "escalation_rules": escalation,
            "after_hours_behavior": after_hours,
            "enabled_modules": sorted(modules),
        }

    def _validate_patch(
        self, tenant_id: UUID, fields: dict[str, Any]
    ) -> dict[str, Any]:
        patch: dict[str, Any] = {}
        if "assistant_name" in fields and fields["assistant_name"] is not None:
            name = str(fields["assistant_name"]).strip()
            if not name or not _NAME_RE.match(name) or "<" in name or ">" in name:
                raise AgentConfigError(
                    "invalid_assistant_name",
                    "Agent name is required and must be short safe text",
                )
            patch["assistant_name"] = name
        if "name" in fields and fields["name"] is not None:
            pname = str(fields["name"]).strip()
            if not pname or len(pname) > 128 or "<" in pname:
                raise AgentConfigError("invalid_name", "Profile name is invalid")
            patch["name"] = pname
        if "voice" in fields and fields["voice"] is not None:
            try:
                patch["voice"] = assert_voice(str(fields["voice"]))
            except ValueError as exc:
                raise AgentConfigError("invalid_voice", str(exc)) from exc
        if "language" in fields and fields["language"] is not None:
            try:
                patch["language"] = assert_language(str(fields["language"]))
            except ValueError as exc:
                raise AgentConfigError("invalid_language", str(exc)) from exc
        if "tone" in fields and fields["tone"] is not None:
            try:
                patch["tone"] = assert_tone(str(fields["tone"]))
            except ValueError as exc:
                raise AgentConfigError("invalid_tone", str(exc)) from exc
        if "greeting" in fields and fields["greeting"] is not None:
            greeting = str(fields["greeting"]).strip()
            if not greeting:
                raise AgentConfigError("invalid_greeting", "Greeting cannot be empty")
            if len(greeting) > _MAX_GREETING or "<script" in greeting.lower():
                raise AgentConfigError("invalid_greeting", "Greeting is invalid")
            patch["greeting"] = greeting
        if "custom_instructions" in fields:
            raw = fields["custom_instructions"]
            if raw is None:
                patch["custom_instructions"] = None
            else:
                text = str(raw).strip()
                if len(text) > _MAX_CUSTOM or "<script" in text.lower():
                    raise AgentConfigError(
                        "invalid_custom_instructions",
                        "Custom instructions are too long or unsafe",
                    )
                patch["custom_instructions"] = text or None
        if (
            "business_hours_summary" in fields
            and fields["business_hours_summary"] is not None
        ):
            patch["business_hours_summary"] = str(fields["business_hours_summary"])[
                :500
            ]
        if "business_hours" in fields and fields["business_hours"] is not None:
            if not isinstance(fields["business_hours"], dict):
                raise AgentConfigError(
                    "invalid_business_hours", "business_hours must be an object"
                )
            patch["business_hours"] = fields["business_hours"]
        if "handoff_rules_text" in fields and fields["handoff_rules_text"] is not None:
            patch["handoff_rules_text"] = str(fields["handoff_rules_text"])[:2000]
        if (
            "supported_languages" in fields
            and fields["supported_languages"] is not None
        ):
            langs = []
            for item in fields["supported_languages"]:
                langs.append(normalize_language(str(item)))
            patch["supported_languages"] = langs or ["en"]
        if "status" in fields and fields["status"] is not None:
            status = str(fields["status"]).strip().lower()
            if status not in {"draft", "active", "archived"}:
                raise AgentConfigError(
                    "invalid_status", f"Unsupported status: {status}"
                )
            patch["status"] = status
        if "response_style" in fields and fields["response_style"] is not None:
            patch["response_style"] = str(fields["response_style"])[:64]
        if (
            "business_description" in fields
            and fields["business_description"] is not None
        ):
            patch["business_description"] = str(fields["business_description"])[:4000]

        voice = patch.get("voice")
        language = patch.get("language")
        if voice and language and not voice_supports_language(voice, language):
            raise AgentConfigError(
                "voice_language_incompatible",
                "Selected voice is not compatible with the language",
            )

        if "capabilities" in fields and fields["capabilities"] is not None:
            if not isinstance(fields["capabilities"], dict):
                raise AgentConfigError(
                    "invalid_capabilities", "capabilities must be an object"
                )
            caps = normalize_capabilities(fields["capabilities"])
            modules = self._enabled_modules(tenant_id)
            for key, enabled in caps.items():
                if not enabled:
                    continue
                if key not in CAPABILITY_KEYS:
                    raise AgentConfigError(
                        "CAPABILITY_UNAVAILABLE", f"Unknown capability: {key}"
                    )
                missing = [
                    m
                    for m in CAPABILITY_BY_KEY[key].required_modules
                    if m not in modules
                ]
                if missing:
                    raise AgentConfigError(
                        "CAPABILITY_UNAVAILABLE",
                        f"{key} requires module(s): {', '.join(missing)}",
                    )
            patch["capabilities"] = caps

        if "transfer_rules" in fields and fields["transfer_rules"] is not None:
            patch["transfer_rules"] = normalize_bool_rules(
                fields["transfer_rules"],
                allowed=TRANSFER_RULE_KEYS,
                defaults=default_transfer_rules(),
            )
        if "escalation_rules" in fields and fields["escalation_rules"] is not None:
            patch["escalation_rules"] = normalize_bool_rules(
                fields["escalation_rules"],
                allowed=ESCALATION_RULE_KEYS,
                defaults=default_escalation_rules(),
            )
        if (
            "after_hours_behavior" in fields
            and fields["after_hours_behavior"] is not None
        ):
            ah = str(fields["after_hours_behavior"]).strip().lower()
            if ah not in AFTER_HOURS_BEHAVIORS:
                raise AgentConfigError(
                    "invalid_after_hours", f"Unsupported after-hours behavior: {ah}"
                )
            patch["after_hours_behavior"] = ah

        # Pass-through safe identity fields already validated above
        for key in ("enabled_tools",):
            if key in fields and fields[key] is not None:
                patch[key] = fields[key]
        return patch

    def _assert_activatable(self, enriched: dict[str, Any]) -> None:
        if not (enriched.get("assistant_name") or enriched.get("name")):
            raise AgentConfigError(
                "invalid_configuration", "Agent name is required before activation"
            )
        try:
            assert_voice(enriched.get("voice"))
            assert_language(enriched.get("language"))
        except ValueError as exc:
            raise AgentConfigError("invalid_configuration", str(exc)) from exc
        greeting = (enriched.get("greeting") or "").strip()
        if not greeting:
            raise AgentConfigError(
                "invalid_configuration", "Greeting is required before activation"
            )
        # Capabilities requested but unavailable → block activation
        for state in enriched.get("capability_states") or []:
            if state.get("requested") and not state.get("available"):
                raise AgentConfigError(
                    "CAPABILITY_UNAVAILABLE",
                    state.get("unavailable_reason")
                    or f"Capability {state.get('key')} unavailable",
                )


def normalize_voice_language_tone(
    *, voice: str | None, language: str | None, tone: str | None
) -> tuple[str, str, str]:
    return normalize_voice(voice), normalize_language(language), normalize_tone(tone)

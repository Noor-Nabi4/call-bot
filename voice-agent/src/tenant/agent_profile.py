"""Typed tenant Agent Profile (approved configuration only)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class AgentProfileError(ValueError):
    """Raised when a profile payload is missing or invalid."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        item = value.strip()
        return [item] if item else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    raise AgentProfileError(
        "agent_profile_invalid",
        "Expected a list of strings",
    )


@dataclass(frozen=True, slots=True)
class AgentProfile:
    """Approved agent configuration loaded once per call after tenant resolve.

    Never includes credentials, internal IDs, provider config, or private ops data.
    """

    tenant_id: str
    business_name: str
    agent_profile_id: str | None = None
    name: str | None = None
    agent_type: str = "receptionist"
    assistant_name: str | None = None
    business_description: str | None = None
    greeting: str | None = None
    tone: str | None = None
    default_language: str = "en"
    supported_languages: tuple[str, ...] = ("en",)
    response_style: str = "concise"
    service_areas: tuple[str, ...] = ()
    business_hours_summary: str | None = None
    booking_rules: str | None = None
    pricing_disclosure_policy: str | None = None
    handoff_rules: str | None = None
    restricted_topics: tuple[str, ...] = ()
    custom_instructions: str | None = None
    enabled_tools: tuple[str, ...] = (
        "crm",
        "scheduling",
        "knowledge",
        "handoff",
        "sms",
    )
    call_flow: dict[str, Any] | None = None
    profile_version: int = 1
    updated_at: str | None = None
    voice: str | None = None

    @classmethod
    def from_api_payload(cls, payload: dict[str, Any]) -> AgentProfile:
        tenant_id = _optional_str(payload.get("tenant_id"))
        business_name = _optional_str(payload.get("business_name"))
        if not tenant_id:
            raise AgentProfileError("agent_profile_invalid", "tenant_id is required")
        if not business_name:
            raise AgentProfileError(
                "agent_profile_invalid", "business_name is required"
            )

        default_language = (
            _optional_str(payload.get("default_language"))
            or _optional_str(payload.get("language"))
            or "en"
        )
        supported = tuple(_str_list(payload.get("supported_languages")))
        if not supported:
            supported = (default_language,)

        version_raw = payload.get("profile_version", 1)
        try:
            profile_version = int(version_raw)
        except (TypeError, ValueError) as exc:
            raise AgentProfileError(
                "agent_profile_invalid", "profile_version must be an integer"
            ) from exc
        if profile_version < 1:
            raise AgentProfileError(
                "agent_profile_invalid", "profile_version must be >= 1"
            )

        tools_raw = payload.get("enabled_tools")
        enabled: list[str] = []
        if isinstance(tools_raw, dict):
            enabled = [k for k, v in tools_raw.items() if v]
        elif isinstance(tools_raw, list):
            enabled = _str_list(tools_raw)
        else:
            enabled = ["crm", "scheduling", "knowledge", "handoff", "sms"]

        call_flow_raw = payload.get("call_flow")
        call_flow: dict[str, Any] | None = None
        if isinstance(call_flow_raw, dict):
            call_flow = call_flow_raw

        profile_id = _optional_str(payload.get("agent_profile_id")) or _optional_str(
            payload.get("id")
        )

        return cls(
            tenant_id=tenant_id,
            business_name=business_name,
            agent_profile_id=profile_id,
            name=_optional_str(payload.get("name")),
            agent_type=_optional_str(payload.get("agent_type")) or "receptionist",
            assistant_name=_optional_str(payload.get("assistant_name")),
            business_description=_optional_str(payload.get("business_description")),
            greeting=_optional_str(payload.get("greeting")),
            tone=_optional_str(payload.get("tone")),
            default_language=default_language,
            supported_languages=supported,
            response_style=_optional_str(payload.get("response_style")) or "concise",
            service_areas=tuple(_str_list(payload.get("service_areas"))),
            business_hours_summary=_optional_str(payload.get("business_hours_summary")),
            booking_rules=_optional_str(payload.get("booking_rules")),
            pricing_disclosure_policy=_optional_str(
                payload.get("pricing_disclosure_policy")
            ),
            handoff_rules=_optional_str(payload.get("handoff_rules")),
            restricted_topics=tuple(_str_list(payload.get("restricted_topics"))),
            custom_instructions=_optional_str(payload.get("custom_instructions")),
            enabled_tools=tuple(enabled),
            call_flow=call_flow,
            profile_version=profile_version,
            updated_at=_optional_str(payload.get("updated_at")),
            voice=_optional_str(payload.get("voice")),
        )

    def to_api_payload(self) -> dict[str, Any]:
        """Serialize for cache round-trip (inverse of from_api_payload)."""
        tools_dict = dict.fromkeys(self.enabled_tools, True)
        return {
            "tenant_id": self.tenant_id,
            "business_name": self.business_name,
            "agent_profile_id": self.agent_profile_id,
            "id": self.agent_profile_id,
            "name": self.name,
            "agent_type": self.agent_type,
            "assistant_name": self.assistant_name,
            "business_description": self.business_description,
            "greeting": self.greeting,
            "tone": self.tone,
            "default_language": self.default_language,
            "supported_languages": list(self.supported_languages),
            "response_style": self.response_style,
            "service_areas": list(self.service_areas),
            "business_hours_summary": self.business_hours_summary,
            "booking_rules": self.booking_rules,
            "pricing_disclosure_policy": self.pricing_disclosure_policy,
            "handoff_rules": self.handoff_rules,
            "restricted_topics": list(self.restricted_topics),
            "custom_instructions": self.custom_instructions,
            "enabled_tools": tools_dict,
            "call_flow": self.call_flow,
            "profile_version": self.profile_version,
            "updated_at": self.updated_at,
            "voice": self.voice,
        }

    def tool_enabled(self, tool_group: str) -> bool:
        return tool_group in self.enabled_tools

    def supports_language(self, language_code: str) -> bool:
        code = language_code.strip().lower()
        if not code:
            return False
        supported = {lang.lower() for lang in self.supported_languages}
        if code in supported:
            return True
        # Accept base language (e.g. en from en-US).
        base = code.split("-", 1)[0]
        return base in supported or any(
            lang.lower().startswith(base) for lang in self.supported_languages
        )

    def max_spoken_sentences(self, *, default: int = 2) -> int:
        style = (self.response_style or "concise").strip().lower()
        if style in {"brief", "concise", "short"}:
            return min(default, 2)
        if style in {"detailed", "verbose"}:
            return max(default, 4)
        return default


@dataclass
class CallFacts:
    """Structured call facts kept separate from free-form chat history."""

    caller_name: str | None = None
    caller_phone: str | None = None
    requested_service: str | None = None
    address: str | None = None
    preferred_date: str | None = None
    preferred_time: str | None = None
    confirmed_appointment: str | None = None
    current_task: str | None = None
    unresolved_question: str | None = None
    completed_actions: list[str] = field(default_factory=list)

    def as_prompt_lines(self) -> list[str]:
        lines: list[str] = []
        mapping = (
            ("Caller name", self.caller_name),
            ("Caller phone", self.caller_phone),
            ("Requested service", self.requested_service),
            ("Address", self.address),
            ("Preferred date", self.preferred_date),
            ("Preferred time", self.preferred_time),
            ("Confirmed appointment", self.confirmed_appointment),
            ("Current task", self.current_task),
            ("Unresolved question", self.unresolved_question),
        )
        for label, value in mapping:
            if value:
                lines.append(f"{label}: {value}")
        if self.completed_actions:
            lines.append("Completed actions: " + "; ".join(self.completed_actions[-8:]))
        return lines

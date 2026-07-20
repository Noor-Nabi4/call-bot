"""Call flow schema: ordered conversation steps for an agent profile.

MVP stores a linear step list (not a full graph). Steps are compiled into
system instructions for the single LiveKit voice agent. Multi-agent handoffs
per LiveKit workflows docs can layer on later without changing this storage.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

VALID_STEP_TYPES = frozenset(
    {
        "greeting",
        "qualify",
        "book",
        "faq",
        "handoff",
        "custom",
    }
)

_MAX_STEPS = 20
_MAX_LABEL = 128
_MAX_INSTRUCTION = 2000


class CallFlowError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def default_call_flow() -> dict[str, Any]:
    """Starter linear flow for new agent profiles."""
    return {
        "version": 1,
        "steps": [
            {
                "id": "step-greeting",
                "type": "greeting",
                "label": "Greet the caller",
                "instruction": (
                    "Open with a brief, natural greeting. Confirm you can help."
                ),
                "enabled": True,
            },
            {
                "id": "step-qualify",
                "type": "qualify",
                "label": "Understand the need",
                "instruction": (
                    "Ask what they need. Capture name and callback number when useful."
                ),
                "enabled": True,
            },
            {
                "id": "step-book",
                "type": "book",
                "label": "Book or update appointment",
                "instruction": (
                    "When they want to schedule, use scheduling tools. Confirm details aloud."
                ),
                "enabled": True,
            },
            {
                "id": "step-faq",
                "type": "faq",
                "label": "Answer common questions",
                "instruction": (
                    "For hours, areas, and policy questions, use knowledge search first."
                ),
                "enabled": True,
            },
            {
                "id": "step-handoff",
                "type": "handoff",
                "label": "Escalate to a human",
                "instruction": (
                    "For emergencies, billing disputes, or when the caller asks for a person, "
                    "confirm then use handoff."
                ),
                "enabled": True,
            },
        ],
    }


def validate_call_flow(raw: Any) -> dict[str, Any]:
    """Normalize and validate a call flow document."""
    if raw is None:
        return default_call_flow()
    if not isinstance(raw, dict):
        raise CallFlowError("invalid_call_flow", "call_flow must be an object")
    version = int(raw.get("version") or 1)
    if version < 1:
        raise CallFlowError("invalid_call_flow", "version must be >= 1")
    steps_raw = raw.get("steps")
    if not isinstance(steps_raw, list):
        raise CallFlowError("invalid_call_flow", "steps must be a list")
    if len(steps_raw) > _MAX_STEPS:
        raise CallFlowError(
            "invalid_call_flow", f"At most {_MAX_STEPS} steps are allowed"
        )
    steps: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(steps_raw):
        if not isinstance(item, dict):
            raise CallFlowError(
                "invalid_call_flow", f"Step {index + 1} must be an object"
            )
        step_type = str(item.get("type") or "custom").strip().lower()
        if step_type not in VALID_STEP_TYPES:
            raise CallFlowError(
                "invalid_call_flow",
                f"Unsupported step type '{step_type}'. "
                f"Allowed: {sorted(VALID_STEP_TYPES)}",
            )
        label = str(item.get("label") or step_type).strip()[:_MAX_LABEL]
        if not label:
            raise CallFlowError("invalid_call_flow", "Step label is required")
        step_id = str(item.get("id") or f"step-{uuid4().hex[:8]}").strip()[:64]
        if step_id in seen_ids:
            raise CallFlowError("invalid_call_flow", f"Duplicate step id: {step_id}")
        seen_ids.add(step_id)
        instruction = item.get("instruction")
        instruction_text = None
        if instruction is not None:
            instruction_text = str(instruction).strip()[:_MAX_INSTRUCTION] or None
        enabled = bool(item.get("enabled", True))
        steps.append(
            {
                "id": step_id,
                "type": step_type,
                "label": label,
                "instruction": instruction_text,
                "enabled": enabled,
            }
        )
    return {"version": version, "steps": steps}


def render_call_flow_instructions(flow: dict[str, Any] | None) -> str:
    """Compile enabled steps into system-instruction text for the voice agent."""
    if not flow:
        return ""
    steps = flow.get("steps") if isinstance(flow, dict) else None
    if not isinstance(steps, list) or not steps:
        return ""
    enabled = [s for s in steps if isinstance(s, dict) and s.get("enabled", True)]
    if not enabled:
        return ""
    lines = [
        "[call-flow-v1 — ORDERED CALL FLOW]",
        "Follow these steps in order when practical. Skip a step only if the "
        "caller clearly does not need it. Do not invent steps that are not listed.",
    ]
    for index, step in enumerate(enabled, start=1):
        label = str(step.get("label") or step.get("type") or f"Step {index}")
        step_type = str(step.get("type") or "custom")
        instruction = str(step.get("instruction") or "").strip()
        lines.append(f"{index}. ({step_type}) {label}")
        if instruction:
            lines.append(f"   Guidance: {instruction}")
    return "\n".join(lines)

"""Compile ordered call-flow steps into voice-agent instructions."""

from __future__ import annotations

from typing import Any


def render_call_flow_section(flow: dict[str, Any] | None) -> str:
    """Return an instructions block for enabled call-flow steps."""
    if not flow or not isinstance(flow, dict):
        return ""
    steps = flow.get("steps")
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

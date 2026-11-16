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
        "[call-flow-v2 — GUIDED CALL FLOW]",
        "These steps are a soft guide, not a rigid script. Always answer the "
        "caller's current question first. Advance through remaining steps when "
        "they help the caller's goal; skip any step that is unnecessary, already "
        "covered, or would feel repetitive. Do not invent steps that are not "
        "listed. Prefer natural conversation over reading the list in order.",
    ]
    for index, step in enumerate(enabled, start=1):
        label = str(step.get("label") or step.get("type") or f"Step {index}")
        step_type = str(step.get("type") or "custom")
        instruction = str(step.get("instruction") or "").strip()
        lines.append(f"{index}. ({step_type}) {label}")
        if instruction:
            lines.append(f"   Guidance: {instruction}")
    return "\n".join(lines)

"""Phase 14 voice tool registration — no legacy scheduling / customer bypass."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from tools.ai_business_tools import build_ai_business_tools
from tools.crm import build_crm_tools, build_legacy_crm_compat_tools


def _names(tools: list[Any]) -> set[str]:
    out: set[str] = set()
    for tool in tools:
        name = getattr(tool, "name", None) or getattr(tool, "__name__", None)
        if name:
            out.add(str(name))
    return out


def test_phase14_tools_include_booking_and_commerce() -> None:
    client = MagicMock()
    names = _names(build_ai_business_tools(client))
    assert "create_booking" in names
    assert "reschedule_appointment" in names
    assert "cancel_appointment" in names
    assert "create_order" in names
    assert "find_customer" in names
    assert "send_sms" in names
    # No duplicate names
    tools = build_ai_business_tools(client)
    assert len(tools) == len(_names(tools))


def test_legacy_compat_keeps_only_lead_and_call_context() -> None:
    client = MagicMock()
    full = _names(build_crm_tools(client))
    compat = _names(build_legacy_crm_compat_tools(client))
    assert compat == {"get_call_context", "create_lead"}
    assert "create_or_update_customer" in full
    assert "create_or_update_customer" not in compat

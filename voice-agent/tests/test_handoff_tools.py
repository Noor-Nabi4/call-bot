"""Handoff tool gating tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from session.userdata import SessionUserData
from tools.handoff import build_handoff_tools
from tools.platform_handoff import PlatformHandoffClient


class FakeHandoffClient(PlatformHandoffClient):
    def __init__(self, settings: dict[str, Any] | None = None) -> None:
        super().__init__(base_url="http://example", internal_token="tok")
        self._settings = settings or {
            "enabled": False,
            "mode": "cold",
            "escalation_phone_e164": None,
        }

    def get_settings(self, tenant_id: str) -> dict[str, Any]:
        return {"settings": self._settings}


@pytest.mark.asyncio
async def test_handoff_requires_confirmation() -> None:
    from livekit.agents.llm import ToolError

    tool = build_handoff_tools(FakeHandoffClient())[0]
    ctx = MagicMock()
    ctx.session.userdata = SessionUserData(
        tenant_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        call_id="c1",
        room_name="r1",
        business_name="Acme",
    )
    with pytest.raises(ToolError):
        await tool(ctx, reason="caller_request", caller_confirmed=False)


@pytest.mark.asyncio
async def test_handoff_disabled() -> None:
    from livekit.agents.llm import ToolError

    tool = build_handoff_tools(FakeHandoffClient({"enabled": False}))[0]
    ctx = MagicMock()
    ctx.session.userdata = SessionUserData(
        tenant_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        call_id="c1",
        room_name="r1",
        business_name="Acme",
    )
    with pytest.raises(ToolError):
        await tool(ctx, reason="emergency", caller_confirmed=True)

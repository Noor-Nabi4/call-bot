"""CRM tool safety unit tests (no live platform)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from session.userdata import SessionUserData
from tools.crm import build_crm_tools
from tools.platform_crm import PlatformCrmClient, PlatformCrmError


class FakeCrmClient(PlatformCrmClient):
    def __init__(self) -> None:
        super().__init__(base_url="http://example", internal_token="tok")
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((path, payload))
        if path.endswith("/lookup"):
            return {"found": False, "customer": None}
        if path.endswith("/upsert"):
            return {
                "customer": {
                    "id": "cust-1",
                    "name": payload["name"],
                    "phones": [payload["phone"]],
                }
            }
        if path.endswith("/leads"):
            return {
                "lead": {
                    "id": "lead-1",
                    "reference_code": "JB-ABC123",
                    "service_type": payload["service_type"],
                }
            }
        return {}


def _context(userdata: SessionUserData | None) -> MagicMock:
    ctx = MagicMock()
    ctx.session.userdata = userdata
    ctx.disallow_interruptions = MagicMock()
    return ctx


@pytest.mark.asyncio
async def test_tools_require_userdata() -> None:
    tools = {t.name if hasattr(t, "name") else getattr(t, "__name__", ""): t for t in build_crm_tools(FakeCrmClient())}
    # function_tool wraps callables — invoke underlying via tools list
    built = build_crm_tools(FakeCrmClient())
    lookup = built[1]
    ctx = _context(None)
    from livekit.agents.llm import ToolError

    with pytest.raises(ToolError):
        await lookup(ctx, phone="+15551112222")


@pytest.mark.asyncio
async def test_create_customer_requires_confirmation() -> None:
    from livekit.agents.llm import ToolError

    built = build_crm_tools(FakeCrmClient())
    create = built[2]
    userdata = SessionUserData(
        tenant_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        call_id="call-1",
        room_name="room-1",
        business_name="Acme",
    )
    ctx = _context(userdata)
    with pytest.raises(ToolError):
        await create(
            ctx,
            name="Noor",
            phone="+15551112222",
            caller_confirmed=False,
        )


@pytest.mark.asyncio
async def test_create_lead_requires_customer() -> None:
    from livekit.agents.llm import ToolError

    built = build_crm_tools(FakeCrmClient())
    create_lead = built[3]
    userdata = SessionUserData(
        tenant_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        call_id="call-1",
        room_name="room-1",
        business_name="Acme",
        customer_id=None,
    )
    ctx = _context(userdata)
    with pytest.raises(ToolError):
        await create_lead(
            ctx,
            service_type="AC repair",
            caller_confirmed=True,
        )


@pytest.mark.asyncio
async def test_upsert_uses_userdata_tenant() -> None:
    client = FakeCrmClient()
    built = build_crm_tools(client)
    create = built[2]
    userdata = SessionUserData(
        tenant_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        call_id="call-1",
        room_name="room-1",
        business_name="Acme",
    )
    ctx = _context(userdata)
    result = await create(
        ctx,
        name="Noor",
        phone="+15551112222",
        caller_confirmed=True,
        address="1 Main",
    )
    assert result["ok"] is True
    assert userdata.customer_id == "cust-1"
    assert client.calls[-1][1]["tenant_id"] == userdata.tenant_id

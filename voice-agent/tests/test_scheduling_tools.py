"""Scheduling tool safety unit tests (no live platform)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from session.userdata import SessionUserData
from tools.platform_scheduling import PlatformSchedulingClient
from tools.scheduling import build_scheduling_tools


class FakeSchedulingClient(PlatformSchedulingClient):
    def __init__(self) -> None:
        super().__init__(base_url="http://example", internal_token="tok")
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls.append((path, payload or {}))
        if path.endswith("/slots"):
            return {
                "timezone": "UTC",
                "slot_minutes": 60,
                "slots": [
                    {
                        "starts_at": "2026-07-20T15:00:00+00:00",
                        "ends_at": "2026-07-20T16:00:00+00:00",
                        "local_start": "2026-07-20T15:00:00+00:00",
                        "local_end": "2026-07-20T16:00:00+00:00",
                    }
                ],
            }
        if path.endswith("/appointments") and method == "POST":
            return {
                "appointment": {
                    "id": "appt-1",
                    "confirmation_code": "APT-ABC123",
                    "starts_at": payload["starts_at"] if payload else None,
                    "status": "scheduled",
                }
            }
        if path.endswith("/reschedule"):
            return {
                "appointment": {
                    "id": "appt-1",
                    "confirmation_code": "APT-ABC123",
                    "status": "scheduled",
                }
            }
        if path.endswith("/cancel"):
            return {
                "appointment": {
                    "id": "appt-1",
                    "status": "canceled",
                }
            }
        return {}


def _context(userdata: SessionUserData | None) -> MagicMock:
    ctx = MagicMock()
    ctx.session.userdata = userdata
    ctx.disallow_interruptions = MagicMock()
    return ctx


def _userdata(**kwargs: Any) -> SessionUserData:
    base = dict(
        tenant_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        call_id="call-1",
        room_name="room-1",
        business_name="Acme",
    )
    base.update(kwargs)
    return SessionUserData(**base)


@pytest.mark.asyncio
async def test_get_slots_uses_userdata_tenant() -> None:
    client = FakeSchedulingClient()
    get_slots = build_scheduling_tools(client)[0]
    ctx = _context(_userdata())
    result = await get_slots(ctx)
    assert result["count"] == 1
    assert client.calls[-1][1]["tenant_id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


@pytest.mark.asyncio
async def test_book_requires_confirmation() -> None:
    from livekit.agents.llm import ToolError

    book = build_scheduling_tools(FakeSchedulingClient())[1]
    ctx = _context(_userdata(customer_id="cust-1"))
    with pytest.raises(ToolError):
        await book(
            ctx,
            starts_at="2026-07-20T15:00:00+00:00",
            service_type="AC",
            caller_confirmed=False,
        )


@pytest.mark.asyncio
async def test_book_requires_customer() -> None:
    from livekit.agents.llm import ToolError

    book = build_scheduling_tools(FakeSchedulingClient())[1]
    ctx = _context(_userdata(customer_id=None))
    with pytest.raises(ToolError):
        await book(
            ctx,
            starts_at="2026-07-20T15:00:00+00:00",
            service_type="AC",
            caller_confirmed=True,
        )


@pytest.mark.asyncio
async def test_book_success() -> None:
    client = FakeSchedulingClient()
    book = build_scheduling_tools(client)[1]
    userdata = _userdata(customer_id="cust-1")
    ctx = _context(userdata)
    result = await book(
        ctx,
        starts_at="2026-07-20T15:00:00+00:00",
        service_type="AC repair",
        caller_confirmed=True,
    )
    assert result["ok"] is True
    assert result["confirmation_code"] == "APT-ABC123"
    assert userdata.extra["appointment_id"] == "appt-1"
    assert client.calls[-1][1]["tenant_id"] == userdata.tenant_id
    assert client.calls[-1][1]["customer_id"] == "cust-1"


@pytest.mark.asyncio
async def test_cancel_requires_confirmation() -> None:
    from livekit.agents.llm import ToolError

    cancel = build_scheduling_tools(FakeSchedulingClient())[3]
    ctx = _context(_userdata())
    with pytest.raises(ToolError):
        await cancel(ctx, appointment_id="appt-1", caller_confirmed=False)

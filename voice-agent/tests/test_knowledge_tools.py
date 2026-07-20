"""Knowledge tool unit tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from session.userdata import SessionUserData
from tools.knowledge import build_knowledge_tools
from tools.platform_knowledge import PlatformKnowledgeClient


class FakeKnowledgeClient(PlatformKnowledgeClient):
    def __init__(self) -> None:
        super().__init__(base_url="http://example", internal_token="tok")
        self.queries: list[tuple[str, str]] = []

    def search(
        self,
        *,
        tenant_id: str,
        query: str,
        limit: int = 5,
        agent_profile_id: str | None = None,
    ) -> dict[str, Any]:
        self.queries.append((tenant_id, query, agent_profile_id))
        return {
            "count": 1,
            "articles": [
                {
                    "id": "a1",
                    "title": "Hours",
                    "body": "Open 9-5",
                    "untrusted": True,
                }
            ],
        }


@pytest.mark.asyncio
async def test_search_uses_userdata_tenant() -> None:
    client = FakeKnowledgeClient()
    tool = build_knowledge_tools(client)[0]
    ctx = MagicMock()
    ctx.session.userdata = SessionUserData(
        tenant_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        call_id="c1",
        room_name="r1",
        business_name="Acme",
    )
    result = await tool(ctx, query="hours")
    assert result["count"] == 1
    assert client.queries[0][0] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert "id" not in result["articles"][0]
    assert result["articles"][0]["title"] == "Hours"
    assert ctx.session.userdata.knowledge_lookup_used is True

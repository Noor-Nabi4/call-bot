"""LiveKit SIP inbound trunk and dispatch rule adapters.

Docs (verified via LiveKit MCP):
- https://docs.livekit.io/telephony/accepting-calls/inbound-trunk/
- https://docs.livekit.io/telephony/accepting-calls/dispatch-rule/
- https://docs.livekit.io/telephony/start/providers/twilio/
"""

from __future__ import annotations

from livekit import api

from callbot_platform.telephony.interfaces import (
    DispatchRuleService,
    LiveKitDispatchRuleInfo,
    LiveKitInboundTrunkInfo,
    SipTrunkService,
)


class LiveKitApiError(RuntimeError):
    pass


class LiveKitSipService(SipTrunkService, DispatchRuleService):
    def __init__(
        self,
        *,
        url: str,
        api_key: str,
        api_secret: str,
    ) -> None:
        if not url or not api_key or not api_secret:
            raise LiveKitApiError("LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET are required")
        self._url = url
        self._api_key = api_key
        self._api_secret = api_secret

    def _client(self) -> api.LiveKitAPI:
        return api.LiveKitAPI(self._url, self._api_key, self._api_secret)

    # --- SipTrunkService (LiveKit portion) ---

    def create_or_get_twilio_trunk(self, **kwargs):  # type: ignore[no-untyped-def]
        raise NotImplementedError("Twilio trunks are managed by TwilioSipTrunkService")

    def associate_number_with_twilio_trunk(self, **kwargs):  # type: ignore[no-untyped-def]
        raise NotImplementedError("Twilio trunks are managed by TwilioSipTrunkService")

    async def _create_inbound_trunk_async(
        self, *, name: str, numbers: list[str], metadata: str | None
    ) -> LiveKitInboundTrunkInfo:
        lk = self._client()
        try:
            trunk = api.SIPInboundTrunkInfo(
                name=name,
                numbers=numbers,
                metadata=metadata or "",
            )
            request = api.CreateSIPInboundTrunkRequest(trunk=trunk)
            created = await lk.sip.create_sip_inbound_trunk(request)
            return LiveKitInboundTrunkInfo(
                trunk_id=created.sip_trunk_id,
                name=created.name,
                numbers=list(created.numbers),
            )
        finally:
            await lk.aclose()

    def create_livekit_inbound_trunk(
        self,
        *,
        name: str,
        numbers: list[str],
        metadata: str | None = None,
    ) -> LiveKitInboundTrunkInfo:
        import asyncio

        return asyncio.run(
            self._create_inbound_trunk_async(name=name, numbers=numbers, metadata=metadata)
        )

    async def _delete_inbound_trunk_async(self, trunk_id: str) -> None:
        lk = self._client()
        try:
            await lk.sip.delete_sip_inbound_trunk(
                api.DeleteSIPInboundTrunkRequest(sip_trunk_id=trunk_id)
            )
        finally:
            await lk.aclose()

    def delete_livekit_inbound_trunk(self, trunk_id: str) -> None:
        import asyncio

        asyncio.run(self._delete_inbound_trunk_async(trunk_id))

    async def _create_dispatch_async(
        self,
        *,
        name: str,
        agent_name: str,
        metadata: str,
        trunk_ids: list[str],
        room_prefix: str,
    ) -> LiveKitDispatchRuleInfo:
        lk = self._client()
        try:
            rule = api.SIPDispatchRule(
                dispatch_rule_individual=api.SIPDispatchRuleIndividual(
                    room_prefix=room_prefix,
                )
            )
            info = api.SIPDispatchRuleInfo(
                rule=rule,
                name=name,
                trunk_ids=trunk_ids,
                room_config=api.RoomConfiguration(
                    agents=[
                        api.RoomAgentDispatch(
                            agent_name=agent_name,
                            metadata=metadata,
                        )
                    ]
                ),
            )
            created = await lk.sip.create_sip_dispatch_rule(
                api.CreateSIPDispatchRuleRequest(dispatch_rule=info)
            )
            return LiveKitDispatchRuleInfo(
                dispatch_rule_id=created.sip_dispatch_rule_id,
                name=created.name,
            )
        finally:
            await lk.aclose()

    def create_individual_dispatch_rule(
        self,
        *,
        name: str,
        agent_name: str,
        metadata: str,
        trunk_ids: list[str],
        room_prefix: str = "call-",
    ) -> LiveKitDispatchRuleInfo:
        import asyncio

        return asyncio.run(
            self._create_dispatch_async(
                name=name,
                agent_name=agent_name,
                metadata=metadata,
                trunk_ids=trunk_ids,
                room_prefix=room_prefix,
            )
        )

    async def _delete_dispatch_async(self, dispatch_rule_id: str) -> None:
        lk = self._client()
        try:
            await lk.sip.delete_sip_dispatch_rule(
                api.DeleteSIPDispatchRuleRequest(sip_dispatch_rule_id=dispatch_rule_id)
            )
        finally:
            await lk.aclose()

    def delete_dispatch_rule(self, dispatch_rule_id: str) -> None:
        import asyncio

        asyncio.run(self._delete_dispatch_async(dispatch_rule_id))

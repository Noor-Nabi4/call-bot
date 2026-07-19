"""Human escalation / warm-cold transfer tools.

Docs:
- Warm: https://docs.livekit.io/agents/prebuilt/tasks/warm-transfer/
- Cold: https://docs.livekit.io/telephony/features/transfers/cold/
"""

from __future__ import annotations

import logging
import os
from typing import Any

from livekit import api, rtc
from livekit.agents import RunContext, function_tool, get_job_context
from livekit.agents.llm import ToolError

from session.userdata import SessionUserData
from tools.platform_handoff import PlatformHandoffClient, PlatformHandoffError

logger = logging.getLogger("voice-agent.handoff")

ESCALATION_REASONS = frozenset(
    {
        "billing_dispute",
        "emergency",
        "abuse",
        "caller_request",
        "complex",
        "other",
    }
)


def _userdata(context: RunContext) -> SessionUserData:
    data = context.session.userdata
    if not isinstance(data, SessionUserData):
        raise ToolError("Call is not linked to a business yet.")
    return data


def _find_sip_participant(room: rtc.Room) -> rtc.RemoteParticipant | None:
    for p in room.remote_participants.values():
        if p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
            return p
    return None


async def _warm_transfer(
    *,
    phone: str,
    trunk_id: str,
    chat_ctx: Any,
    extra: str,
) -> None:
    from livekit.agents.beta.workflows import WarmTransferTask

    # Docs: sip_call_to + sip_trunk_id
    # https://docs.livekit.io/agents/prebuilt/tasks/warm-transfer/
    await WarmTransferTask(
        sip_call_to=phone,
        sip_trunk_id=trunk_id,
        chat_ctx=chat_ctx,
        extra_instructions=extra,
    )


async def _cold_transfer(*, room: rtc.Room, phone: str) -> None:
    job_ctx = get_job_context()
    sip_participant = _find_sip_participant(room)
    if sip_participant is None:
        raise ToolError(
            "This call is not a phone call I can transfer. Offer a callback."
        )
    transfer_to = phone if phone.startswith("tel:") else f"tel:{phone}"
    await job_ctx.api.sip.transfer_sip_participant(
        api.TransferSIPParticipantRequest(
            room_name=room.name,
            participant_identity=sip_participant.identity,
            transfer_to=transfer_to,
            play_dialtone=False,
        )
    )


def build_handoff_tools(client: PlatformHandoffClient) -> list[Any]:
    @function_tool()
    async def request_human_handoff(
        context: RunContext,
        reason: str,
        caller_confirmed: bool,
        summary: str | None = None,
    ) -> dict[str, Any]:
        """Transfer the caller to this tenant's human queue when escalation rules apply.

        Use for billing disputes, emergencies, abuse, or when the caller clearly
        asks for a person. Confirm aloud first, then set caller_confirmed=true.

        Args:
            reason: One of billing_dispute, emergency, abuse, caller_request, complex, other.
            caller_confirmed: Must be true after verbal confirmation.
            summary: Short context for the human agent.
        """
        if not caller_confirmed:
            raise ToolError(
                "Confirm with the caller that you will transfer them to a person first."
            )
        reason_n = (reason or "").strip().lower()
        if reason_n not in ESCALATION_REASONS:
            raise ToolError(
                "Use a valid escalation reason: billing_dispute, emergency, abuse, "
                "caller_request, complex, or other."
            )
        data = _userdata(context)
        try:
            payload = client.get_settings(data.tenant_id)
        except PlatformHandoffError as exc:
            raise ToolError(
                "I could not reach the transfer settings right now."
            ) from exc
        settings = payload.get("settings") or {}
        if not settings.get("enabled"):
            raise ToolError(
                "Human transfer is not enabled for this business. Offer a callback instead."
            )
        phone = settings.get("escalation_phone_e164")
        if not phone:
            raise ToolError(
                "No escalation phone is configured. Offer to take a callback number."
            )

        job_ctx = get_job_context()
        mode = (settings.get("mode") or "warm").lower()
        trunk_id = (
            settings.get("sip_outbound_trunk_id")
            or os.getenv("LIVEKIT_SIP_OUTBOUND_TRUNK", "").strip()
        )
        extra = (
            f"Escalation reason: {reason_n}. Tenant: {data.business_name}. "
            f"Caller summary: {summary or 'none'}."
        )

        context.disallow_interruptions()
        await context.session.generate_reply(
            instructions=(
                "Briefly tell the caller you are transferring them to a teammate now."
            )
        )

        try:
            if mode == "warm" and trunk_id:
                await _warm_transfer(
                    phone=phone,
                    trunk_id=trunk_id,
                    chat_ctx=context.session.chat_ctx,
                    extra=extra,
                )
                used = "warm"
            else:
                await _cold_transfer(room=job_ctx.room, phone=phone)
                used = "cold"
        except ToolError:
            raise
        except Exception as exc:
            logger.exception("handoff_failed")
            raise ToolError(
                "The transfer failed. Please offer to take a callback number."
            ) from exc

        logger.info(
            "handoff_completed",
            extra={"tenant_id": data.tenant_id, "reason": reason_n, "mode": used},
        )
        return {"ok": True, "mode": used, "reason": reason_n}

    return [request_human_handoff]

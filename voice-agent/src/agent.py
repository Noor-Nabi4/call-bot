"""LiveKit voice agent: OpenAI Realtime speech-to-speech."""

from __future__ import annotations

import uuid
from pathlib import Path

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    TurnHandlingOptions,
    cli,
    room_io,
)
from livekit.plugins import noise_cancellation, openai
from livekit.plugins.openai import realtime
from openai.types.beta.realtime.session import TurnDetection

from config import ConfigurationError, Settings
from observability.logging import configure_logging, get_logger, log_event
from observability.metrics import CallMetrics
from prompts import build_system_instructions
from session.events import attach_realtime_metrics, attach_session_events
from session.lifecycle import CallLifecycle
from session.state import CallState
from session.userdata import SessionUserData
from tenant.resolve import TenantResolveError, resolver_from_env
from tenant.sip_attrs import extract_sip_context, is_sip_participant
from tools.crm import build_crm_tools
from tools.platform_crm import PlatformCrmError, crm_client_from_env

# Load local secrets for development. Production injects env vars directly.
load_dotenv(Path(__file__).resolve().parent.parent / ".env.local")

configure_logging()
logger = get_logger("voice-agent")


class VoiceAssistant(Agent):
    """Single speech-to-speech assistant for one LiveKit session."""

    def __init__(self, instructions: str, *, tools: list | None = None) -> None:
        super().__init__(instructions=instructions, tools=tools or [])
        self._lifecycle: CallLifecycle | None = None

    def bind_lifecycle(self, lifecycle: CallLifecycle) -> None:
        self._lifecycle = lifecycle

    async def on_enter(self) -> None:
        lifecycle = self._lifecycle
        if lifecycle is None:
            return

        # Per LiveKit realtime metrics recipe: attach after enter when
        # realtime_llm_session is available.
        try:
            attach_realtime_metrics(lifecycle, self.realtime_llm_session)
        except Exception:
            logger.exception(
                "realtime_metrics_attach_failed",
                extra={"call_id": lifecycle.state.call_id},
            )

    async def speak_greeting(self) -> None:
        lifecycle = self._lifecycle
        if lifecycle is None or lifecycle.state.greeting_sent:
            return
        lifecycle.state.greeting_sent = True
        lifecycle.state.mark_active()
        log_event(
            logger,
            "greeting",
            call_id=lifecycle.state.call_id,
            room_name=lifecycle.state.room_name,
            tenant_id=lifecycle.state.tenant_id,
        )
        await self.session.generate_reply(
            instructions=(
                "Greet the caller briefly, introduce yourself as the business "
                "voice assistant, and ask how you can help. One or two short "
                "sentences only."
            )
        )


def _build_realtime_model(settings: Settings) -> openai.realtime.RealtimeModel:
    # Docs: OpenAI Realtime plugin + semantic VAD turn detection
    # https://docs.livekit.io/agents/models/realtime/plugins/openai/
    return realtime.RealtimeModel(
        model=settings.openai_realtime_model,
        voice=settings.openai_voice,
        temperature=settings.temperature,
        api_key=settings.openai_api_key,
        turn_detection=TurnDetection(
            type="semantic_vad",
            eagerness="medium",
            create_response=True,
            interrupt_response=True,
        ),
    )


def _build_session(
    settings: Settings, *, userdata: SessionUserData | None = None
) -> AgentSession:
    # Docs: realtime models use turn_detection="realtime_llm"
    # https://docs.livekit.io/agents/logic/turns/
    return AgentSession(
        llm=_build_realtime_model(settings),
        user_away_timeout=settings.user_away_timeout_sec,
        userdata=userdata,
        turn_handling=TurnHandlingOptions(
            turn_detection="realtime_llm",
            interruption={
                "enabled": True,
                # Kept for false-interruption recovery when applicable.
                "false_interruption_timeout": 2.0,
                "resume_false_interruption": True,
            },
        ),
    )


server = AgentServer()


@server.rtc_session(agent_name="voice-agent")
async def entrypoint(ctx: JobContext) -> None:
    try:
        settings = Settings.from_env()
    except ConfigurationError:
        logger.exception("invalid_configuration")
        raise

    call_id = (
        ctx.job.id if getattr(ctx, "job", None) and ctx.job.id else str(uuid.uuid4())
    )
    room_name = ctx.room.name
    job_metadata = getattr(getattr(ctx, "job", None), "metadata", None)

    ctx.log_context_fields = {
        "room": room_name,
        "call_id": call_id,
        "tenant_id": settings.tenant_id,
    }

    state = CallState(
        call_id=call_id,
        room_name=room_name,
        tenant_id=None,
    )
    metrics = CallMetrics(
        call_id=call_id,
        room_name=room_name,
        tenant_id=None,
    )
    instructions = build_system_instructions(
        business_name=settings.business_name,
        max_spoken_sentences=settings.max_spoken_sentences,
        language=settings.language,
        business_facts=settings.business_facts,
    )

    crm_client = crm_client_from_env()
    session = _build_session(settings)
    agent = VoiceAssistant(instructions=instructions, tools=[])
    lifecycle = CallLifecycle(
        session=session,
        state=state,
        metrics=metrics,
        settings=settings,
        shutdown_job=ctx.shutdown,
    )
    agent.bind_lifecycle(lifecycle)
    attach_session_events(lifecycle, session)

    platform_call_id_holder: dict[str, str | None] = {"id": None}

    async def _on_job_shutdown() -> None:
        # Persist CRM call end when possible.
        userdata = session.userdata
        if (
            isinstance(userdata, SessionUserData)
            and userdata.platform_call_id
            and userdata.tenant_id
        ):
            try:
                crm_client.end_call(
                    tenant_id=userdata.tenant_id,
                    call_id=userdata.platform_call_id,
                    status=state.current_status.value
                    if state.current_status
                    else "closed",
                    disconnect_reason=state.disconnect_reason,
                    metrics=metrics.as_log_fields(),
                    customer_id=userdata.customer_id,
                )
            except Exception:
                logger.exception(
                    "crm_call_end_failed",
                    extra={"call_id": call_id, "tenant_id": userdata.tenant_id},
                )
        if metrics.ended_at is None:
            lifecycle.on_session_closed("job_shutdown")
        else:
            log_event(logger, "job_shutdown", **metrics.as_log_fields())

    ctx.add_shutdown_callback(_on_job_shutdown)

    log_event(
        logger,
        "call_starting",
        call_id=call_id,
        room_name=room_name,
        tenant_id=settings.tenant_id,
        model=settings.openai_realtime_model,
        voice=settings.openai_voice,
        end_of_call_summary_webhook=False,
        crm_tools=True,
    )

    # Docs: https://docs.livekit.io/transport/media/noise-cancellation/
    # BVC for browser/WebRTC; BVCTelephony for SIP callers.
    await session.start(
        agent=agent,
        room=ctx.room,
        room_options=room_io.RoomOptions(
            delete_room_on_close=True,
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind
                    == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )

    lifecycle.start_max_duration_watch()

    # Connect after session start so RoomIO is ready for the greeting path.
    await ctx.connect()

    participant = await ctx.wait_for_participant()
    sip = is_sip_participant(participant)
    resolver = resolver_from_env()

    called_number = None
    trunk_id = None
    if sip:
        provisional = extract_sip_context(participant, room_name=room_name)
        called_number = provisional.called_number
        trunk_id = provisional.inbound_trunk_id

    try:
        resolution = resolver.resolve(
            job_metadata=job_metadata,
            called_number=called_number,
            livekit_inbound_trunk_id=trunk_id,
            is_sip=sip,
        )
    except TenantResolveError as exc:
        log_event(
            logger,
            "tenant_resolve_failed",
            call_id=call_id,
            room_name=room_name,
            code=exc.code,
            error=str(exc),
            is_sip=sip,
        )
        await lifecycle.end_call(reason="tenant_unresolved", error_code=exc.code)
        return

    state.tenant_id = resolution.tenant_id
    metrics.tenant_id = resolution.tenant_id
    ctx.log_context_fields["tenant_id"] = resolution.tenant_id

    caller_number = None
    if sip:
        telephony = extract_sip_context(
            participant,
            room_name=room_name,
            tenant_id=resolution.tenant_id,
            dispatch_rule_id=resolution.livekit_dispatch_rule_id,
        )
        if resolution.livekit_inbound_trunk_id:
            telephony.inbound_trunk_id = resolution.livekit_inbound_trunk_id
        state.apply_telephony(telephony)
        caller_number = telephony.caller_number
        called_number = telephony.called_number or called_number
        if telephony.called_number:
            try:
                resolver.notify_inbound_observed(
                    called_number=telephony.called_number,
                    caller_number=telephony.caller_number,
                    livekit_inbound_trunk_id=telephony.inbound_trunk_id,
                    livekit_room_name=room_name,
                    provider_call_id=telephony.provider_call_id,
                )
            except Exception:
                logger.exception(
                    "inbound_observed_notify_failed",
                    extra={"call_id": call_id, "tenant_id": resolution.tenant_id},
                )

    userdata = SessionUserData(
        tenant_id=resolution.tenant_id,
        call_id=call_id,
        room_name=room_name,
        business_name=settings.business_name,
        caller_number=caller_number,
        called_number=called_number,
        is_sip=sip,
    )
    session.userdata = userdata

    # Bind CRM tools only after fail-closed tenant resolve.
    # Docs: https://docs.livekit.io/agents/logic/tools/definition/
    await agent.update_tools(build_crm_tools(crm_client))

    try:
        started = crm_client.start_call(
            tenant_id=resolution.tenant_id,
            room_name=room_name,
            job_id=call_id,
            caller_number=caller_number,
            called_number=called_number,
            telephony_provider="twilio" if sip else None,
            provider_call_id=(
                state.telephony.provider_call_id if state.telephony else None
            ),
        )
        platform_call = started.get("call") or {}
        userdata.platform_call_id = platform_call.get("id")
        platform_call_id_holder["id"] = userdata.platform_call_id
    except PlatformCrmError:
        logger.exception(
            "crm_call_start_failed",
            extra={"call_id": call_id, "tenant_id": resolution.tenant_id},
        )

    state.mark_active(participant.identity)
    metrics.participant_identity = participant.identity
    log_event(
        logger,
        "participant_connected",
        call_id=call_id,
        room_name=room_name,
        participant_identity=participant.identity,
        tenant_id=resolution.tenant_id,
        is_sip=sip,
        resolve_source=resolution.source,
        caller_number=caller_number,
        called_number=called_number,
        platform_call_id=userdata.platform_call_id,
    )

    # Greeting only after successful tenant resolution (fail-closed for SIP).
    await agent.speak_greeting()


# Keep a stable name for tests and local imports.
Assistant = VoiceAssistant


if __name__ == "__main__":
    cli.run_app(server)

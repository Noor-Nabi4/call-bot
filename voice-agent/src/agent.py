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

# Load local secrets for development. Production injects env vars directly.
load_dotenv(Path(__file__).resolve().parent.parent / ".env.local")

configure_logging()
logger = get_logger("voice-agent")


class VoiceAssistant(Agent):
    """Single speech-to-speech assistant for one LiveKit session."""

    def __init__(self, instructions: str) -> None:
        super().__init__(instructions=instructions)
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

        if lifecycle.state.greeting_sent:
            return

        lifecycle.state.greeting_sent = True
        lifecycle.state.mark_active()
        log_event(
            logger,
            "greeting",
            call_id=lifecycle.state.call_id,
            room_name=lifecycle.state.room_name,
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


def _build_session(settings: Settings) -> AgentSession:
    # Docs: realtime models use turn_detection="realtime_llm"
    # https://docs.livekit.io/agents/logic/turns/
    return AgentSession(
        llm=_build_realtime_model(settings),
        user_away_timeout=settings.user_away_timeout_sec,
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

    ctx.log_context_fields = {
        "room": room_name,
        "call_id": call_id,
        "tenant_id": settings.tenant_id,
    }

    state = CallState(
        call_id=call_id,
        room_name=room_name,
        tenant_id=settings.tenant_id,
    )
    metrics = CallMetrics(call_id=call_id, room_name=room_name)
    instructions = build_system_instructions(
        business_name=settings.business_name,
        max_spoken_sentences=settings.max_spoken_sentences,
        language=settings.language,
        business_facts=settings.business_facts,
    )

    session = _build_session(settings)
    agent = VoiceAssistant(instructions=instructions)
    lifecycle = CallLifecycle(
        session=session,
        state=state,
        metrics=metrics,
        settings=settings,
        shutdown_job=ctx.shutdown,
    )
    agent.bind_lifecycle(lifecycle)
    attach_session_events(lifecycle, session)

    log_event(
        logger,
        "call_starting",
        call_id=call_id,
        room_name=room_name,
        model=settings.openai_realtime_model,
        voice=settings.openai_voice,
    )

    # Docs: https://docs.livekit.io/transport/media/noise-cancellation/
    # BVC for browser/WebRTC; BVCTelephony for SIP callers.
    await session.start(
        agent=agent,
        room=ctx.room,
        room_options=room_io.RoomOptions(
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
    state.mark_active(participant.identity)
    metrics.participant_identity = participant.identity
    log_event(
        logger,
        "participant_connected",
        call_id=call_id,
        room_name=room_name,
        participant_identity=participant.identity,
    )


# Keep a stable name for tests and local imports.
Assistant = VoiceAssistant


if __name__ == "__main__":
    cli.run_app(server)

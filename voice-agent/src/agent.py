"""LiveKit voice agent: OpenAI Realtime speech-to-speech."""

from __future__ import annotations

import asyncio
import math
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    TurnHandlingOptions,
    cli,
    room_io,
)
from livekit.agents.worker import ServerEnvOption
from livekit.plugins import noise_cancellation, openai
from livekit.plugins.openai import realtime
from openai.types.beta.realtime.session import TurnDetection

from config import ConfigurationError, Settings
from observability.logging import configure_logging, get_logger, log_event
from observability.metrics import CallMetrics
from prompts import (
    bootstrap_instructions,
    build_system_instructions_from_profile,
)
from session.events import attach_realtime_metrics, attach_session_events
from session.fast_start import (
    build_greeting_instructions,
    cancel_task,
    run_in_thread,
)
from session.lifecycle import CallLifecycle
from session.state import CallState
from session.userdata import SessionUserData
from tenant.agent_profile import AgentProfile, CallFacts
from tenant.resolve import (
    PlatformTenantResolver,
    TenantResolution,
    TenantResolveError,
    is_console_runtime,
    resolver_from_env,
    voice_runtime_mode,
)
from tenant.sip_attrs import extract_sip_context, is_sip_participant
from tools.crm import build_crm_tools
from tools.handoff import build_handoff_tools
from tools.knowledge import build_knowledge_tools
from tools.platform_agent_profile import (
    PlatformAgentProfileClient,
    PlatformAgentProfileError,
    agent_profile_client_from_env,
)
from tools.platform_crm import PlatformCrmError, crm_client_from_env
from tools.platform_handoff import handoff_client_from_env
from tools.platform_knowledge import knowledge_client_from_env
from tools.platform_scheduling import scheduling_client_from_env
from tools.scheduling import build_scheduling_tools

# Load local secrets for development. Production injects env vars directly.
load_dotenv(Path(__file__).resolve().parent.parent / ".env.local")

configure_logging()
logger = get_logger("voice-agent")

SERVICE_UNAVAILABLE_SPEECH = (
    "I'm sorry, our phone assistant is temporarily unavailable. "
    "Please try calling again shortly."
)


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
            agent_profile_version=lifecycle.metrics.agent_profile_version,
        )
        userdata = self.session.userdata
        greeting_hint = None
        if isinstance(userdata, SessionUserData) and userdata.agent_profile:
            greeting_hint = userdata.agent_profile.greeting
        await self.session.generate_reply(
            instructions=build_greeting_instructions(greeting_hint)
        )

    async def speak_service_unavailable(self) -> None:
        # Docs: AgentSession.say for predetermined speech (returns SpeechHandle).
        try:
            handle = self.session.say(
                SERVICE_UNAVAILABLE_SPEECH, allow_interruptions=False
            )
            await handle.wait_for_playout()
        except Exception:
            logger.exception("service_unavailable_speech_failed")


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


def _prewarm(proc: JobProcess) -> None:
    # Docs: https://docs.livekit.io/agents/server/options/#prewarm-function
    # Import heavy plugins into idle job processes so first call pays less.
    from livekit.plugins import noise_cancellation as _nc  # noqa: F401
    from livekit.plugins import openai as _openai  # noqa: F401

    proc.userdata["prewarmed"] = True


# Keep one warmed process in local `dev` so job spawn is not cold every call.
# Production still scales idle processes with CPU count.
# Docs: https://docs.livekit.io/agents/server/options/#prewarm-function
server = AgentServer(
    setup_fnc=_prewarm,
    num_idle_processes=ServerEnvOption(
        dev_default=int(os.getenv("AGENT_NUM_IDLE_PROCESSES", "1") or "1"),
        prod_default=math.ceil(os.cpu_count() or 1),
    ),
)


async def _prepare_tenant_profile(
    *,
    resolver: PlatformTenantResolver,
    profile_client: PlatformAgentProfileClient,
    job_metadata: str | None,
    called_number: str | None,
    livekit_inbound_trunk_id: str | None,
    is_sip: bool,
) -> tuple[TenantResolution, AgentProfile]:
    resolution = await run_in_thread(
        lambda: resolver.resolve(
            job_metadata=job_metadata,
            called_number=called_number,
            livekit_inbound_trunk_id=livekit_inbound_trunk_id,
            is_sip=is_sip,
        )
    )
    profile = await run_in_thread(
        lambda: profile_client.get_profile(resolution.tenant_id)
    )
    if profile.tenant_id != resolution.tenant_id:
        raise PlatformAgentProfileError(
            "agent_profile_tenant_mismatch",
            "Profile tenant_id does not match resolved tenant",
        )
    return resolution, profile


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
    # Bootstrap only — no business identity until the tenant profile loads.
    # Docs: https://docs.livekit.io/agents/logic/tools/design/#update-in-place
    instructions = bootstrap_instructions()

    crm_client = crm_client_from_env()
    scheduling_client = scheduling_client_from_env()
    knowledge_client = knowledge_client_from_env()
    handoff_client = handoff_client_from_env()
    profile_client = agent_profile_client_from_env()
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

    async def _on_job_shutdown() -> None:
        # Persist CRM call end when possible.
        try:
            userdata = session.userdata
        except ValueError:
            userdata = None
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
        voice_runtime_mode=voice_runtime_mode(),
        console_helper_active=is_console_runtime(),
        env_business_facts_unused_after_resolve=True,
    )
    if is_console_runtime():
        log_event(
            logger,
            "console_helper_active",
            call_id=call_id,
            note=(
                "VOICE_RUNTIME_MODE=console: env TENANT_ID fallback may apply for "
                "non-SIP only. BUSINESS_* is never used after tenant resolve."
            ),
        )

    resolver = resolver_from_env()

    # Overlap non-SIP tenant+profile HTTP with OpenAI realtime session connect.
    # SIP must wait for participant DID attrs; discard this task if the caller is SIP.
    early_prepare_task: asyncio.Task[tuple[TenantResolution, AgentProfile]] = (
        asyncio.create_task(
            _prepare_tenant_profile(
                resolver=resolver,
                profile_client=profile_client,
                job_metadata=job_metadata,
                called_number=None,
                livekit_inbound_trunk_id=None,
                is_sip=False,
            )
        )
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

    called_number = None
    trunk_id = None
    if sip:
        await cancel_task(early_prepare_task)
        provisional = extract_sip_context(participant, room_name=room_name)
        called_number = provisional.called_number
        trunk_id = provisional.inbound_trunk_id
        try:
            resolution, profile = await _prepare_tenant_profile(
                resolver=resolver,
                profile_client=profile_client,
                job_metadata=job_metadata,
                called_number=called_number,
                livekit_inbound_trunk_id=trunk_id,
                is_sip=True,
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
            await agent.speak_service_unavailable()
            await lifecycle.end_call(reason="tenant_unresolved", error_code=exc.code)
            return
        except PlatformAgentProfileError as exc:
            log_event(
                logger,
                "agent_profile_load_failed",
                call_id=call_id,
                room_name=room_name,
                tenant_id=settings.tenant_id,
                code=exc.code,
                error=str(exc),
                is_sip=True,
            )
            await agent.speak_service_unavailable()
            await lifecycle.end_call(
                reason="agent_profile_unavailable",
                error_code=exc.code,
            )
            return
    else:
        try:
            resolution, profile = await early_prepare_task
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
            await agent.speak_service_unavailable()
            await lifecycle.end_call(reason="tenant_unresolved", error_code=exc.code)
            return
        except PlatformAgentProfileError as exc:
            log_event(
                logger,
                "agent_profile_load_failed",
                call_id=call_id,
                room_name=room_name,
                tenant_id=settings.tenant_id,
                code=exc.code,
                error=str(exc),
                is_sip=False,
            )
            await agent.speak_service_unavailable()
            await lifecycle.end_call(
                reason="agent_profile_unavailable"
                if exc.code != "agent_profile_tenant_mismatch"
                else "agent_profile_tenant_mismatch",
                error_code=exc.code,
            )
            return

    state.tenant_id = resolution.tenant_id
    metrics.tenant_id = resolution.tenant_id
    ctx.log_context_fields["tenant_id"] = resolution.tenant_id
    metrics.agent_profile_version = profile.profile_version
    metrics.requested_language = profile.default_language
    ctx.log_context_fields["agent_profile_version"] = profile.profile_version

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

    call_facts = CallFacts(caller_phone=caller_number)
    userdata = SessionUserData(
        tenant_id=resolution.tenant_id,
        call_id=call_id,
        room_name=room_name,
        business_name=profile.business_name,
        agent_profile=profile,
        agent_profile_version=profile.profile_version,
        call_facts=call_facts,
        requested_language=profile.default_language,
        caller_number=caller_number,
        called_number=called_number,
        is_sip=sip,
    )
    session.userdata = userdata

    tenant_instructions = build_system_instructions_from_profile(
        profile,
        max_spoken_sentences=settings.max_spoken_sentences,
        call_facts=call_facts,
    )
    # Docs: https://docs.livekit.io/agents/logic/tools/design/
    await agent.update_instructions(tenant_instructions)

    # Bind tools only after fail-closed tenant + profile resolve.
    # Docs: https://docs.livekit.io/agents/logic/tools/definition/
    await agent.update_tools(
        [
            *build_crm_tools(crm_client),
            *build_scheduling_tools(scheduling_client),
            *build_knowledge_tools(knowledge_client, metrics=metrics),
            *build_handoff_tools(handoff_client),
        ]
    )

    # Overlap CRM call-start HTTP with greeting generation.
    async def _start_crm_call() -> str | None:
        try:
            started = await run_in_thread(
                lambda: crm_client.start_call(
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
            )
            platform_call = started.get("call") or {}
            call_row_id = platform_call.get("id")
            return str(call_row_id) if call_row_id else None
        except PlatformCrmError:
            logger.exception(
                "crm_call_start_failed",
                extra={"call_id": call_id, "tenant_id": resolution.tenant_id},
            )
            return None

    crm_task = asyncio.create_task(_start_crm_call())

    state.mark_active(participant.identity)
    metrics.participant_identity = participant.identity
    log_event(
        logger,
        "participant_connected",
        call_id=call_id,
        room_name=room_name,
        participant_identity=participant.identity,
        tenant_id=resolution.tenant_id,
        agent_profile_version=profile.profile_version,
        requested_language=profile.default_language,
        is_sip=sip,
        resolve_source=resolution.source,
        caller_number=caller_number,
        called_number=called_number,
        early_prepare=not sip,
    )

    # Greeting only after successful tenant + profile resolution.
    await agent.speak_greeting()
    userdata.platform_call_id = await crm_task
    if userdata.platform_call_id:
        log_event(
            logger,
            "crm_call_started",
            call_id=call_id,
            tenant_id=resolution.tenant_id,
            platform_call_id=userdata.platform_call_id,
        )


# Keep a stable name for tests and local imports.
Assistant = VoiceAssistant


if __name__ == "__main__":
    cli.run_app(server)

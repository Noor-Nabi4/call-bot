"use client";

import {
  BarVisualizer,
  LiveKitRoom,
  RoomAudioRenderer,
  useVoiceAssistant,
  VoiceAssistantControlBar,
} from "@livekit/components-react";
import "@livekit/components-styles";
import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Reveal } from "@/components/landing/reveal";
import { track } from "@/lib/analytics";
import { voiceDemo as copy } from "@/lib/copy";
import { safeUserError } from "@/lib/safe-error";

type ConnectionDetails = {
  serverUrl: string;
  roomName: string;
  participantName: string;
  participantToken: string;
  agentName: string;
};

type CallPhase =
  | "idle"
  | "connecting"
  | "listening"
  | "thinking"
  | "speaking"
  | "interrupted"
  | "disconnected"
  | "error";

const PHASE_LABELS: Record<CallPhase, string> = {
  idle: copy.ready,
  connecting: copy.connecting,
  listening: copy.listening,
  thinking: copy.thinking,
  speaking: copy.speaking,
  interrupted: copy.interrupted,
  disconnected: copy.ended,
  error: copy.connectionProblem,
};

function mapAgentState(state: string | undefined): CallPhase {
  if (!state) return "listening";
  const s = state.toLowerCase();
  if (s.includes("listen")) return "listening";
  if (s.includes("think")) return "thinking";
  if (s.includes("speak")) return "speaking";
  if (s.includes("interrupt")) return "interrupted";
  return "listening";
}

function AgentStage({ onPhase }: { onPhase: (phase: CallPhase) => void }) {
  const { state, audioTrack, agentTranscriptions } = useVoiceAssistant();
  const phase = mapAgentState(state);

  useEffect(() => {
    onPhase(phase);
  }, [phase, onPhase]);

  const latestTranscript = useMemo(() => {
    if (!agentTranscriptions?.length) return null;
    return agentTranscriptions[agentTranscriptions.length - 1]?.text ?? null;
  }, [agentTranscriptions]);

  return (
    <div className="grid gap-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="m-0 text-[11px] tracking-[0.12em] text-hero-muted uppercase">
            {copy.sessionLabel}
          </p>
          <p className="mt-1 font-display text-2xl font-semibold tracking-[-0.03em] text-white">
            {PHASE_LABELS[phase]}
          </p>
        </div>
        <span className="rounded-full bg-teal/20 px-3 py-1 text-xs font-semibold text-teal-bright">
          Live
        </span>
      </div>

      <div className="relative mx-auto grid size-44 place-items-center sm:size-52">
        <div
          className={`absolute inset-0 rounded-full bg-teal/20 ${
            phase === "speaking" || phase === "listening"
              ? "animate-pulse"
              : ""
          }`}
          aria-hidden
        />
        <div className="relative z-[1] grid size-[78%] place-items-center rounded-full border border-white/15 bg-white/5">
          <BarVisualizer
            state={state}
            barCount={20}
            trackRef={audioTrack}
            className="lk-audio-bar-visualizer h-16 w-full max-w-[10rem]"
            options={{ minHeight: 5 }}
          />
        </div>
      </div>

      <div className="min-h-16 rounded-[var(--radius-md)] border border-white/10 bg-white/5 px-4 py-3">
        <p className="m-0 text-sm leading-relaxed text-white/85 sm:text-base">
          {latestTranscript || copy.waitingHint}
        </p>
      </div>
    </div>
  );
}

export function VoiceDemoSection() {
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [details, setDetails] = useState<ConnectionDetails | null>(null);
  const [phase, setPhase] = useState<CallPhase>("idle");

  const connect = useCallback(async () => {
    setConnecting(true);
    setError(null);
    setPhase("connecting");
    track("voice_demo_start");
    try {
      const response = await fetch("/api/token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const payload = (await response.json()) as ConnectionDetails & {
        error?: string;
      };
      if (!response.ok) {
        throw new Error(payload.error || copy.startFailed);
      }
      setDetails(payload);
      track("voice_demo_connected", { room: payload.roomName });
    } catch (err) {
      setDetails(null);
      setPhase("error");
      setError(safeUserError(err, copy.startFailed));
      track("voice_demo_error");
    } finally {
      setConnecting(false);
    }
  }, []);

  const disconnect = useCallback(() => {
    setDetails(null);
    setPhase("disconnected");
    setError(null);
    track("voice_demo_end");
  }, []);

  const onPhase = useCallback((next: CallPhase) => {
    setPhase(next);
  }, []);

  return (
    <section
      id="demo"
      className="section-pad relative overflow-hidden border-t border-line bg-hero text-white"
      aria-labelledby="demo-heading"
    >
      <div
        className="pointer-events-none absolute inset-0"
        aria-hidden="true"
        style={{
          background:
            "radial-gradient(60% 50% at 20% 20%, rgba(20,184,160,0.22), transparent 55%), radial-gradient(50% 40% at 90% 80%, rgba(47,111,173,0.18), transparent 50%)",
        }}
      />
      <div className="relative z-[1] content-width grid items-center gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,24rem)] lg:gap-14">
        <Reveal variant="left">
          <div className="max-w-xl">
            <p className="m-0 mb-3 inline-flex rounded-full border border-white/15 bg-white/5 px-3 py-1 text-[11px] font-semibold tracking-[0.12em] text-teal-bright uppercase">
              Interactive demo
            </p>
            <h2
              id="demo-heading"
              className="font-display m-0 text-[clamp(1.9rem,4vw,2.85rem)] font-semibold leading-[1.08] tracking-[-0.04em]"
            >
              {copy.title}
            </h2>
            <p className="mt-4 m-0 text-base leading-relaxed text-hero-muted sm:text-lg">
              {copy.supporting}
            </p>
            <p className="mt-4 m-0 text-sm text-hero-muted/90">{copy.privacy}</p>
            <div className="mt-6">
              <Link
                href="/signup"
                onClick={() => track("cta_start_trial", { source: "demo" })}
                className="text-sm font-semibold text-teal-bright transition-colors hover:text-white"
              >
                {copy.ctaAfter} →
              </Link>
            </div>
          </div>
        </Reveal>

        <Reveal variant="right">
          <div className="rounded-[24px] border border-white/10 bg-white/[0.04] p-5 shadow-[var(--shadow-lg)] backdrop-blur-sm sm:p-6">
            {details ? (
              <LiveKitRoom
                token={details.participantToken}
                serverUrl={details.serverUrl}
                connect
                audio
                video={false}
                onDisconnected={() => {
                  setPhase("disconnected");
                  disconnect();
                }}
                onError={() => {
                  setPhase("error");
                  setError(copy.interruptedError);
                  track("voice_demo_error");
                }}
                className="grid gap-5"
              >
                <AgentStage key={details.roomName} onPhase={onPhase} />
                <RoomAudioRenderer />
                <div className="flex flex-col items-stretch gap-3">
                  <div className="voice-demo-controls [&_.lk-button]:rounded-full [&_.lk-button]:bg-white/10">
                    <VoiceAssistantControlBar controls={{ leave: true }} />
                  </div>
                  <button
                    type="button"
                    onClick={disconnect}
                    className="inline-flex items-center justify-center rounded-[var(--radius-md)] border border-white/20 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-white/10"
                  >
                    {copy.endCall}
                  </button>
                </div>
              </LiveKitRoom>
            ) : (
              <div className="grid gap-5">
                <div>
                  <p className="m-0 text-[11px] tracking-[0.12em] text-hero-muted uppercase">
                    {copy.sessionLabel}
                  </p>
                  <p className="mt-1 font-display text-2xl font-semibold tracking-[-0.03em]">
                    {PHASE_LABELS[phase === "idle" ? "idle" : phase]}
                  </p>
                </div>
                <p className="m-0 text-sm leading-relaxed text-hero-muted">
                  {copy.idleHint}
                </p>
                <button
                  type="button"
                  onClick={connect}
                  disabled={connecting}
                  aria-busy={connecting}
                  className="inline-flex items-center justify-center rounded-[var(--radius-md)] bg-teal-bright px-5 py-3.5 text-sm font-semibold text-hero transition-[transform,background-color] duration-200 hover:-translate-y-px hover:bg-white disabled:cursor-wait disabled:opacity-70"
                >
                  {connecting ? copy.connectingAction : copy.startCall}
                </button>
              </div>
            )}

            {error ? (
              <p
                className="mt-4 m-0 rounded-[var(--radius-md)] border border-red-400/30 bg-red-500/10 px-3 py-2 text-sm text-red-100"
                role="alert"
              >
                {error}
              </p>
            ) : null}
            <p className="sr-only">Current phase: {PHASE_LABELS[phase]}</p>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

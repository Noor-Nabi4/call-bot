"use client";

import {
  BarVisualizer,
  LiveKitRoom,
  RoomAudioRenderer,
  useVoiceAssistant,
  VoiceAssistantControlBar,
} from "@livekit/components-react";
import "@livekit/components-styles";
import { Phone, PhoneOff } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { cn } from "@/lib/cn";
import { Button, ErrorBanner } from "@/components/ui";
import { voice } from "@/lib/copy";
import { safeConnectionError, safeUserError } from "@/lib/safe-error";

type ConnectionDetails = {
  serverUrl: string;
  roomName: string;
  participantName: string;
  participantToken: string;
  agentName: string;
  tenantId: string | null;
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

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0");
  const s = Math.floor(seconds % 60)
    .toString()
    .padStart(2, "0");
  return `${m}:${s}`;
}

function mapAgentState(state: string | undefined): CallPhase {
  if (!state) return "listening";
  const s = state.toLowerCase();
  if (s.includes("listen")) return "listening";
  if (s.includes("think")) return "thinking";
  if (s.includes("speak")) return "speaking";
  if (s.includes("interrupt")) return "interrupted";
  return "listening";
}

const PHASE_LABELS: Record<CallPhase, string> = {
  idle: voice.ready,
  connecting: voice.connecting,
  listening: voice.listening,
  thinking: voice.preparing,
  speaking: voice.speaking,
  interrupted: voice.interrupted,
  disconnected: voice.ended,
  error: voice.connectionProblem,
};

function CallTimer({ connected }: { connected: boolean }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!connected) return;
    const started = Date.now();
    const id = window.setInterval(() => {
      setElapsed(Math.floor((Date.now() - started) / 1000));
    }, 1000);
    return () => window.clearInterval(id);
  }, [connected]);

  return (
    <span className="font-mono text-sm tabular-nums text-text-secondary">
      {formatElapsed(connected ? elapsed : 0)}
    </span>
  );
}

function AgentStage({
  onPhase,
  timerKey,
}: {
  onPhase: (phase: CallPhase) => void;
  timerKey: string;
}) {
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
    <section aria-live="polite" className="grid gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="m-0 text-[0.7rem] tracking-[0.16em] text-text-muted uppercase">
            {voice.sessionLabel}
          </p>
          <p className="mt-1 font-display text-2xl font-semibold tracking-tight sm:text-3xl">
            {PHASE_LABELS[phase]}
          </p>
        </div>
        <CallTimer key={timerKey} connected />
      </div>

      <div className="relative mx-auto grid size-48 place-items-center sm:size-56">
        <div
          className={cn(
            "absolute inset-0 rounded-full bg-brand-soft",
            phase === "speaking" || phase === "listening"
              ? "animate-[pulse-ring_2.4s_ease-in-out_infinite]"
              : null,
          )}
          aria-hidden
        />
        <div className="relative z-[1] grid size-[78%] place-items-center rounded-full border border-border bg-surface-strong">
          <BarVisualizer
            state={state}
            barCount={24}
            trackRef={audioTrack}
            className="visualizer h-20 w-full max-w-[11rem]"
            options={{ minHeight: 6 }}
          />
        </div>
      </div>

      <div className="min-h-16 rounded-xl border border-border bg-surface-strong/60 px-4 py-3">
        {latestTranscript ? (
          <p className="m-0 text-base leading-relaxed text-text-primary">
            {latestTranscript}
          </p>
        ) : (
          <p className="m-0 text-base leading-relaxed text-text-muted">
            {voice.waitingHint}
          </p>
        )}
      </div>
    </section>
  );
}

export function Playground() {
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [details, setDetails] = useState<ConnectionDetails | null>(null);
  const [phase, setPhase] = useState<CallPhase>("idle");

  const connect = useCallback(async () => {
    setConnecting(true);
    setError(null);
    setPhase("connecting");
    try {
      const response = await fetch("/api/token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || voice.startFailed);
      }
      setDetails(payload as ConnectionDetails);
    } catch (err) {
      setDetails(null);
      setPhase("error");
      setError(safeUserError(err, voice.startFailed));
    } finally {
      setConnecting(false);
    }
  }, []);

  const disconnect = useCallback(() => {
    setDetails(null);
    setPhase("disconnected");
    setError(null);
  }, []);

  const onPhase = useCallback((next: CallPhase) => {
    setPhase(next);
  }, []);

  if (details) {
    return (
      <div className="glass-panel animate-[rise_420ms_ease-out] w-full max-w-xl p-[clamp(1.25rem,3vw,1.75rem)]">
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
            setError(voice.interruptedError);
          }}
          className="grid gap-5"
        >
          <AgentStage
            key={details.roomName}
            timerKey={details.roomName}
            onPhase={onPhase}
          />
          <RoomAudioRenderer />
          <div className="controls flex flex-col items-center gap-3">
            <VoiceAssistantControlBar controls={{ leave: true }} />
            <Button
              variant="danger"
              onClick={disconnect}
              className="w-full max-w-xs"
            >
              <PhoneOff className="size-4" aria-hidden />
              {voice.endCall}
            </Button>
          </div>
        </LiveKitRoom>
        {error ? (
          <div className="mt-4">
            <ErrorBanner message={safeConnectionError(error)} />
          </div>
        ) : null}
        <p className="sr-only">Current phase: {PHASE_LABELS[phase]}</p>
      </div>
    );
  }

  return (
    <div className="glass-panel animate-[rise_420ms_ease-out] w-full max-w-xl p-[clamp(1.25rem,3vw,1.75rem)]">
      <div className="mb-6 flex items-center justify-between gap-3">
        <div>
          <p className="m-0 text-[0.7rem] tracking-[0.16em] text-text-muted uppercase">
            {voice.sessionLabel}
          </p>
          <p className="mt-1 font-display text-2xl font-semibold tracking-tight">
            {PHASE_LABELS[phase === "idle" ? "idle" : phase]}
          </p>
        </div>
        <CallTimer key="idle" connected={false} />
      </div>

      <div className="relative mx-auto mb-6 grid size-40 place-items-center">
        <div
          className="absolute inset-0 rounded-full bg-brand-soft opacity-60"
          aria-hidden
        />
        <div className="relative z-[1] grid size-[72%] place-items-center rounded-full border border-border bg-surface-strong text-brand">
          <Phone className="size-8" aria-hidden />
        </div>
      </div>

      <p className="mb-6 text-[0.95rem] leading-relaxed text-text-secondary">
        {voice.idleHint}
      </p>

      <Button
        className="w-full"
        onClick={connect}
        disabled={connecting}
        aria-busy={connecting}
      >
        <Phone className="size-4" aria-hidden />
        {connecting ? voice.connectingAction : voice.startCall}
      </Button>

      {error ? (
        <div className="mt-4">
          <ErrorBanner message={error} />
        </div>
      ) : null}
    </div>
  );
}

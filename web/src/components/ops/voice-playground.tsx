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
import { Button, ErrorState } from "@/components/ui";
import { cn } from "@/lib/cn";
import { safeUserError } from "@/lib/safe-error";
import type { TestCallSession } from "@/types";

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
  idle: "Ready to test",
  connecting: "Connecting…",
  listening: "Listening",
  thinking: "Thinking",
  speaking: "Speaking",
  interrupted: "Interrupted",
  disconnected: "Call ended",
  error: "Connection problem",
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

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0");
  const s = Math.floor(seconds % 60)
    .toString()
    .padStart(2, "0");
  return `${m}:${s}`;
}

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
    <span className="font-mono text-sm tabular-nums text-text-muted">
      {formatElapsed(connected ? elapsed : 0)}
    </span>
  );
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
    <section aria-live="polite" className="grid gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="m-0 text-[0.7rem] tracking-[0.16em] text-text-muted uppercase">
            Live session
          </p>
          <p className="mt-1 font-heading text-2xl font-semibold tracking-tight text-text-primary">
            {PHASE_LABELS[phase]}
          </p>
        </div>
        <CallTimer connected />
      </div>

      <div className="relative mx-auto grid size-44 place-items-center sm:size-52">
        <div
          className={cn(
            "absolute inset-0 rounded-full bg-brand-soft",
            phase === "speaking" || phase === "listening"
              ? "animate-pulse"
              : null,
          )}
          aria-hidden
        />
        <div className="relative z-[1] grid size-[78%] place-items-center rounded-full border border-border bg-surface">
          <BarVisualizer
            state={state}
            barCount={24}
            trackRef={audioTrack}
            className="h-20 w-full max-w-[11rem]"
            options={{ minHeight: 6 }}
          />
        </div>
      </div>

      <div className="min-h-16 rounded-[12px] border border-border bg-surface-muted/60 px-4 py-3">
        {latestTranscript ? (
          <p className="m-0 text-sm leading-relaxed text-text-primary">
            {latestTranscript}
          </p>
        ) : (
          <p className="m-0 text-sm leading-relaxed text-text-muted">
            Speak after the agent greets you. Use your mic to test your agent
            profile.
          </p>
        )}
      </div>
    </section>
  );
}

type VoicePlaygroundProps = {
  session: TestCallSession;
  onEnded: () => void;
  onError: (message: string) => void;
};

export function VoicePlayground({
  session,
  onEnded,
  onError,
}: VoicePlaygroundProps) {
  const [phase, setPhase] = useState<CallPhase>("connecting");
  const [error, setError] = useState<string | null>(null);

  const onPhase = useCallback((next: CallPhase) => {
    setPhase(next);
  }, []);

  return (
    <div className="w-full rounded-[16px] border border-border bg-surface p-5 sm:p-6">
      <LiveKitRoom
        token={session.participant_token}
        serverUrl={session.server_url}
        connect
        audio
        video={false}
        onDisconnected={() => {
          setPhase("disconnected");
          onEnded();
        }}
        onError={() => {
          const message = "The voice session failed. Please try again.";
          setPhase("error");
          setError(message);
          onError(message);
        }}
        className="grid gap-5"
      >
        <AgentStage onPhase={onPhase} />
        <RoomAudioRenderer />
        <div className="flex flex-col items-center gap-3">
          <VoiceAssistantControlBar controls={{ leave: true }} />
          <Button variant="danger" onClick={onEnded} className="w-full max-w-xs">
            <PhoneOff className="size-4" aria-hidden />
            End test call
          </Button>
        </div>
      </LiveKitRoom>
      {error ? (
        <div className="mt-4">
          <ErrorState message={safeUserError(error, error)} />
        </div>
      ) : null}
      <p className="sr-only">Current phase: {PHASE_LABELS[phase]}</p>
    </div>
  );
}

type IdlePlaygroundProps = {
  connecting: boolean;
  error: string | null;
  onStart: () => void;
  disabled?: boolean;
};

export function IdlePlayground({
  connecting,
  error,
  onStart,
  disabled,
}: IdlePlaygroundProps) {
  return (
    <div className="w-full rounded-[16px] border border-border bg-surface p-5 sm:p-6">
      <div className="mb-6 flex items-center justify-between gap-3">
        <div>
          <p className="m-0 text-[0.7rem] tracking-[0.16em] text-text-muted uppercase">
            Tenant playground
          </p>
          <p className="mt-1 font-heading text-2xl font-semibold tracking-tight text-text-primary">
            {PHASE_LABELS.idle}
          </p>
        </div>
        <CallTimer connected={false} />
      </div>

      <div className="relative mx-auto mb-6 grid size-36 place-items-center">
        <div
          className="absolute inset-0 rounded-full bg-brand-soft opacity-70"
          aria-hidden
        />
        <div className="relative z-[1] grid size-[72%] place-items-center rounded-full border border-border bg-surface text-brand">
          <Phone className="size-8" aria-hidden />
        </div>
      </div>

      <p className="mb-6 text-sm leading-relaxed text-text-secondary">
        Start a browser voice session against your selected agent profile. This
        uses your tenant credentials and signed metadata — not the public landing
        demo.
      </p>

      <Button
        className="w-full"
        onClick={onStart}
        disabled={connecting || disabled}
        aria-busy={connecting}
      >
        <Phone className="size-4" aria-hidden />
        {connecting ? "Starting…" : "Start test call"}
      </Button>

      {error ? (
        <div className="mt-4">
          <ErrorState message={error} />
        </div>
      ) : null}
    </div>
  );
}

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

  const labels: Record<CallPhase, string> = {
    idle: "Idle",
    connecting: "Connecting",
    listening: "Listening",
    thinking: "Thinking",
    speaking: "Speaking",
    interrupted: "Interrupted",
    disconnected: "Disconnected",
    error: "Error",
  };

  return (
    <section aria-live="polite" className="grid gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="m-0 text-[0.7rem] tracking-[0.16em] text-text-muted uppercase">
            Live status
          </p>
          <p className="mt-1 font-display text-2xl font-semibold tracking-tight capitalize sm:text-3xl">
            {labels[phase]}
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
            Waiting for the agent to speak. Allow microphone access when
            prompted.
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
        throw new Error(payload.error || "Token request failed");
      }
      setDetails(payload as ConnectionDetails);
    } catch (err) {
      setDetails(null);
      setPhase("error");
      setError(err instanceof Error ? err.message : "Unable to connect");
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
        <div className="mb-5 flex flex-wrap gap-2 text-xs text-text-muted">
          <span className="rounded-full border border-border bg-surface-strong px-2.5 py-1">
            Room {details.roomName}
          </span>
          <span className="rounded-full border border-border bg-surface-strong px-2.5 py-1">
            Agent {details.agentName}
          </span>
          {details.tenantId ? (
            <span className="rounded-full border border-border bg-surface-strong px-2.5 py-1">
              Tenant {details.tenantId}
            </span>
          ) : null}
        </div>
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
          onError={(err) => {
            setPhase("error");
            setError(err.message);
          }}
          className="grid gap-5"
        >
          <AgentStage key={details.roomName} timerKey={details.roomName} onPhase={onPhase} />
          <RoomAudioRenderer />
          <div className="controls flex flex-col items-center gap-3">
            <VoiceAssistantControlBar controls={{ leave: true }} />
            <Button variant="danger" onClick={disconnect} className="w-full max-w-xs">
              <PhoneOff className="size-4" aria-hidden />
              End call
            </Button>
          </div>
        </LiveKitRoom>
        {error ? <div className="mt-4"><ErrorBanner message={error} /></div> : null}
        <p className="sr-only">Current phase: {phase}</p>
      </div>
    );
  }

  return (
    <div className="glass-panel animate-[rise_420ms_ease-out] w-full max-w-xl p-[clamp(1.25rem,3vw,1.75rem)]">
      <div className="mb-6 flex items-center justify-between gap-3">
        <div>
          <p className="m-0 text-[0.7rem] tracking-[0.16em] text-text-muted uppercase">
            Session
          </p>
          <p className="mt-1 font-display text-2xl font-semibold tracking-tight">
            {phase === "error"
              ? "Connection error"
              : phase === "disconnected"
                ? "Disconnected"
                : phase === "connecting"
                  ? "Connecting…"
                  : "Ready to talk"}
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
        Start a browser session against your LiveKit{" "}
        <code className="text-brand-bright">voice-agent</code> worker. A
        short-lived token is minted and the agent is dispatched into the room.
      </p>

      <Button
        className="w-full"
        onClick={connect}
        disabled={connecting}
        aria-busy={connecting}
      >
        <Phone className="size-4" aria-hidden />
        {connecting ? "Connecting…" : "Start call"}
      </Button>

      {error ? (
        <div className="mt-4">
          <ErrorBanner message={error} />
        </div>
      ) : null}
    </div>
  );
}

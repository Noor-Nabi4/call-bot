"use client";

import {
  BarVisualizer,
  LiveKitRoom,
  RoomAudioRenderer,
  useVoiceAssistant,
  VoiceAssistantControlBar,
} from "@livekit/components-react";
import "@livekit/components-styles";
import { useCallback, useMemo, useState } from "react";

type ConnectionDetails = {
  serverUrl: string;
  roomName: string;
  participantName: string;
  participantToken: string;
  agentName: string;
  tenantId: string | null;
};

const panelClass =
  "w-full max-w-[52rem] animate-rise-slow rounded-2xl border border-line bg-white/72 p-[clamp(1.25rem,3vw,2rem)] shadow-panel backdrop-blur-[10px]";

function AgentStage() {
  const { state, audioTrack, agentTranscriptions } = useVoiceAssistant();
  const latestTranscript = useMemo(() => {
    if (!agentTranscriptions?.length) return null;
    return agentTranscriptions[agentTranscriptions.length - 1]?.text ?? null;
  }, [agentTranscriptions]);

  return (
    <section aria-live="polite">
      <p className="m-0 text-[0.8rem] tracking-[0.12em] text-ink-soft uppercase">
        Agent state
      </p>
      <p className="mt-1.5 mb-4 font-display text-[1.6rem] font-semibold tracking-[-0.03em] capitalize sm:text-[2rem]">
        {state}
      </p>
      <div className="grid min-h-48 place-items-center rounded-2xl bg-[linear-gradient(180deg,rgba(15,118,110,0.12),rgba(15,118,110,0.04)),var(--color-live-soft)] p-5">
        <BarVisualizer
          state={state}
          barCount={28}
          trackRef={audioTrack}
          className="visualizer h-32 w-full max-w-[34rem]"
          options={{ minHeight: 8 }}
        />
      </div>
      {latestTranscript ? (
        <p className="mt-4 mb-0 min-h-14 text-lg leading-snug">
          {latestTranscript}
        </p>
      ) : (
        <p className="mt-4 mb-0 min-h-14 text-lg leading-snug text-ink-soft">
          Waiting for the agent to speak. Allow microphone access when prompted.
        </p>
      )}
    </section>
  );
}

export function Playground() {
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [details, setDetails] = useState<ConnectionDetails | null>(null);

  const connect = useCallback(async () => {
    setConnecting(true);
    setError(null);
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
      setError(err instanceof Error ? err.message : "Unable to connect");
    } finally {
      setConnecting(false);
    }
  }, []);

  const disconnect = useCallback(() => {
    setDetails(null);
    setError(null);
  }, []);

  if (details) {
    return (
      <div className={panelClass}>
        <div className="mb-5 flex flex-wrap gap-x-4 gap-y-3 text-[0.95rem] text-ink-soft">
          <span className="rounded-full bg-paper-deep px-2.5 py-1.5">
            Room {details.roomName}
          </span>
          <span className="rounded-full bg-paper-deep px-2.5 py-1.5">
            Agent {details.agentName}
          </span>
          {details.tenantId ? (
            <span className="rounded-full bg-paper-deep px-2.5 py-1.5">
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
          onDisconnected={disconnect}
          onError={(err) => setError(err.message)}
          className="grid gap-5"
        >
          <AgentStage />
          <RoomAudioRenderer />
          <div className="controls flex justify-start">
            <VoiceAssistantControlBar controls={{ leave: true }} />
          </div>
        </LiveKitRoom>
        {error ? (
          <p className="mt-4 mb-0 font-semibold text-danger">{error}</p>
        ) : null}
      </div>
    );
  }

  return (
    <div className={panelClass}>
      <p className="mb-6 max-w-xl text-[1.05rem] leading-relaxed text-ink-soft">
        Start a browser session against your local or LiveKit Cloud{" "}
        <code>voice-agent</code> worker. The server mints a short-lived token and
        explicitly dispatches the agent into the room.
      </p>
      <button
        type="button"
        className="cursor-pointer rounded-full border-0 bg-live px-6 py-[0.95rem] font-sans text-base font-bold tracking-wide text-white transition duration-150 ease-out enabled:hover:-translate-y-px enabled:hover:bg-live-deep disabled:cursor-wait disabled:opacity-70"
        onClick={connect}
        disabled={connecting}
      >
        {connecting ? "Connecting…" : "Start call"}
      </button>
      {error ? (
        <p className="mt-4 mb-0 font-semibold text-danger">{error}</p>
      ) : null}
    </div>
  );
}

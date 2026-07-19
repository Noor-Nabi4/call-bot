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

function AgentStage() {
  const { state, audioTrack, agentTranscriptions } = useVoiceAssistant();
  const latestTranscript = useMemo(() => {
    if (!agentTranscriptions?.length) return null;
    return agentTranscriptions[agentTranscriptions.length - 1]?.text ?? null;
  }, [agentTranscriptions]);

  return (
    <section className="stage" aria-live="polite">
      <p className="stage-label">Agent state</p>
      <p className="stage-state">{state}</p>
      <div className="visualizer-shell">
        <BarVisualizer
          state={state}
          barCount={28}
          trackRef={audioTrack}
          className="visualizer"
          options={{ minHeight: 8 }}
        />
      </div>
      {latestTranscript ? (
        <p className="transcript">{latestTranscript}</p>
      ) : (
        <p className="transcript muted">
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
      <div className="session">
        <div className="session-meta">
          <span>Room {details.roomName}</span>
          <span>Agent {details.agentName}</span>
          {details.tenantId ? <span>Tenant {details.tenantId}</span> : null}
        </div>
        <LiveKitRoom
          token={details.participantToken}
          serverUrl={details.serverUrl}
          connect
          audio
          video={false}
          onDisconnected={disconnect}
          onError={(err) => setError(err.message)}
          className="room"
        >
          <AgentStage />
          <RoomAudioRenderer />
          <div className="controls">
            <VoiceAssistantControlBar controls={{ leave: true }} />
          </div>
        </LiveKitRoom>
        {error ? <p className="error">{error}</p> : null}
      </div>
    );
  }

  return (
    <div className="connect-panel">
      <p className="connect-copy">
        Start a browser session against your local or LiveKit Cloud{" "}
        <code>voice-agent</code> worker. The server mints a short-lived token and
        explicitly dispatches the agent into the room.
      </p>
      <button
        type="button"
        className="connect-button"
        onClick={connect}
        disabled={connecting}
      >
        {connecting ? "Connecting…" : "Start call"}
      </button>
      {error ? <p className="error">{error}</p> : null}
    </div>
  );
}

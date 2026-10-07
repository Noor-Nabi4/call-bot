"use client";

import { useEffect, useRef, useState } from "react";
import {
  getCallIntelligence,
  getCallRecording,
  getCallTranscript,
  reanalyzeCall,
  type CallIntelligence,
  type CallRecording,
  type CallTranscript,
} from "@/lib/api/call-intelligence";
import { ApiError } from "@/lib/api/client";
import { Button, StatusPill } from "@/components/ui";

function formatMs(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function IntelCard({
  label,
  value,
}: {
  label: string;
  value: string | null | undefined;
}) {
  return (
    <div className="rounded-lg border border-border bg-surface-muted/40 px-3 py-2">
      <div className="text-[11px] font-medium uppercase tracking-wide text-text-muted">
        {label}
      </div>
      <div className="mt-1 text-sm text-text-primary">
        {value && value.trim() ? value : "—"}
      </div>
    </div>
  );
}

export function CallIntelligencePanel({ callId }: { callId: string }) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [recording, setRecording] = useState<CallRecording | null>(null);
  const [transcript, setTranscript] = useState<CallTranscript | null>(null);
  const [intel, setIntel] = useState<CallIntelligence | null>(null);
  const [recError, setRecError] = useState<string | null>(null);
  const [txError, setTxError] = useState<string | null>(null);
  const [intelError, setIntelError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [reanalyzing, setReanalyzing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setRecording(null);
    setTranscript(null);
    setIntel(null);
    setRecError(null);
    setTxError(null);
    setIntelError(null);

    async function load() {
      const results = await Promise.allSettled([
        getCallRecording(callId),
        getCallTranscript(callId),
        getCallIntelligence(callId),
      ]);
      if (cancelled) return;

      const [recR, txR, intelR] = results;
      if (recR.status === "fulfilled") {
        setRecording(recR.value.recording);
      } else {
        const err = recR.reason;
        if (err instanceof ApiError && err.status === 403) {
          setRecError("No permission to view recordings");
        } else if (err instanceof ApiError && err.status === 404) {
          setRecError(null);
        } else {
          setRecError("Recording unavailable");
        }
      }
      if (txR.status === "fulfilled") {
        setTranscript(txR.value.transcript);
      } else {
        const err = txR.reason;
        if (err instanceof ApiError && err.status === 403) {
          setTxError("No permission to view transcripts");
        } else if (!(err instanceof ApiError && err.status === 404)) {
          setTxError("Transcript unavailable");
        }
      }
      if (intelR.status === "fulfilled") {
        setIntel(intelR.value.intelligence);
      } else {
        const err = intelR.reason;
        if (err instanceof ApiError && err.status === 403) {
          setIntelError("No permission to view intelligence");
        } else if (!(err instanceof ApiError && err.status === 404)) {
          setIntelError("Intelligence unavailable");
        }
      }
      setLoading(false);
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [callId]);

  function seekTo(ms: number) {
    const el = audioRef.current;
    if (!el) return;
    el.currentTime = ms / 1000;
    void el.play().catch(() => undefined);
  }

  async function onReanalyze() {
    setReanalyzing(true);
    try {
      await reanalyzeCall(callId);
      setIntel((prev) =>
        prev
          ? { ...prev, analysis_status: "PENDING" }
          : prev,
      );
    } catch {
      /* toast handled by parent if needed */
    } finally {
      setReanalyzing(false);
    }
  }

  if (loading) {
    return (
      <p className="text-sm text-text-muted">Loading call intelligence…</p>
    );
  }

  return (
    <div className="space-y-5 border-t border-border pt-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">Call Intelligence</h3>
        {intel ? (
          <StatusPill status={intel.analysis_status.toLowerCase()} />
        ) : null}
      </div>

      {/* Overview chips */}
      {intel && intel.analysis_status === "COMPLETED" ? (
        <div className="flex flex-wrap gap-2 text-xs">
          {intel.classification ? (
            <span className="rounded-md border border-border px-2 py-1">
              {intel.classification.replace(/_/g, " ")}
              {intel.classification_confidence != null
                ? ` · ${Math.round(intel.classification_confidence * 100)}%`
                : ""}
            </span>
          ) : null}
          {intel.sentiment ? (
            <span className="rounded-md border border-border px-2 py-1">
              Sentiment: {intel.sentiment}
            </span>
          ) : null}
        </div>
      ) : null}

      {/* Recording */}
      <section className="space-y-2">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
          Recording
        </h4>
        {recError ? (
          <p className="text-sm text-text-secondary">{recError}</p>
        ) : recording?.download_url ? (
          <div className="space-y-2">
            <audio
              ref={audioRef}
              controls
              preload="metadata"
              src={recording.download_url}
              className="w-full"
            />
            {recording.duration_ms != null ? (
              <p className="text-xs text-text-muted">
                Duration {formatMs(recording.duration_ms)}
              </p>
            ) : null}
          </div>
        ) : (
          <p className="text-sm text-text-secondary">No recording available</p>
        )}
      </section>

      {/* Transcript */}
      <section className="space-y-2">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
          Transcript
        </h4>
        {txError ? (
          <p className="text-sm text-text-secondary">{txError}</p>
        ) : transcript?.status === "COMPLETED" && transcript.segments?.length ? (
          <ul className="max-h-56 space-y-2 overflow-y-auto text-sm">
            {transcript.segments.map((seg) => (
              <li key={seg.id} className="flex gap-2">
                <button
                  type="button"
                  className="shrink-0 font-mono text-xs text-brand hover:underline"
                  onClick={() => seekTo(seg.start_ms)}
                >
                  {formatMs(seg.start_ms)}
                </button>
                <div>
                  <span className="mr-1 text-xs font-medium text-text-muted">
                    {seg.speaker}
                  </span>
                  <span className="text-text-primary">{seg.text}</span>
                </div>
              </li>
            ))}
          </ul>
        ) : transcript ? (
          <p className="text-sm text-text-secondary">
            Transcript {transcript.status.toLowerCase()}
            {transcript.last_error ? `: ${transcript.last_error}` : ""}
          </p>
        ) : (
          <p className="text-sm text-text-secondary">No transcript yet</p>
        )}
      </section>

      {/* AI Summary */}
      <section className="space-y-2">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
            AI Summary
          </h4>
          <Button
            type="button"
            size="sm"
            variant="secondary"
            disabled={reanalyzing}
            onClick={() => void onReanalyze()}
          >
            {reanalyzing ? "Queuing…" : "Reanalyze"}
          </Button>
        </div>
        {intelError ? (
          <p className="text-sm text-text-secondary">{intelError}</p>
        ) : intel?.analysis_status === "COMPLETED" ? (
          <div className="grid gap-2 sm:grid-cols-2">
            <IntelCard label="Intent" value={intel.intent} />
            <IntelCard label="Sentiment" value={intel.sentiment} />
            <IntelCard label="Problem" value={intel.problem} />
            <IntelCard label="Outcome" value={intel.outcome} />
            <IntelCard
              label="Appointment status"
              value={intel.appointment_status}
            />
            <IntelCard label="Follow-up" value={intel.follow_up} />
            {intel.important_notes?.length ? (
              <div className="sm:col-span-2">
                <IntelCard
                  label="Important notes"
                  value={intel.important_notes.join(" · ")}
                />
              </div>
            ) : null}
          </div>
        ) : intel ? (
          <p className="text-sm text-text-secondary">
            Analysis {intel.analysis_status.toLowerCase()}
            {intel.last_error ? `: ${intel.last_error}` : ""}
          </p>
        ) : (
          <p className="text-sm text-text-secondary">No analysis yet</p>
        )}
      </section>
    </div>
  );
}

"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { PhoneCall } from "lucide-react";
import { AppShell } from "@/components/shell";
import { formatWhen, listCalls } from "@/lib/api";
import { useAuth } from "@/lib/use-auth";
import { errors, liveCalls as copy } from "@/lib/ops-copy";
import { safeUserError } from "@/lib/safe-error";
import type { Call } from "@/types";
import {
  DataTable,
  EmptyState,
  ErrorState,
  LoadingSkeleton,
  PageHeader,
  StatusPill,
  type DataTableColumn,
} from "@/components/ui";

const POLL_MS = 5_000;
const POLL_HIDDEN_MS = 30_000;

function formatElapsed(seconds?: number | null): string {
  if (seconds == null || seconds < 0) return "—";
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (mins > 0) return `${mins}m ${secs}s`;
  return `${secs}s`;
}

function liveElapsedSeconds(call: Call, nowMs: number): number | null {
  if (call.started_at && !call.ended_at) {
    return Math.max(
      0,
      Math.floor((nowMs - new Date(call.started_at).getTime()) / 1000),
    );
  }
  return call.elapsed_seconds ?? null;
}

export default function LiveCallsPage() {
  const { user, loading } = useAuth({ roles: ["admin", "dispatcher"] });
  const [rows, setRows] = useState<Call[]>([]);
  const [fetching, setFetching] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nowMs, setNowMs] = useState(() => Date.now());
  const inFlight = useRef(false);

  const load = useCallback(async (soft = false) => {
    if (inFlight.current) return;
    inFlight.current = true;
    if (soft) setRefreshing(true);
    try {
      const data = await listCalls({ status: "active", limit: 100 });
      setRows(data.calls || []);
      setError(null);
    } catch (e) {
      setError(safeUserError(e, errors.loadFailed));
    } finally {
      inFlight.current = false;
      setFetching(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    if (!user) return;
    void load(false);
  }, [user, load]);

  useEffect(() => {
    if (!user) return;
    let timeoutId = 0;
    const tick = () => {
      void load(true);
      const ms =
        document.visibilityState === "hidden" ? POLL_HIDDEN_MS : POLL_MS;
      timeoutId = window.setTimeout(tick, ms);
    };
    const ms =
      document.visibilityState === "hidden" ? POLL_HIDDEN_MS : POLL_MS;
    timeoutId = window.setTimeout(tick, ms);
    const onVis = () => {
      window.clearTimeout(timeoutId);
      const next =
        document.visibilityState === "hidden" ? POLL_HIDDEN_MS : POLL_MS;
      timeoutId = window.setTimeout(tick, next);
    };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      window.clearTimeout(timeoutId);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [user, load]);

  useEffect(() => {
    if (!user || rows.length === 0) return;
    const id = window.setInterval(() => setNowMs(Date.now()), 1_000);
    return () => window.clearInterval(id);
  }, [user, rows.length]);

  const columns: DataTableColumn<Call>[] = useMemo(
    () => [
      {
        id: "status",
        header: "Status",
        cell: (c) => <StatusPill status={c.status} />,
        className: "w-28",
      },
      {
        id: "caller",
        header: "Caller",
        cell: (c) => (
          <span className="font-mono text-xs">{c.caller_number || "—"}</span>
        ),
        mono: true,
      },
      {
        id: "called",
        header: "Called",
        cell: (c) => (
          <span className="font-mono text-xs">{c.called_number || "—"}</span>
        ),
        mono: true,
      },
      {
        id: "started",
        header: "Started",
        cell: (c) => (
          <span className="text-text-secondary">{formatWhen(c.started_at)}</span>
        ),
      },
      {
        id: "elapsed",
        header: copy.elapsed,
        cell: (c) => (
          <span className="font-mono text-xs">
            {formatElapsed(liveElapsedSeconds(c, nowMs))}
          </span>
        ),
        className: "w-24",
      },
      {
        id: "handoff",
        header: "Flags",
        cell: (c) =>
          c.handoff_requested ? (
            <span className="text-xs text-amber-700">{copy.handoff}</span>
          ) : (
            <span className="text-xs text-text-muted">—</span>
          ),
      },
    ],
    [nowMs],
  );

  if (loading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  return (
    <AppShell user={user}>
      <PageHeader
        title={copy.title}
        description={copy.description}
        actions={
          <div className="flex items-center gap-3">
            {refreshing ? (
              <span className="text-xs text-text-muted">{copy.refreshing}</span>
            ) : null}
            <Link
              href="/calls"
              className="text-sm font-medium text-brand hover:underline"
            >
              {copy.history}
            </Link>
          </div>
        }
      />

      {error ? (
        <ErrorState message={error} onRetry={() => void load(false)} />
      ) : null}

      {!error && fetching ? <LoadingSkeleton rows={4} /> : null}

      {!error && !fetching ? (
        <DataTable
          columns={columns}
          rows={rows}
          empty={
            <EmptyState
              icon={<PhoneCall className="size-8" />}
              title={copy.empty}
              description={copy.emptyHint}
            />
          }
        />
      ) : null}
    </AppShell>
  );
}

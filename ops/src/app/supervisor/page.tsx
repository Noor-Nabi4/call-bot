"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { PhoneCall, Shield } from "lucide-react";
import { AppShell } from "@/components/shell";
import {
  formatWhen,
  getSupervisorSnapshot,
  type SupervisorSnapshot,
} from "@/lib/api";
import { useAuth } from "@/lib/use-auth";
import { errors, supervisor as copy } from "@/lib/copy";
import { safeUserError } from "@/lib/safe-error";
import type { Call } from "@/types";
import {
  DataTable,
  EmptyState,
  ErrorState,
  LoadingSkeleton,
  MetricSummary,
  PageHeader,
  StatusPill,
  Surface,
  type DataTableColumn,
} from "@/components/ui";

const POLL_MS = 8_000;
const POLL_HIDDEN_MS = 45_000;

function formatDuration(seconds: number): string {
  if (!seconds || seconds <= 0) return "0s";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (m <= 0) return `${s}s`;
  return `${m}m ${s}s`;
}

function callColumns(showEnded: boolean): DataTableColumn<Call>[] {
  const cols: DataTableColumn<Call>[] = [
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
      header: "Line",
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
  ];
  if (showEnded) {
    cols.push({
      id: "ended",
      header: "Ended",
      cell: (c) => (
        <span className="text-text-secondary">{formatWhen(c.ended_at)}</span>
      ),
    });
  } else {
    cols.push({
      id: "elapsed",
      header: "Elapsed",
      cell: (c) => (
        <span className="font-mono text-xs">
          {formatDuration(c.elapsed_seconds || 0)}
        </span>
      ),
      className: "w-24",
    });
  }
  cols.push({
    id: "flags",
    header: "Flags",
    cell: (c) =>
      c.handoff_requested ? (
        <span className="text-xs text-amber-700">Handoff</span>
      ) : (
        <span className="text-xs text-text-muted">—</span>
      ),
  });
  return cols;
}

export default function SupervisorPage() {
  const { user, loading } = useAuth({ roles: ["admin", "dispatcher"] });
  const [snapshot, setSnapshot] = useState<SupervisorSnapshot | null>(null);
  const [fetching, setFetching] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef(false);

  const load = useCallback(async (soft = false) => {
    if (inFlight.current) return;
    inFlight.current = true;
    if (soft) setRefreshing(true);
    try {
      const data = await getSupervisorSnapshot({ recent_limit: 15 });
      setSnapshot(data.snapshot);
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
    timeoutId = window.setTimeout(
      tick,
      document.visibilityState === "hidden" ? POLL_HIDDEN_MS : POLL_MS,
    );
    const onVis = () => {
      window.clearTimeout(timeoutId);
      timeoutId = window.setTimeout(
        tick,
        document.visibilityState === "hidden" ? POLL_HIDDEN_MS : POLL_MS,
      );
    };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      window.clearTimeout(timeoutId);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [user, load]);

  if (loading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={8} />
      </div>
    );
  }

  const summary = snapshot?.summary;

  return (
    <AppShell user={user}>
      <PageHeader
        title={copy.title}
        description={copy.description}
        actions={
          <div className="flex flex-wrap items-center gap-3">
            {refreshing ? (
              <span className="text-xs text-text-muted">{copy.refreshing}</span>
            ) : null}
            <Link
              href="/live"
              className="text-sm font-medium text-brand hover:underline"
            >
              {copy.openLive}
            </Link>
            <Link
              href="/metrics"
              className="text-sm font-medium text-brand hover:underline"
            >
              {copy.openMetrics}
            </Link>
          </div>
        }
      />

      {error ? (
        <ErrorState message={error} onRetry={() => void load(false)} />
      ) : null}

      {fetching && !snapshot ? <LoadingSkeleton rows={6} /> : null}

      {snapshot && summary ? (
        <div className="space-y-6">
          <MetricSummary
            items={[
              { label: copy.active, value: summary.calls_active },
              { label: copy.handoffsOpen, value: summary.handoffs_open },
              { label: copy.callsToday, value: summary.calls_today },
              { label: copy.handoffsToday, value: summary.handoffs_today },
              {
                label: copy.avgDuration,
                value: formatDuration(summary.avg_call_duration_seconds),
              },
            ]}
          />

          <Surface className="p-4">
            <h2 className="mb-3 text-sm font-semibold text-text-primary">
              {copy.attention}
            </h2>
            {snapshot.attention.length === 0 ? (
              <EmptyState
                icon={<Shield className="size-8" />}
                title={copy.attentionEmpty}
                className="py-8"
              />
            ) : (
              <DataTable
                columns={callColumns(false)}
                rows={snapshot.attention}
              />
            )}
          </Surface>

          <Surface className="p-4">
            <h2 className="mb-3 text-sm font-semibold text-text-primary">
              {copy.live}
            </h2>
            <DataTable
              columns={callColumns(false)}
              rows={snapshot.active_calls}
              empty={
                <EmptyState
                  icon={<PhoneCall className="size-8" />}
                  title={copy.liveEmpty}
                  className="py-8"
                />
              }
            />
          </Surface>

          <Surface className="p-4">
            <h2 className="mb-3 text-sm font-semibold text-text-primary">
              {copy.recent}
            </h2>
            <DataTable
              columns={callColumns(true)}
              rows={snapshot.recent_calls}
              empty={
                <EmptyState
                  icon={<PhoneCall className="size-8" />}
                  title={copy.recentEmpty}
                  className="py-8"
                />
              }
            />
          </Surface>
        </div>
      ) : null}
    </AppShell>
  );
}

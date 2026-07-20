"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { BarChart3 } from "lucide-react";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import { errors, metrics as copy } from "@/lib/copy";
import { safeUserError } from "@/lib/safe-error";
import {
  EmptyState,
  ErrorState,
  FilterBar,
  LoadingSkeleton,
  MetricSummary,
  PageHeader,
  Select,
  StatusPill,
  Surface,
} from "@/components/ui";

const API =
  process.env.NEXT_PUBLIC_PLATFORM_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

type DayPoint = { date: string; calls: number };

type Metrics = {
  window_days: number;
  calls: number;
  calls_ended: number;
  calls_active: number;
  voice_minutes: number;
  avg_call_duration_seconds: number;
  avg_quality_score?: number | null;
  quality_reviews?: number;
  handoffs_requested: number;
  handoff_rate: number;
  appointment_booked_calls: number;
  appointments: number;
  jobs: number;
  jobs_completed: number;
  customers: number;
  jobs_by_status: Record<string, number>;
  disconnect_reasons: Record<string, number>;
  calls_by_day: DayPoint[];
};

const DAY_OPTIONS = [7, 30, 90];

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`, { credentials: "include" });
  if (!res.ok) throw new Error(errors.loadFailed);
  return res.json();
}

function formatDuration(seconds: number): string {
  if (!seconds || seconds <= 0) return "0s";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (m <= 0) return `${s}s`;
  return `${m}m ${s}s`;
}

export default function MetricsPage() {
  const { user, loading } = useAuth({ roles: ["admin", "dispatcher"] });
  const [days, setDays] = useState(30);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (windowDays: number) => {
    const data = await getJson<{ metrics: Metrics }>(
      `/api/admin/metrics?days=${windowDays}`,
    );
    setMetrics(data.metrics);
  }, []);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      load(days)
        .catch((e) => setError(safeUserError(e, errors.loadFailed)))
        .finally(() => {
          if (!cancelled) setFetching(false);
        });
    });
    return () => {
      cancelled = true;
    };
  }, [user, days, load]);

  const statusEntries = metrics?.jobs_by_status
    ? Object.entries(metrics.jobs_by_status).sort((a, b) => b[1] - a[1])
    : [];
  const maxStatusCount = statusEntries.reduce((m, [, c]) => Math.max(m, c), 1);

  const disconnectEntries = useMemo(() => {
    if (!metrics?.disconnect_reasons) return [];
    return Object.entries(metrics.disconnect_reasons).sort(
      (a, b) => b[1] - a[1],
    );
  }, [metrics]);
  const maxDisconnect = disconnectEntries.reduce(
    (m, [, c]) => Math.max(m, c),
    1,
  );

  const maxDayCalls = useMemo(() => {
    if (!metrics?.calls_by_day?.length) return 1;
    return Math.max(1, ...metrics.calls_by_day.map((d) => d.calls));
  }, [metrics]);

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
          <FilterBar className="mb-0 border-0 bg-transparent p-0">
            <Select
              className="w-auto"
              value={String(days)}
              onChange={(e) => {
                setFetching(true);
                setDays(Number(e.target.value));
              }}
              aria-label="Date range"
            >
              {DAY_OPTIONS.map((d) => (
                <option key={d} value={d}>
                  Last {d} days
                </option>
              ))}
            </Select>
          </FilterBar>
        }
      />

      {error ? (
        <ErrorState
          className="mb-4"
          message={error}
          onRetry={() => {
            setError(null);
            setFetching(true);
            load(days)
              .catch((e) => setError(safeUserError(e, errors.loadFailed)))
              .finally(() => setFetching(false));
          }}
        />
      ) : null}

      {fetching ? (
        <LoadingSkeleton rows={5} />
      ) : !metrics ? (
        <EmptyState
          icon={<BarChart3 className="size-8" />}
          title={copy.empty}
          description={copy.emptyHint}
        />
      ) : (
        <div className="space-y-4">
          <MetricSummary
            items={[
              { label: copy.calls, value: metrics.calls },
              { label: copy.voiceMinutes, value: metrics.voice_minutes },
              {
                label: copy.avgDuration,
                value: formatDuration(metrics.avg_call_duration_seconds),
              },
              { label: copy.handoffs, value: metrics.handoffs_requested },
              {
                label: copy.avgQuality,
                value:
                  metrics.avg_quality_score != null
                    ? `${metrics.avg_quality_score}/5`
                    : "—",
                hint:
                  metrics.quality_reviews != null
                    ? `${metrics.quality_reviews} reviews`
                    : undefined,
              },
              { label: copy.appointments, value: metrics.appointments },
              { label: copy.jobs, value: metrics.jobs },
            ]}
          />

          <div className="grid gap-4 lg:grid-cols-2">
            <Surface className="p-4">
              <h2 className="text-sm font-semibold text-text-primary">
                {copy.callsByDay}
              </h2>
              <p className="mt-0.5 text-xs text-text-muted">
                Last {metrics.window_days} days · {metrics.calls_ended} ended ·{" "}
                {metrics.calls_active} active now
              </p>
              {metrics.calls_by_day.length === 0 ? (
                <p className="mt-4 text-sm text-text-muted">{copy.noCallVolume}</p>
              ) : (
                <div className="mt-4 flex h-32 items-end gap-0.5">
                  {metrics.calls_by_day.map((point) => (
                    <div
                      key={point.date}
                      className="flex min-w-0 flex-1 flex-col items-center justify-end"
                      title={`${point.date}: ${point.calls}`}
                    >
                      <div
                        className="w-full rounded-t bg-brand/80"
                        style={{
                          height: `${Math.max(
                            point.calls > 0 ? 8 : 2,
                            (point.calls / maxDayCalls) * 100,
                          )}%`,
                        }}
                      />
                    </div>
                  ))}
                </div>
              )}
            </Surface>

            <Surface className="p-4">
              <h2 className="text-sm font-semibold text-text-primary">
                {copy.callOutcomes}
              </h2>
              <p className="mt-0.5 text-xs text-text-muted">
                Handoff rate{" "}
                {(metrics.handoff_rate * 100).toFixed(1)}% · Booked from call{" "}
                {metrics.appointment_booked_calls}
              </p>
              {disconnectEntries.length === 0 ? (
                <p className="mt-4 text-sm text-text-muted">
                  {copy.noDisconnect}
                </p>
              ) : (
                <ul className="mt-4 space-y-3">
                  {disconnectEntries.map(([reason, count]) => (
                    <li key={reason} className="flex items-center gap-3">
                      <span className="w-36 shrink-0 truncate font-mono text-xs text-text-secondary">
                        {reason}
                      </span>
                      <div className="h-2 min-w-0 flex-1 overflow-hidden rounded-full bg-surface-muted">
                        <div
                          className="h-full rounded-full bg-brand transition-all"
                          style={{
                            width: `${Math.max(4, (count / maxDisconnect) * 100)}%`,
                          }}
                        />
                      </div>
                      <span className="w-8 shrink-0 text-right font-mono text-xs text-text-secondary">
                        {count}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Surface>
          </div>

          <Surface className="p-4">
            <h2 className="text-sm font-semibold text-text-primary">
              {copy.jobsByStatus}
            </h2>
            <p className="mt-0.5 text-xs text-text-muted">
              Last {metrics.window_days} days · {metrics.jobs_completed}{" "}
              completed · {metrics.customers} customers
            </p>
            {statusEntries.length === 0 ? (
              <p className="mt-4 text-sm text-text-muted">No job status data.</p>
            ) : (
              <ul className="mt-4 space-y-3">
                {statusEntries.map(([status, count]) => (
                  <li key={status} className="flex items-center gap-3">
                    <StatusPill status={status} className="shrink-0" />
                    <div className="h-2 min-w-0 flex-1 overflow-hidden rounded-full bg-surface-muted">
                      <div
                        className="h-full rounded-full bg-brand transition-all"
                        style={{
                          width: `${Math.max(4, (count / maxStatusCount) * 100)}%`,
                        }}
                      />
                    </div>
                    <span className="w-8 shrink-0 text-right font-mono text-xs text-text-secondary">
                      {count}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Surface>
        </div>
      )}
    </AppShell>
  );
}

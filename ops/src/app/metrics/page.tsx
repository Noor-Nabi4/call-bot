"use client";

import { useCallback, useEffect, useState } from "react";
import { BarChart3 } from "lucide-react";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
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

type Metrics = {
  window_days: number;
  calls: number;
  appointments: number;
  jobs: number;
  jobs_completed: number;
  customers: number;
  jobs_by_status: Record<string, number>;
};

const DAY_OPTIONS = [7, 30, 90];

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`, { credentials: "include" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
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
        .catch((e) => setError(e instanceof Error ? e.message : "Load failed"))
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
        title="Metrics"
        description="Call, appointment, and job activity for this tenant."
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
              .catch((e) => setError(e.message))
              .finally(() => setFetching(false));
          }}
        />
      ) : null}

      {fetching ? (
        <LoadingSkeleton rows={5} />
      ) : !metrics ? (
        <EmptyState
          icon={<BarChart3 className="size-8" />}
          title="No metrics available"
          description="Metrics will appear once activity is recorded."
        />
      ) : (
        <>
          <MetricSummary
            items={[
              { label: "Calls", value: metrics.calls },
              { label: "Appointments", value: metrics.appointments },
              { label: "Jobs", value: metrics.jobs },
              { label: "Completed", value: metrics.jobs_completed },
              { label: "Customers", value: metrics.customers },
            ]}
          />

          <Surface className="p-4">
            <h2 className="text-sm font-semibold text-text-primary">
              Jobs by status
            </h2>
            <p className="mt-0.5 text-xs text-text-muted">
              Last {metrics.window_days} days
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
        </>
      )}
    </AppShell>
  );
}

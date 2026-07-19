"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";

const API =
  process.env.NEXT_PUBLIC_PLATFORM_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`, { credentials: "include" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export default function MetricsPage() {
  const { user, loading } = useAuth({ roles: ["admin", "dispatcher"] });
  const [metrics, setMetrics] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    if (!user) return;
    getJson<{ metrics: Record<string, unknown> }>("/api/admin/metrics?days=30")
      .then((d) => setMetrics(d.metrics))
      .catch(() => undefined);
  }, [user]);

  if (loading || !user) return <p className="p-6 text-ink-muted">Loading…</p>;

  return (
    <AppShell user={user}>
      <h2 className="text-xl font-semibold">Call & job metrics</h2>
      <p className="text-sm text-ink-muted">Last 30 days for this tenant.</p>
      {metrics && (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 md:grid-cols-3">
          {["calls", "appointments", "jobs", "jobs_completed", "customers"].map(
            (k) => (
              <div
                key={k}
                className="rounded border border-line bg-panel p-4"
              >
                <p className="text-xs uppercase text-ink-muted">{k.replace("_", " ")}</p>
                <p className="mt-1 text-2xl font-semibold font-mono">
                  {String(metrics[k] ?? 0)}
                </p>
              </div>
            ),
          )}
        </div>
      )}
      {metrics?.jobs_by_status && (
        <pre className="mt-4 rounded border border-line bg-panel p-3 text-xs font-mono">
          {JSON.stringify(metrics.jobs_by_status, null, 2)}
        </pre>
      )}
    </AppShell>
  );
}

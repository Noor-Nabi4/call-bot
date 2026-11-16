"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import { listHandoffs, type HandoffRow } from "@/lib/api/handoffs";
import { safeUserError } from "@/lib/safe-error";
import { errors } from "@/lib/ops-copy";
import {
  EmptyState,
  ErrorState,
  ForbiddenState,
  LoadingSkeleton,
  PageHeader,
  Select,
  StatusPill,
} from "@/components/ui";

const VIEWS = [
  { key: "QUEUE", label: "Queue" },
  { key: "ASSIGNED", label: "Assigned" },
  { key: "EMERGENCY", label: "Emergency" },
  { key: "COMPLETED", label: "Completed" },
] as const;

export default function HandoffsQueuePage() {
  const { user, loading, forbidden } = useAuth({ permission: "handoffs.read" });
  const [view, setView] = useState<string>("QUEUE");
  const [items, setItems] = useState<HandoffRow[]>([]);
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setFetching(true);
    setError(null);
    try {
      const res = await listHandoffs({ status: view, limit: 100 });
      setItems(res.items || []);
    } catch (e) {
      setError(safeUserError(e, errors.loadFailed));
    } finally {
      setFetching(false);
    }
  }, [view]);

  useEffect(() => {
    if (!user) return;
    void load();
  }, [user, load]);

  if (loading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={6} />
      </div>
    );
  }
  if (forbidden) {
    return (
      <AppShell user={user}>
        <ForbiddenState />
      </AppShell>
    );
  }

  return (
    <AppShell user={user}>
      <PageHeader
        title="Human Handoffs"
        description="AI → human queue with full call intelligence context."
        actions={
          <Select value={view} onChange={(e) => setView(e.target.value)}>
            {VIEWS.map((v) => (
              <option key={v.key} value={v.key}>
                {v.label}
              </option>
            ))}
          </Select>
        }
      />

      {error ? (
        <ErrorState className="mb-4" message={error} onRetry={() => void load()} />
      ) : null}

      {fetching ? (
        <LoadingSkeleton rows={5} />
      ) : items.length === 0 ? (
        <EmptyState
          title="No handoffs"
          description="When AI or staff request a human, items appear here."
        />
      ) : (
        <ul className="divide-y divide-border rounded-lg border border-border">
          {items.map((h) => (
            <li key={h.id}>
              <Link
                href={`/crm/handoffs/${h.id}`}
                className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 hover:bg-surface-muted/50"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2 text-sm">
                    <StatusPill status={h.status.toLowerCase()} />
                    <span className="font-medium text-text-primary">
                      {h.priority}
                    </span>
                    <span className="text-text-muted">{h.channel}</span>
                    {h.department ? (
                      <span className="text-text-secondary">{h.department}</span>
                    ) : null}
                  </div>
                  <p className="mt-1 truncate text-sm text-text-secondary">
                    {h.summary || h.intent || "No summary"}
                  </p>
                </div>
                <span className="shrink-0 text-xs text-text-muted">
                  {h.requested_at
                    ? new Date(h.requested_at).toLocaleString()
                    : ""}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </AppShell>
  );
}

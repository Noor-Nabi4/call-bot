"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Phone } from "lucide-react";
import { AppShell } from "@/components/shell";
import { formatWhen } from "@/lib/api";
import { useAuth } from "@/lib/use-auth";
import { calls as copy, errors } from "@/lib/copy";
import { safeUserError } from "@/lib/safe-error";
import {
  DataTable,
  DetailDrawer,
  EmptyState,
  ErrorState,
  LoadingSkeleton,
  PageHeader,
  SearchInput,
  StatusPill,
  Timeline,
  type DataTableColumn,
} from "@/components/ui";

const API =
  process.env.NEXT_PUBLIC_PLATFORM_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

type Call = {
  id: string;
  room_name: string;
  status: string;
  caller_number?: string | null;
  called_number?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
  customer_id?: string | null;
};

function formatDuration(
  started?: string | null,
  ended?: string | null,
): string {
  if (!started || !ended) return "—";
  const ms = new Date(ended).getTime() - new Date(started).getTime();
  if (ms < 0) return "—";
  const totalSec = Math.floor(ms / 1000);
  const mins = Math.floor(totalSec / 60);
  const secs = totalSec % 60;
  if (mins > 0) return `${mins}m ${secs}s`;
  return `${secs}s`;
}

function CallsWorkspace() {
  const searchParams = useSearchParams();
  const statusFilter = (searchParams.get("status") || "").toLowerCase().trim();
  const { user, loading } = useAuth({ roles: ["admin", "dispatcher"] });
  const [rows, setRows] = useState<Call[]>([]);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Call | null>(null);
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const res = await fetch(`${API}/api/admin/calls`, { credentials: "include" });
    if (!res.ok) throw new Error(errors.loadFailed);
    const data = await res.json();
    setRows(data.calls || []);
  }, []);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      load()
        .catch((e) => setError(safeUserError(e, errors.loadFailed)))
        .finally(() => {
          if (!cancelled) setFetching(false);
        });
    });
    return () => {
      cancelled = true;
    };
  }, [user, load]);

  const filtered = useMemo(() => {
    return rows.filter((c) => {
      if (statusFilter && c.status.toLowerCase() !== statusFilter) return false;
      if (!search.trim()) return true;
      const q = search.toLowerCase();
      return (
        c.status.toLowerCase().includes(q) ||
        (c.caller_number || "").includes(q) ||
        (c.called_number || "").includes(q)
      );
    });
  }, [rows, search, statusFilter]);

  const columns: DataTableColumn<Call>[] = [
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
      id: "duration",
      header: "Duration",
      cell: (c) => (
        <span className="font-mono text-xs">
          {formatDuration(c.started_at, c.ended_at)}
        </span>
      ),
      className: "w-24",
    },
  ];

  const timelineItems = selected
    ? [
        ...(selected.started_at
          ? [
              {
                id: "started",
                title: "Call started",
                detail: "Call connected",
                time: formatWhen(selected.started_at),
                tone: "success" as const,
              },
            ]
          : []),
        ...(selected.ended_at
          ? [
              {
                id: "ended",
                title: "Call ended",
                detail: `Duration: ${formatDuration(selected.started_at, selected.ended_at)}`,
                time: formatWhen(selected.ended_at),
                tone: "default" as const,
              },
            ]
          : []),
      ]
    : [];

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
          <SearchInput
            className="w-full sm:w-64"
            placeholder="Search calls…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onClear={() => setSearch("")}
          />
        }
      />

      {statusFilter ? (
        <div className="mb-4 flex flex-wrap items-center gap-2 text-sm">
          <span className="rounded-lg border border-border bg-surface-muted px-2.5 py-1 text-text-secondary">
            Status:{" "}
            <span className="font-medium text-text-primary">
              {statusFilter.replace(/_/g, " ")}
            </span>
          </span>
          <Link href="/calls" className="text-xs text-brand hover:underline">
            Clear status filter
          </Link>
        </div>
      ) : null}

      {error ? (
        <ErrorState
          className="mb-4"
          message={error}
          onRetry={() => {
            setError(null);
            setFetching(true);
            load()
              .catch((e) => setError(safeUserError(e, errors.loadFailed)))
              .finally(() => setFetching(false));
          }}
        />
      ) : null}

      {fetching ? (
        <LoadingSkeleton rows={5} />
      ) : (
        <DataTable
          columns={columns}
          rows={filtered}
          onRowClick={setSelected}
          selectedId={selected?.id}
          empty={
            <EmptyState
              icon={<Phone className="size-8" />}
              title={
                search || statusFilter ? "No matching calls" : copy.empty
              }
              description={copy.emptyHint}
            />
          }
        />
      )}

      <DetailDrawer
        open={!!selected}
        onClose={() => setSelected(null)}
        title={copy.detailTitle}
        description={
          selected
            ? `${formatWhen(selected.started_at)} · ${selected.status.replace(/_/g, " ")}`
            : undefined
        }
      >
        {selected ? (
          <div className="space-y-5">
            <dl className="grid gap-3 text-sm">
              <div>
                <dt className="text-xs font-medium text-text-muted uppercase">Status</dt>
                <dd className="mt-1">
                  <StatusPill status={selected.status} />
                </dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-text-muted uppercase">Caller</dt>
                <dd className="mt-1 font-mono">{selected.caller_number || "—"}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-text-muted uppercase">Called</dt>
                <dd className="mt-1 font-mono">{selected.called_number || "—"}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-text-muted uppercase">Duration</dt>
                <dd className="mt-1 font-mono">
                  {formatDuration(selected.started_at, selected.ended_at)}
                </dd>
              </div>
            </dl>
            <div>
              <h3 className="mb-3 text-sm font-semibold">Timeline</h3>
              <Timeline items={timelineItems} />
            </div>
          </div>
        ) : null}
      </DetailDrawer>
    </AppShell>
  );
}

export default function CallsPage() {
  return (
    <Suspense
      fallback={
        <div className="p-6">
          <LoadingSkeleton rows={6} />
        </div>
      }
    >
      <CallsWorkspace />
    </Suspense>
  );
}

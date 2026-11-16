"use client";

import { FormEvent, Suspense, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Phone } from "lucide-react";
import { AppShell } from "@/components/shell";
import { formatWhen, listCalls, reviewCallQuality } from "@/lib/api";
import { useAuth } from "@/lib/use-auth";
import { calls as copy, errors } from "@/lib/ops-copy";
import { safeUserError } from "@/lib/safe-error";
import type { Call } from "@/types";
import {
  Button,
  DataTable,
  DetailDrawer,
  EmptyState,
  ErrorState,
  ForbiddenState,
  Field,
  LoadingSkeleton,
  PageHeader,
  SearchInput,
  Select,
  StatusPill,
  Textarea,
  Timeline,
  useToast,
  type DataTableColumn,
} from "@/components/ui";
import { CallIntelligencePanel } from "@/components/calls/CallIntelligencePanel";

const DISPOSITIONS = [
  "resolved",
  "callback",
  "transferred",
  "spam",
  "no_answer",
  "abandoned",
  "other",
] as const;

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
  const { user, loading, forbidden } = useAuth({ permission: "calls.read" });
  const toast = useToast();
  const [rows, setRows] = useState<Call[]>([]);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Call | null>(null);
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [score, setScore] = useState("5");
  const [disposition, setDisposition] = useState("resolved");
  const [notes, setNotes] = useState("");
  const [savingQuality, setSavingQuality] = useState(false);

  const load = useCallback(async () => {
    const data = await listCalls({ limit: 100 });
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

  useEffect(() => {
    if (!selected) return;
    setScore(selected.quality_score != null ? String(selected.quality_score) : "5");
    setDisposition(selected.disposition_code || "resolved");
    setNotes(selected.quality_notes || "");
  }, [selected]);

  const filtered = useMemo(() => {
    return rows.filter((c) => {
      if (statusFilter && c.status.toLowerCase() !== statusFilter) return false;
      if (!search.trim()) return true;
      const q = search.toLowerCase();
      return (
        c.status.toLowerCase().includes(q) ||
        (c.caller_number || "").includes(q) ||
        (c.called_number || "").includes(q) ||
        (c.disposition_code || "").includes(q)
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
    {
      id: "qa",
      header: "QA",
      cell: (c) =>
        c.quality_score != null ? (
          <span className="font-mono text-xs">{c.quality_score}/5</span>
        ) : (
          <span className="text-xs text-text-muted">—</span>
        ),
      className: "w-16",
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
        ...(selected.quality_reviewed_at
          ? [
              {
                id: "qa",
                title: "Quality reviewed",
                detail: `Score ${selected.quality_score}/5 · ${selected.disposition_code || "—"}`,
                time: formatWhen(selected.quality_reviewed_at),
                tone: "default" as const,
              },
            ]
          : []),
      ]
    : [];

  async function onSaveQuality(e: FormEvent) {
    e.preventDefault();
    if (!selected || selected.status === "active" || !selected.ended_at) return;
    setSavingQuality(true);
    try {
      const data = await reviewCallQuality(selected.id, {
        quality_score: Number(score),
        disposition_code: disposition,
        quality_notes: notes.trim() || null,
      });
      setSelected(data.call);
      setRows((prev) =>
        prev.map((c) => (c.id === data.call.id ? data.call : c)),
      );
      toast.push(copy.qualitySaved, "success");
    } catch (err) {
      toast.push(safeUserError(err, errors.saveFailed), "error");
    } finally {
      setSavingQuality(false);
    }
  }

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
        title={copy.title}
        description={copy.description}
        actions={
          <div className="flex flex-wrap items-center gap-3">
            <Link
              href="/live"
              className="text-sm font-medium text-brand hover:underline"
            >
              {copy.liveLink}
            </Link>
            <SearchInput
              className="w-full sm:w-64"
              placeholder="Search calls…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onClear={() => setSearch("")}
            />
          </div>
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
                <dt className="text-xs font-medium text-text-muted uppercase">
                  Status
                </dt>
                <dd className="mt-1">
                  <StatusPill status={selected.status} />
                </dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-text-muted uppercase">
                  Caller
                </dt>
                <dd className="mt-1 font-mono">
                  {selected.caller_number || "—"}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-text-muted uppercase">
                  Called
                </dt>
                <dd className="mt-1 font-mono">
                  {selected.called_number || "—"}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-text-muted uppercase">
                  Duration
                </dt>
                <dd className="mt-1 font-mono">
                  {formatDuration(selected.started_at, selected.ended_at)}
                </dd>
              </div>
            </dl>
            <div>
              <h3 className="mb-3 text-sm font-semibold">Timeline</h3>
              <Timeline items={timelineItems} />
            </div>
            <CallIntelligencePanel callId={selected.id} />
            {selected.status !== "active" && selected.ended_at ? (
              <form className="space-y-3 border-t border-border pt-4" onSubmit={onSaveQuality}>
                <h3 className="text-sm font-semibold">{copy.quality}</h3>
                <Field label={copy.score}>
                  <Select
                    value={score}
                    onChange={(e) => setScore(e.target.value)}
                  >
                    {[1, 2, 3, 4, 5].map((n) => (
                      <option key={n} value={String(n)}>
                        {n}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label={copy.disposition}>
                  <Select
                    value={disposition}
                    onChange={(e) => setDisposition(e.target.value)}
                  >
                    {DISPOSITIONS.map((d) => (
                      <option key={d} value={d}>
                        {d.replace(/_/g, " ")}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label={copy.notes}>
                  <Textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    rows={3}
                    maxLength={2000}
                  />
                </Field>
                <Button type="submit" size="sm" disabled={savingQuality}>
                  {savingQuality ? copy.savingQuality : copy.saveQuality}
                </Button>
              </form>
            ) : null}
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

"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import {
  assignDispatchJob,
  getDispatchBoard,
  getDispatchEvents,
  type DispatchBoard,
  type DispatchJobCard,
  type DispatchTechnician,
} from "@/lib/api/dispatch-crm";
import { isBookingConflict, ApiError } from "@/lib/api/client";
import { hasPermission } from "@/lib/permissions";
import { useAuth } from "@/lib/use-auth";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  EmptyState,
  ErrorState,
  Field,
  Input,
  LoadingSkeleton,
  PageHeader,
  StatusPill,
} from "@/components/ui";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function JobCard({
  job,
  draggable,
  onDragStart,
}: {
  job: DispatchJobCard;
  draggable: boolean;
  onDragStart: (jobId: string) => void;
}) {
  return (
    <div
      draggable={draggable}
      onDragStart={() => onDragStart(job.id)}
      className="cursor-grab rounded border border-border bg-surface px-2 py-2 text-sm active:cursor-grabbing"
    >
      <div className="flex items-center justify-between gap-2">
        <Link
          href={`/crm/jobs/${job.id}`}
          className="font-medium underline-offset-2 hover:underline"
        >
          {job.job_number}
        </Link>
        <StatusPill status={job.status} />
      </div>
      <p className="text-text-muted">
        {job.customer?.display_name || job.customer?.name || "Customer"}
      </p>
      <p className="text-xs">
        {job.scheduled_starts_at
          ? new Date(job.scheduled_starts_at).toLocaleString()
          : "Unscheduled"}
        {job.eta ? ` · ETA ${new Date(job.eta).toLocaleTimeString()}` : ""}
      </p>
      <p className="text-xs text-text-muted">{job.priority}</p>
    </div>
  );
}

export default function CrmDispatchBoardPage() {
  const { user, loading: authLoading } = useAuth({
    permission: "dispatch.read",
  });
  const [date, setDate] = useState(todayIso);
  const [q, setQ] = useState("");
  const [board, setBoard] = useState<DispatchBoard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [dragJobId, setDragJobId] = useState<string | null>(null);
  const [lastEventId, setLastEventId] = useState<string | null>(null);
  const canAssign = !!user && hasPermission(user, "jobs.assign");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getDispatchBoard({
        date,
        q: q || undefined,
        limit: 500,
      });
      setBoard(data);
    } catch (err) {
      setError(safeUserError(err));
      setBoard(null);
    } finally {
      setLoading(false);
    }
  }, [date, q]);

  useEffect(() => {
    if (!authLoading && user) void load();
  }, [authLoading, user, load]);

  // Poll dispatch events; reconcile by refreshing the board on relevant types.
  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const res = await getDispatchEvents({
          after_id: lastEventId || undefined,
          limit: 50,
        });
        if (cancelled || !res.events.length) return;
        const last = res.events[res.events.length - 1];
        setLastEventId(last.id);
        const relevant = res.events.some((e) =>
          [
            "JOB_ASSIGNED",
            "JOB_UNASSIGNED",
            "JOB_REASSIGNED",
            "JOB_STATUS_CHANGED",
            "TECHNICIAN_STATUS_CHANGED",
            "ETA_CHANGED",
          ].includes(e.event_type),
        );
        if (relevant) await load();
      } catch {
        /* polling is best-effort */
      }
    };
    const id = window.setInterval(() => void tick(), 8000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [user, lastEventId, load]);

  async function onSearch(e: FormEvent) {
    e.preventDefault();
    await load();
  }

  async function dropOnTechnician(tech: DispatchTechnician | null) {
    if (!dragJobId || busy || !canAssign) return;
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      await assignDispatchJob(dragJobId, {
        technician_id: tech ? tech.id : null,
      });
      await load();
    } catch (err) {
      if (err instanceof ApiError || isBookingConflict(err)) {
        setInfo(
          "Assignment conflict — board refreshed. Another dispatcher may have updated this job.",
        );
        await load();
      } else {
        setError(safeUserError(err));
        await load();
      }
    } finally {
      setBusy(false);
      setDragJobId(null);
    }
  }

  if (authLoading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton />
      </div>
    );
  }

  const byTech = new Map<string, DispatchJobCard[]>();
  for (const j of board?.assigned_jobs || []) {
    const tid = j.assigned_technician_id || "";
    if (!byTech.has(tid)) byTech.set(tid, []);
    byTech.get(tid)!.push(j);
  }

  return (
    <AppShell user={user}>
      <PageHeader
        title="Dispatch board"
        description="Technician columns over authoritative Jobs. Drag to assign — server revalidates eligibility."
        actions={
          <Link
            href="/dispatch"
            className="text-sm underline-offset-2 hover:underline"
          >
            Legacy kanban
          </Link>
        }
      />

      <form
        onSubmit={onSearch}
        className="mb-4 flex flex-wrap items-end gap-3"
      >
        <Field label="Date">
          <Input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
        </Field>
        <Field label="Search">
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Job #, customer…"
          />
        </Field>
        <Button type="submit" disabled={busy || loading}>
          {loading ? "Loading…" : "Refresh"}
        </Button>
      </form>

      {error ? <ErrorState message={error} onRetry={() => void load()} /> : null}
      {info ? (
        <p className="mb-3 text-sm" role="status">
          {info}
        </p>
      ) : null}

      {loading && !board ? <LoadingSkeleton /> : null}

      {board && board.technicians.length === 0 ? (
        <EmptyState
          title="No technicians"
          description="Create an active technician before dispatching jobs."
        />
      ) : null}

      {board ? (
        <div className="space-y-4">
          <p className="text-sm text-text-muted">
            {board.date} · {board.timezone} · generated{" "}
            {new Date(board.generated_at).toLocaleTimeString()}
          </p>

          <div className="flex gap-3 overflow-x-auto pb-4">
            <section
              className="min-w-[220px] max-w-[260px] shrink-0 rounded-md border border-border p-2"
              onDragOver={(e) => e.preventDefault()}
              onDrop={() => void dropOnTechnician(null)}
            >
              <h2 className="mb-2 text-sm font-medium">Unassigned</h2>
              <div className="space-y-2">
                {board.unassigned_jobs.length === 0 ? (
                  <p className="text-xs text-text-muted">No unassigned jobs</p>
                ) : (
                  board.unassigned_jobs.map((j) => (
                    <JobCard
                      key={j.id}
                      job={j}
                      draggable={canAssign && !busy}
                      onDragStart={setDragJobId}
                    />
                  ))
                )}
              </div>
            </section>

            {board.technicians.map((tech) => (
              <section
                key={tech.id}
                className="min-w-[220px] max-w-[260px] shrink-0 rounded-md border border-border p-2"
                onDragOver={(e) => e.preventDefault()}
                onDrop={() => void dropOnTechnician(tech)}
              >
                <div className="mb-2 flex items-start justify-between gap-2">
                  <div>
                    <h2 className="text-sm font-medium">{tech.display_name}</h2>
                    <p className="text-xs text-text-muted">{tech.status}</p>
                  </div>
                  <Link
                    href={`/crm/dispatch/technicians/${tech.id}`}
                    className="text-xs underline-offset-2 hover:underline"
                  >
                    Detail
                  </Link>
                </div>
                <div className="space-y-2">
                  {(byTech.get(tech.id) || []).map((j) => (
                    <JobCard
                      key={j.id}
                      job={j}
                      draggable={canAssign && !busy}
                      onDragStart={setDragJobId}
                    />
                  ))}
                </div>
              </section>
            ))}
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}

"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { AppShell, StatusPill } from "@/components/shell";
import {
  addNote,
  formatWhen,
  getJob,
  transitionJob,
  updateChecklist,
  type Job,
} from "@/lib/api";
import { useAuth } from "@/lib/use-auth";

export default function JobDetailPage() {
  const params = useParams<{ id: string }>();
  const { user, loading } = useAuth();
  const [job, setJob] = useState<Job | null>(null);
  const [note, setNote] = useState("");
  const [completionNotes, setCompletionNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const data = await getJob(params.id);
    setJob(data.job);
  }, [params.id]);

  useEffect(() => {
    if (!user) return;
    refresh().catch((e) => setError(e.message));
  }, [user, refresh]);

  if (loading || !user) {
    return <p className="p-6 text-ink-muted">Loading…</p>;
  }
  if (!job) {
    return (
      <AppShell user={user}>
        <p className="text-ink-muted">{error || "Loading job…"}</p>
      </AppShell>
    );
  }

  async function onToggle(itemId: string) {
    if (!job) return;
    const checklist = job.checklist.map((c) =>
      c.id === itemId ? { ...c, done: !c.done } : c,
    );
    const updated = await updateChecklist(job.id, checklist);
    setJob(updated.job);
  }

  async function onNote(e: FormEvent) {
    e.preventDefault();
    if (!job) return;
    const updated = await addNote(job.id, note);
    setJob(updated.job);
    setNote("");
  }

  async function onTransition(status: string) {
    setError(null);
    try {
      const updated = await transitionJob(
        job!.id,
        status,
        status === "completed" ? completionNotes : undefined,
      );
      setJob(updated.job);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed");
    }
  }

  const home = user.role === "technician" ? "/tech" : "/board";

  return (
    <AppShell user={user}>
      <Link href={home} className="text-sm">
        ← Back
      </Link>
      <div className="mt-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-mono text-sm text-ink-muted">{job.reference_code}</p>
          <h2 className="text-2xl font-semibold">{job.service_type}</h2>
          <p className="text-ink-muted">
            {job.customer?.name}
            {job.customer?.address ? ` · ${job.customer.address}` : ""}
          </p>
          <p className="text-sm text-ink-muted">
            {formatWhen(job.scheduled_starts_at)}
          </p>
        </div>
        <StatusPill status={job.status} />
      </div>

      {error && (
        <p className="mt-3 text-sm text-danger" role="alert">
          {error}
        </p>
      )}

      <section className="mt-6 grid gap-4 md:grid-cols-2">
        <div className="rounded border border-line bg-panel p-4">
          <h3 className="font-semibold">Checklist</h3>
          <ul className="mt-3 space-y-2">
            {job.checklist.map((item) => (
              <li key={item.id}>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={item.done}
                    onChange={() => onToggle(item.id)}
                  />
                  {item.label}
                </label>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded border border-line bg-panel p-4">
          <h3 className="font-semibold">Status actions</h3>
          <div className="mt-3 flex flex-wrap gap-2">
            {user.role !== "technician" && job.status === "scheduled" && (
              <button
                type="button"
                className="rounded bg-accent px-3 py-1.5 text-sm text-white"
                onClick={() => onTransition("dispatched")}
              >
                Dispatch
              </button>
            )}
            {(job.status === "dispatched") && (
                <button
                  type="button"
                  className="rounded bg-accent px-3 py-1.5 text-sm text-white"
                  onClick={() => onTransition("in_progress")}
                >
                  {user.role === "technician" ? "Start job" : "Mark in progress"}
                </button>
              )}
            {job.status === "in_progress" && (
              <div className="w-full space-y-2">
                <textarea
                  className="w-full rounded border border-line px-2 py-1.5 text-sm"
                  rows={3}
                  placeholder="Completion notes (required)"
                  value={completionNotes}
                  onChange={(e) => setCompletionNotes(e.target.value)}
                />
                <button
                  type="button"
                  className="rounded bg-ink px-3 py-1.5 text-sm text-white"
                  onClick={() => onTransition("completed")}
                >
                  Complete job
                </button>
              </div>
            )}
            {user.role !== "technician" &&
              !["completed", "canceled"].includes(job.status) && (
                <button
                  type="button"
                  className="rounded border border-danger px-3 py-1.5 text-sm text-danger"
                  onClick={() => onTransition("canceled")}
                >
                  Cancel
                </button>
              )}
          </div>
          {job.completion_notes && (
            <p className="mt-3 text-sm text-ink-muted">
              Completion: {job.completion_notes}
            </p>
          )}
        </div>
      </section>

      <section className="mt-6 rounded border border-line bg-panel p-4">
        <h3 className="font-semibold">Notes</h3>
        <ul className="mt-3 space-y-2 text-sm">
          {(job.notes || []).map((n) => (
            <li key={n.id} className="border-b border-line pb-2">
              <p>{n.body}</p>
              <p className="text-xs text-ink-muted">
                {n.author_name || "System"} · {formatWhen(n.created_at)}
              </p>
            </li>
          ))}
          {(job.notes || []).length === 0 && (
            <li className="text-ink-muted">No notes yet.</li>
          )}
        </ul>
        <form onSubmit={onNote} className="mt-3 flex gap-2">
          <input
            className="flex-1 rounded border border-line px-2 py-1.5 text-sm"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Add a note"
            required
          />
          <button
            type="submit"
            className="rounded bg-ink px-3 py-1.5 text-sm text-white"
          >
            Add
          </button>
        </form>
      </section>
    </AppShell>
  );
}

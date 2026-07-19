"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { ArrowLeft } from "lucide-react";
import { AppShell } from "@/components/shell";
import {
  addNote,
  formatWhen,
  getJob,
  transitionJob,
  updateChecklist,
  type Job,
} from "@/lib/api";
import { cn } from "@/lib/cn";
import { useAuth } from "@/lib/use-auth";
import { errors } from "@/lib/copy";
import { safeUserError } from "@/lib/safe-error";
import {
  Breadcrumbs,
  Button,
  ErrorState,
  Field,
  Input,
  LoadingSkeleton,
  PageHeader,
  StatusPill,
  Surface,
  Textarea,
} from "@/components/ui";

export default function JobDetailPage() {
  const params = useParams<{ id: string }>();
  const { user, loading } = useAuth();
  const [job, setJob] = useState<Job | null>(null);
  const [note, setNote] = useState("");
  const [completionNotes, setCompletionNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fetching, setFetching] = useState(true);
  const [noteBusy, setNoteBusy] = useState(false);

  const isTech = user?.role === "technician";
  const btnSize = isTech ? "lg" : "md";

  const refresh = useCallback(async () => {
    const data = await getJob(params.id);
    setJob(data.job);
  }, [params.id]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      refresh()
        .catch((e) => setError(safeUserError(e, errors.loadFailed)))
        .finally(() => {
          if (!cancelled) setFetching(false);
        });
    });
    return () => {
      cancelled = true;
    };
  }, [user, refresh]);

  if (loading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  if (fetching && !job) {
    return (
      <AppShell user={user}>
        <LoadingSkeleton rows={6} />
      </AppShell>
    );
  }

  if (!job) {
    return (
      <AppShell user={user}>
        <ErrorState
          title="Job not found"
          message={error || "Unable to load this job."}
          onRetry={() => {
            setFetching(true);
            refresh()
              .catch((e) => setError(safeUserError(e, errors.loadFailed)))
              .finally(() => setFetching(false));
          }}
        />
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
    setNoteBusy(true);
    try {
      const updated = await addNote(job.id, note);
      setJob(updated.job);
      setNote("");
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    } finally {
      setNoteBusy(false);
    }
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
      setError(safeUserError(e, errors.saveFailed));
    }
  }

  const home = isTech ? "/tech" : "/dispatch";

  return (
    <AppShell user={user}>
      <Breadcrumbs
        items={[
          { label: isTech ? "My jobs" : "Dispatch", href: home },
          { label: job.reference_code },
        ]}
      />

      <PageHeader
        className="mt-3"
        eyebrow={job.reference_code}
        title={job.service_type}
        description={[
          job.customer?.name,
          job.customer?.address,
          formatWhen(job.scheduled_starts_at),
        ]
          .filter(Boolean)
          .join(" · ")}
        actions={<StatusPill status={job.status} />}
      />

      <Link
        href={home}
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-text-secondary hover:text-brand"
      >
        <ArrowLeft className="size-3.5" aria-hidden />
        Back
      </Link>

      {error ? (
        <ErrorState className="mb-4" message={error} onRetry={() => setError(null)} />
      ) : null}

      <div className="grid gap-4 md:grid-cols-2">
        <Surface className="p-4">
          <h3 className="text-sm font-semibold text-text-primary">Checklist</h3>
          <ul className={cn("mt-3 space-y-2", isTech && "space-y-3")}>
            {job.checklist.map((item) => (
              <li key={item.id}>
                <label
                  className={cn(
                    "flex items-center gap-3 text-sm",
                    isTech && "min-h-11 rounded-md border border-border px-3 py-2",
                  )}
                >
                  <input
                    type="checkbox"
                    className={cn(isTech && "size-5")}
                    checked={item.done}
                    onChange={() => onToggle(item.id)}
                  />
                  <span className={item.done ? "text-text-muted line-through" : undefined}>
                    {item.label}
                  </span>
                </label>
              </li>
            ))}
            {job.checklist.length === 0 ? (
              <li className="text-sm text-text-muted">No checklist items.</li>
            ) : null}
          </ul>
        </Surface>

        <Surface className="p-4">
          <h3 className="text-sm font-semibold text-text-primary">Status actions</h3>
          <div className={cn("mt-3 flex flex-wrap gap-2", isTech && "flex-col")}>
            {!isTech && job.status === "scheduled" && (
              <Button size={btnSize} onClick={() => onTransition("dispatched")}>
                Dispatch
              </Button>
            )}
            {job.status === "dispatched" && (
              <Button size={btnSize} onClick={() => onTransition("in_progress")}>
                {isTech ? "Start job" : "Mark in progress"}
              </Button>
            )}
            {job.status === "in_progress" && (
              <div className="w-full space-y-2">
                <Field label="Completion notes" hint="Required to complete">
                  <Textarea
                    rows={isTech ? 4 : 3}
                    placeholder="Completion notes (required)"
                    value={completionNotes}
                    onChange={(e) => setCompletionNotes(e.target.value)}
                  />
                </Field>
                <Button
                  variant="ink"
                  size={btnSize}
                  className={isTech ? "w-full" : undefined}
                  onClick={() => onTransition("completed")}
                >
                  Complete job
                </Button>
              </div>
            )}
            {!isTech && !["completed", "canceled"].includes(job.status) && (
              <Button
                variant="danger"
                size={btnSize}
                onClick={() => onTransition("canceled")}
              >
                Cancel
              </Button>
            )}
          </div>
          {job.completion_notes ? (
            <p className="mt-3 text-sm text-text-secondary">
              Completion: {job.completion_notes}
            </p>
          ) : null}
        </Surface>
      </div>

      <Surface className="mt-4 p-4">
        <h3 className="text-sm font-semibold text-text-primary">Notes</h3>
        <ul className="mt-3 space-y-3 text-sm">
          {(job.notes || []).map((n) => (
            <li key={n.id} className="border-b border-border pb-3 last:border-0">
              <p className="text-text-primary">{n.body}</p>
              <p className="mt-1 text-xs text-text-muted">
                {n.author_name || "System"} · {formatWhen(n.created_at)}
              </p>
            </li>
          ))}
          {(job.notes || []).length === 0 && (
            <li className="text-text-muted">No notes yet.</li>
          )}
        </ul>
        <form
          onSubmit={onNote}
          className={cn("mt-4 flex gap-2", isTech && "flex-col sm:flex-row")}
        >
          <Input
            className={cn("flex-1", isTech && "h-11")}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Add a note"
            required
          />
          <Button
            type="submit"
            variant="ink"
            size={btnSize}
            disabled={noteBusy}
            className={isTech ? "w-full sm:w-auto" : undefined}
          >
            {noteBusy ? "Adding…" : "Add"}
          </Button>
        </form>
      </Surface>
    </AppShell>
  );
}

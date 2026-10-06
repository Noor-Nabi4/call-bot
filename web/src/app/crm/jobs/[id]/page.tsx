"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import { listTechnicians } from "@/lib/api/technicians";
import type { Technician } from "@/types";
import {
  archiveCrmJob,
  archiveCrmJobAttachment,
  archiveCrmJobNote,
  assignCrmJob,
  createCrmJobNote,
  getCrmJob,
  getCrmJobHistory,
  JOB_CANCELLABLE,
  JOB_FORWARD_TRANSITIONS,
  listCrmJobAttachments,
  listCrmJobNotes,
  restoreCrmJob,
  transitionCrmJob,
  uploadCrmJobAttachment,
  type JobAttachmentRow,
  type JobNoteRow,
  type JobRow,
  type JobStatusHistoryRow,
} from "@/lib/api/jobs-crm";
import { useAuth } from "@/lib/use-auth";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  ErrorState,
  Field,
  Input,
  LoadingSkeleton,
  PageHeader,
  Select,
  StatusPill,
  Textarea,
} from "@/components/ui";

export default function CrmJobDetailPage() {
  const params = useParams();
  const id = String(params.id || "");
  const { user, loading: authLoading } = useAuth();
  const [job, setJob] = useState<JobRow | null>(null);
  const [history, setHistory] = useState<JobStatusHistoryRow[]>([]);
  const [notes, setNotes] = useState<JobNoteRow[]>([]);
  const [attachments, setAttachments] = useState<JobAttachmentRow[]>([]);
  const [technicians, setTechnicians] = useState<Technician[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [noteBody, setNoteBody] = useState("");
  const [completionNotes, setCompletionNotes] = useState("");
  const [cancelReason, setCancelReason] = useState("");

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const [row, hist, notesRes, attachRes, techRes] = await Promise.all([
        getCrmJob(id),
        getCrmJobHistory(id),
        listCrmJobNotes(id),
        listCrmJobAttachments(id),
        listTechnicians().catch(() => ({ technicians: [] as Technician[] })),
      ]);
      setJob(row);
      setHistory(hist.history);
      setNotes(notesRes.notes);
      setAttachments(attachRes.attachments);
      setTechnicians(techRes.technicians);
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (!authLoading && user) void load();
  }, [authLoading, user, load]);

  async function runAction(fn: () => Promise<JobRow>) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await fn();
      setJob(updated);
      const hist = await getCrmJobHistory(id);
      setHistory(hist.history);
    } catch (err) {
      setError(safeUserError(err));
      await load();
    } finally {
      setBusy(false);
    }
  }

  async function onAddNote(e: FormEvent) {
    e.preventDefault();
    if (!noteBody.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const note = await createCrmJobNote(id, noteBody.trim());
      setNotes((prev) => [note, ...prev]);
      setNoteBody("");
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setBusy(false);
    }
  }

  async function onArchiveNote(noteId: string) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const archived = await archiveCrmJobNote(id, noteId);
      setNotes((prev) => prev.filter((n) => n.id !== archived.id));
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setBusy(false);
    }
  }

  async function onUploadFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || busy) return;
    setBusy(true);
    setError(null);
    try {
      const attachment = await uploadCrmJobAttachment(id, file);
      setAttachments((prev) => [attachment, ...prev]);
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setBusy(false);
    }
  }

  async function onArchiveAttachment(attachmentId: string) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const archived = await archiveCrmJobAttachment(id, attachmentId);
      setAttachments((prev) => prev.filter((a) => a.id !== archived.id));
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setBusy(false);
    }
  }

  if (authLoading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton />
      </div>
    );
  }

  const forwards = job ? JOB_FORWARD_TRANSITIONS[job.status] || [] : [];
  const canCancel = job ? JOB_CANCELLABLE.has(job.status) : false;
  const requiresCompletionNotes = forwards.includes("COMPLETED");

  return (
    <AppShell user={user}>
      <PageHeader
        title={job?.job_number || "Job"}
        description="Lifecycle transitions go through the transition API — status is not freely editable."
      />
      <p className="mb-4 text-sm">
        <Link href="/crm/jobs" className="underline-offset-2 hover:underline">
          Back to jobs
        </Link>
      </p>
      {error ? <ErrorState message={error} /> : null}
      {loading || !job ? (
        <LoadingSkeleton />
      ) : (
        <div className="space-y-8">
          <section className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <StatusPill status={job.status} />
              <span className="text-sm text-neutral-600">
                {job.customer?.display_name || job.customer?.name || job.customer_id}
              </span>
              <span className="text-sm text-neutral-500">
                {job.reference_code}
              </span>
            </div>
            <dl className="grid gap-2 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-neutral-500">Service</dt>
                <dd>{job.service_type}</dd>
              </div>
              <div>
                <dt className="text-neutral-500">Priority</dt>
                <dd>{job.priority}</dd>
              </div>
              <div>
                <dt className="text-neutral-500">Technician</dt>
                <dd>{job.assigned_technician?.display_name || "Unassigned"}</dd>
              </div>
              <div>
                <dt className="text-neutral-500">Scheduled</dt>
                <dd>
                  {job.scheduled_starts_at
                    ? new Date(job.scheduled_starts_at).toLocaleString()
                    : "—"}
                </dd>
              </div>
              <div className="sm:col-span-2">
                <dt className="text-neutral-500">Description</dt>
                <dd>{job.description || "—"}</dd>
              </div>
              {job.completion_notes ? (
                <div className="sm:col-span-2">
                  <dt className="text-neutral-500">Completion notes</dt>
                  <dd>{job.completion_notes}</dd>
                </div>
              ) : null}
            </dl>
          </section>

          <section className="space-y-2">
            <h2 className="text-base font-medium">Assign technician</h2>
            <div className="flex flex-wrap items-center gap-2">
              <Select
                value={job.assigned_technician_id || ""}
                disabled={busy}
                onChange={(e) =>
                  void runAction(() =>
                    assignCrmJob(id, e.target.value || null)
                  )
                }
                aria-label="Assign technician"
                className="max-w-xs"
              >
                <option value="">Unassigned</option>
                {technicians.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.display_name}
                  </option>
                ))}
              </Select>
            </div>
          </section>

          <section className="space-y-2">
            <h2 className="text-base font-medium">Actions</h2>
            {requiresCompletionNotes ? (
              <Field label="Completion notes" hint="Required to mark completed">
                <Textarea
                  rows={3}
                  value={completionNotes}
                  onChange={(e) => setCompletionNotes(e.target.value)}
                  placeholder="Describe the completed work…"
                />
              </Field>
            ) : null}
            <div className="flex flex-wrap gap-2">
              {forwards.map((to) => (
                <Button
                  key={to}
                  type="button"
                  disabled={
                    busy || (to === "COMPLETED" && !completionNotes.trim())
                  }
                  onClick={() =>
                    void runAction(() =>
                      transitionCrmJob(id, {
                        to_status: to,
                        completion_notes:
                          to === "COMPLETED" ? completionNotes : undefined,
                      })
                    )
                  }
                >
                  Mark {to.replace(/_/g, " ").toLowerCase()}
                </Button>
              ))}
              {canCancel ? (
                <Button
                  type="button"
                  variant="secondary"
                  disabled={busy}
                  onClick={() =>
                    void runAction(() =>
                      transitionCrmJob(id, {
                        to_status: "CANCELLED",
                        reason: cancelReason || "Cancelled from CRM",
                      })
                    )
                  }
                >
                  Cancel
                </Button>
              ) : null}
              {job.archived_at ? (
                <Button
                  type="button"
                  variant="secondary"
                  disabled={busy}
                  onClick={() => void runAction(() => restoreCrmJob(id))}
                >
                  Restore
                </Button>
              ) : (
                <Button
                  type="button"
                  variant="secondary"
                  disabled={busy}
                  onClick={() => void runAction(() => archiveCrmJob(id))}
                >
                  Archive
                </Button>
              )}
            </div>
            {canCancel ? (
              <Input
                className="max-w-sm"
                placeholder="Cancellation reason (optional)"
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
              />
            ) : null}
          </section>

          <section className="space-y-2">
            <h2 className="text-base font-medium">Notes</h2>
            <form onSubmit={onAddNote} className="flex gap-2">
              <Input
                className="flex-1"
                value={noteBody}
                onChange={(e) => setNoteBody(e.target.value)}
                placeholder="Add a note"
                required
              />
              <Button type="submit" disabled={busy}>
                Add
              </Button>
            </form>
            <ul className="space-y-2 text-sm">
              {notes.map((n) => (
                <li
                  key={n.id}
                  className="flex items-start justify-between gap-2 border-b border-neutral-100 py-2"
                >
                  <div>
                    <p>{n.body}</p>
                    <p className="text-neutral-500">
                      {n.author_name || "System"}
                      {n.created_at
                        ? ` · ${new Date(n.created_at).toLocaleString()}`
                        : ""}
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={busy}
                    onClick={() => void onArchiveNote(n.id)}
                  >
                    Remove
                  </Button>
                </li>
              ))}
              {notes.length === 0 ? (
                <li className="text-neutral-500">No notes yet.</li>
              ) : null}
            </ul>
          </section>

          <section className="space-y-2">
            <h2 className="text-base font-medium">Attachments</h2>
            <input
              type="file"
              onChange={(e) => void onUploadFile(e)}
              disabled={busy}
              aria-label="Upload attachment"
            />
            <ul className="space-y-2 text-sm">
              {attachments.map((a) => (
                <li
                  key={a.id}
                  className="flex items-center justify-between gap-2 border-b border-neutral-100 py-2"
                >
                  <span>
                    {a.filename}
                    {a.size_bytes
                      ? ` · ${Math.round(a.size_bytes / 1024)} KB`
                      : ""}
                  </span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={busy}
                    onClick={() => void onArchiveAttachment(a.id)}
                  >
                    Remove
                  </Button>
                </li>
              ))}
              {attachments.length === 0 ? (
                <li className="text-neutral-500">No attachments yet.</li>
              ) : null}
            </ul>
          </section>

          <section className="space-y-2">
            <h2 className="text-base font-medium">Status history</h2>
            <ul className="space-y-2 text-sm">
              {history.map((h) => (
                <li key={h.id} className="border-b border-neutral-100 py-2">
                  <span className="font-medium">
                    {h.from_status || "—"} → {h.to_status}
                  </span>
                  {h.reason ? (
                    <span className="text-neutral-600"> · {h.reason}</span>
                  ) : null}
                  <div className="text-neutral-500">
                    {h.changed_by || "system"}
                    {h.created_at
                      ? ` · ${new Date(h.created_at).toLocaleString()}`
                      : ""}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </AppShell>
  );
}

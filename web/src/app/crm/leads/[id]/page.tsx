"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/shell";
import {
  archiveLead,
  archiveLeadNote,
  convertLead,
  createLeadNote,
  getLead,
  listLeadActivities,
  listLeadNotes,
  restoreLead,
  transitionLead,
  updateLead,
  LEAD_PRIORITIES,
  LEAD_SOURCES,
  type LeadActivity,
  type LeadNote,
  type LeadRow,
} from "@/lib/api/leads";
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

export default function LeadDetailPage() {
  const params = useParams();
  const id = String(params.id || "");
  const { user, loading: authLoading } = useAuth();
  const [lead, setLead] = useState<LeadRow | null>(null);
  const [activities, setActivities] = useState<LeadActivity[]>([]);
  const [notes, setNotes] = useState<LeadNote[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [noteBody, setNoteBody] = useState("");
  const [convertName, setConvertName] = useState("");
  const [convertPhone, setConvertPhone] = useState("");

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const [row, acts, noteList] = await Promise.all([
        getLead(id),
        listLeadActivities(id, { limit: 50 }),
        listLeadNotes(id, { limit: 50 }),
      ]);
      setLead(row);
      setActivities(acts.activities);
      setNotes(noteList.notes);
      setConvertName((prev) => prev || row.prospect_name || "");
      setConvertPhone((prev) => prev || row.prospect_phone || "");
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (!authLoading && user) void load();
  }, [authLoading, user, load]);

  async function onTransition(to: string) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await transitionLead(id, to);
      await load();
    } catch (err) {
      setError(safeUserError(err));
      await load();
    } finally {
      setBusy(false);
    }
  }

  async function onSaveMeta(e: FormEvent) {
    e.preventDefault();
    if (!lead) return;
    setBusy(true);
    setError(null);
    try {
      await updateLead(id, {
        title: lead.title,
        description: lead.description,
        source: lead.source,
        priority: lead.priority,
        prospect_name: lead.prospect_name,
        prospect_phone: lead.prospect_phone,
        prospect_email: lead.prospect_email,
        notes: lead.notes,
      });
      await load();
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setBusy(false);
    }
  }

  async function onAddNote(e: FormEvent) {
    e.preventDefault();
    if (!noteBody.trim()) return;
    setBusy(true);
    try {
      await createLeadNote(id, noteBody.trim());
      setNoteBody("");
      await load();
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setBusy(false);
    }
  }

  async function onConvert(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (lead?.customer_id) {
        await convertLead(id, { customer_id: lead.customer_id });
      } else {
        await convertLead(id, {
          create_customer: {
            name: convertName || lead?.title || "Converted lead",
            phone: convertPhone || undefined,
          },
        });
      }
      await load();
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setBusy(false);
    }
  }

  if (authLoading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={8} />
      </div>
    );
  }

  if (loading) {
    return (
      <AppShell user={user}>
        <LoadingSkeleton rows={8} />
      </AppShell>
    );
  }

  if (!lead) {
    return (
      <AppShell user={user}>
        <ErrorState message={error || "Lead not found"} />
        <Link href="/crm/leads">Back to leads</Link>
      </AppShell>
    );
  }

  const next = nextStatuses(lead.status);

  return (
    <AppShell user={user}>
      <PageHeader
        title={lead.title}
        description={`Ref ${lead.reference_code || lead.id.slice(0, 8)}`}
        actions={
          <div className="flex flex-wrap gap-2">
            <Link href="/crm/leads">
              <Button variant="secondary">Back</Button>
            </Link>
            {lead.archived_at ? (
              <Button
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await restoreLead(id);
                    await load();
                  } catch (err) {
                    setError(safeUserError(err));
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Restore
              </Button>
            ) : (
              <Button
                variant="secondary"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await archiveLead(id);
                    await load();
                  } catch (err) {
                    setError(safeUserError(err));
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Archive
              </Button>
            )}
          </div>
        }
      />

      {error ? <ErrorState message={error} /> : null}

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <StatusPill status={lead.status} />
        <span className="text-sm text-zinc-500">{lead.priority}</span>
        <span className="text-sm text-zinc-500">{lead.source}</span>
        {next.map((s) => (
          <Button
            key={s}
            disabled={busy}
            variant="secondary"
            onClick={() => void onTransition(s)}
          >
            Move to {s}
          </Button>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <form onSubmit={onSaveMeta} className="space-y-3 rounded-lg border border-zinc-200 p-4">
          <h2 className="text-sm font-semibold">Lead details</h2>
          <Field label="Title">
            <Input
              value={lead.title}
              onChange={(e) => setLead({ ...lead, title: e.target.value })}
            />
          </Field>
          <Field label="Description">
            <Textarea
              value={lead.description || ""}
              onChange={(e) =>
                setLead({ ...lead, description: e.target.value })
              }
              rows={3}
            />
          </Field>
          <Field label="Source">
            <Select
              value={lead.source}
              onChange={(e) => setLead({ ...lead, source: e.target.value })}
            >
              {LEAD_SOURCES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Priority">
            <Select
              value={lead.priority}
              onChange={(e) => setLead({ ...lead, priority: e.target.value })}
            >
              {LEAD_PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Prospect name">
            <Input
              value={lead.prospect_name || ""}
              onChange={(e) =>
                setLead({ ...lead, prospect_name: e.target.value })
              }
            />
          </Field>
          <Field label="Prospect phone">
            <Input
              value={lead.prospect_phone || ""}
              onChange={(e) =>
                setLead({ ...lead, prospect_phone: e.target.value })
              }
            />
          </Field>
          <Field label="Prospect email">
            <Input
              value={lead.prospect_email || ""}
              onChange={(e) =>
                setLead({ ...lead, prospect_email: e.target.value })
              }
            />
          </Field>
          <Button type="submit" disabled={busy}>
            Save
          </Button>
        </form>

        <div className="space-y-4">
          <div className="rounded-lg border border-zinc-200 p-4">
            <h2 className="mb-2 text-sm font-semibold">Relationships</h2>
            <dl className="space-y-2 text-sm">
              <div>
                <dt className="text-zinc-500">Customer</dt>
                <dd>
                  {lead.customer_id ? (
                    <Link
                      href={`/crm/customers/${lead.customer_id}`}
                      className="underline"
                    >
                      {lead.customer?.display_name ||
                        lead.customer?.name ||
                        lead.customer_id}
                    </Link>
                  ) : (
                    "—"
                  )}
                </dd>
              </div>
              <div>
                <dt className="text-zinc-500">Service</dt>
                <dd>{lead.service?.name || "—"}</dd>
              </div>
              <div>
                <dt className="text-zinc-500">Product</dt>
                <dd>{lead.product?.name || "—"}</dd>
              </div>
              <div>
                <dt className="text-zinc-500">Owner</dt>
                <dd>{lead.owner?.name || "—"}</dd>
              </div>
              <div>
                <dt className="text-zinc-500">Conversion</dt>
                <dd>
                  {lead.converted_at
                    ? `Converted ${new Date(lead.converted_at).toLocaleString()}`
                    : "Not converted"}
                </dd>
              </div>
            </dl>

            {!lead.converted_at && !lead.archived_at ? (
              <form onSubmit={onConvert} className="mt-4 space-y-2">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                  Convert to customer
                </h3>
                {!lead.customer_id ? (
                  <>
                    <Field label="Customer name">
                      <Input
                        value={convertName}
                        onChange={(e) => setConvertName(e.target.value)}
                        required
                      />
                    </Field>
                    <Field label="Phone">
                      <Input
                        value={convertPhone}
                        onChange={(e) => setConvertPhone(e.target.value)}
                      />
                    </Field>
                  </>
                ) : (
                  <p className="text-xs text-zinc-500">
                    Will link to the existing customer on this lead.
                  </p>
                )}
                <Button type="submit" disabled={busy}>
                  Convert
                </Button>
              </form>
            ) : null}
          </div>

          <div className="rounded-lg border border-zinc-200 p-4">
            <h2 className="mb-2 text-sm font-semibold">Notes</h2>
            <form onSubmit={onAddNote} className="mb-3 space-y-2">
              <Textarea
                value={noteBody}
                onChange={(e) => setNoteBody(e.target.value)}
                rows={2}
                placeholder="Add a note…"
              />
              <Button type="submit" disabled={busy || !noteBody.trim()}>
                Add note
              </Button>
            </form>
            <ul className="space-y-2">
              {notes.length === 0 ? (
                <li className="text-sm text-zinc-400">No notes yet</li>
              ) : (
                notes.map((n) => (
                  <li
                    key={n.id}
                    className="rounded border border-zinc-100 p-2 text-sm"
                  >
                    <p>{n.body}</p>
                    <div className="mt-1 flex justify-between text-[10px] text-zinc-400">
                      <span>
                        {n.created_by} ·{" "}
                        {n.created_at
                          ? new Date(n.created_at).toLocaleString()
                          : ""}
                      </span>
                      <button
                        type="button"
                        className="underline"
                        disabled={busy}
                        onClick={async () => {
                          setBusy(true);
                          try {
                            await archiveLeadNote(id, n.id);
                            await load();
                          } catch (err) {
                            setError(safeUserError(err));
                          } finally {
                            setBusy(false);
                          }
                        }}
                      >
                        Archive
                      </button>
                    </div>
                  </li>
                ))
              )}
            </ul>
          </div>

          <div className="rounded-lg border border-zinc-200 p-4">
            <h2 className="mb-2 text-sm font-semibold">Activity</h2>
            <ul className="space-y-2">
              {activities.length === 0 ? (
                <li className="text-sm text-zinc-400">No activity</li>
              ) : (
                activities.map((a) => (
                  <li key={a.id} className="border-b border-zinc-100 pb-2 text-sm">
                    <div className="font-medium">{a.activity_type}</div>
                    <div className="text-xs text-zinc-500">
                      {a.actor || "system"} ·{" "}
                      {a.created_at
                        ? new Date(a.created_at).toLocaleString()
                        : ""}
                    </div>
                  </li>
                ))
              )}
            </ul>
          </div>
        </div>
      </div>
    </AppShell>
  );
}

function nextStatuses(current: string): string[] {
  const map: Record<string, string[]> = {
    NEW: ["QUALIFIED", "LOST"],
    QUALIFIED: ["CONTACTED", "LOST"],
    CONTACTED: ["BOOKED", "LOST"],
    BOOKED: ["WON", "LOST"],
    LOST: ["NEW"],
    WON: [],
  };
  return map[current] || [];
}

"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import {
  acceptHandoff,
  completeHandoff,
  getHandoff,
  rejectHandoff,
  type HandoffRow,
} from "@/lib/api/handoffs";
import { safeUserError } from "@/lib/safe-error";
import { errors } from "@/lib/ops-copy";
import {
  Button,
  ErrorState,
  ForbiddenState,
  LoadingSkeleton,
  PageHeader,
  StatusPill,
  useToast,
} from "@/components/ui";

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-2 border-t border-border pt-4">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
        {title}
      </h3>
      {children}
    </section>
  );
}

export default function HandoffDetailPage() {
  const params = useParams();
  const id = String(params.id || "");
  const { user, loading, forbidden } = useAuth({ permission: "handoffs.read" });
  const toast = useToast();
  const [row, setRow] = useState<HandoffRow | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await getHandoff(id);
      setRow(res.handoff);
    } catch (e) {
      setError(safeUserError(e, errors.loadFailed));
    }
  }, [id]);

  useEffect(() => {
    if (!user || !id) return;
    void load();
  }, [user, id, load]);

  async function run(
    action: "accept" | "reject" | "complete",
  ) {
    setBusy(true);
    try {
      const fn =
        action === "accept"
          ? acceptHandoff
          : action === "reject"
            ? rejectHandoff
            : completeHandoff;
      const res = await fn(id);
      setRow(res.handoff);
      toast.push(
        action === "accept"
          ? "Handoff accepted"
          : action === "reject"
            ? "Returned to queue"
            : "Handoff completed",
        "success",
      );
    } catch (e) {
      toast.push(safeUserError(e, errors.saveFailed), "error");
    } finally {
      setBusy(false);
    }
  }

  if (loading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={8} />
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

  const snap = (row?.context_snapshot || {}) as Record<string, any>;
  const customer = snap.customer as
    | { name?: string; email?: string; id?: string }
    | undefined;
  const jobs = (snap.jobs || []) as Array<{
    id: string;
    job_number?: string;
    status?: string;
  }>;
  const appointments = (snap.appointments || []) as Array<{
    id: string;
    confirmation_code?: string;
    status?: string;
  }>;
  const actions = (snap.ai_actions || []) as Array<{
    action: string;
    created_at?: string;
  }>;
  const transcript = snap.transcript as
    | { full_text?: string; status?: string }
    | undefined;
  const recordingUrl = snap.recording_url as string | undefined;

  return (
    <AppShell user={user}>
      <div className="mb-4">
        <Link href="/crm/handoffs" className="text-sm text-brand hover:underline">
          ← Back to queue
        </Link>
      </div>
      <PageHeader
        title="Handoff detail"
        description="Full context captured when the handoff was created."
        actions={
          row ? (
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                disabled={busy || row.status === "COMPLETED"}
                onClick={() => void run("accept")}
              >
                Accept
              </Button>
              <Button
                size="sm"
                variant="secondary"
                disabled={busy || row.status === "COMPLETED"}
                onClick={() => void run("reject")}
              >
                Reject
              </Button>
              <Button
                size="sm"
                variant="secondary"
                disabled={busy || row.status === "COMPLETED"}
                onClick={() => void run("complete")}
              >
                Complete
              </Button>
            </div>
          ) : null
        }
      />

      {error ? (
        <ErrorState className="mb-4" message={error} onRetry={() => void load()} />
      ) : null}

      {!row ? (
        <LoadingSkeleton rows={6} />
      ) : (
        <div className="mx-auto max-w-3xl space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill status={row.status.toLowerCase()} />
            <span className="text-sm font-medium">{row.priority}</span>
            <span className="text-sm text-text-muted">{row.channel}</span>
            {row.department ? (
              <span className="text-sm text-text-secondary">{row.department}</span>
            ) : null}
          </div>

          <Section title="Transfer reason">
            <p className="text-sm text-text-primary">
              {row.reason.replace(/_/g, " ")}
              {row.summary ? ` — ${row.summary}` : ""}
            </p>
          </Section>

          <Section title="Customer">
            <p className="text-sm">
              {customer?.name || "Unknown"}{" "}
              {customer?.email ? (
                <span className="text-text-muted">· {customer.email}</span>
              ) : null}
            </p>
          </Section>

          <Section title="AI summary">
            <dl className="grid gap-2 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-xs text-text-muted">Intent</dt>
                <dd>{(snap.intent as string) || row.intent || "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-text-muted">Classification</dt>
                <dd>{(snap.classification as string) || "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-text-muted">Sentiment</dt>
                <dd>{(snap.sentiment as string) || "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-text-muted">Emergency</dt>
                <dd>
                  {(snap.emergency as { emergency?: boolean })?.emergency
                    ? "Yes"
                    : "No"}
                </dd>
              </div>
            </dl>
          </Section>

          <Section title="Recording">
            {recordingUrl ? (
              <audio controls preload="metadata" src={recordingUrl} className="w-full" />
            ) : (
              <p className="text-sm text-text-secondary">No recording</p>
            )}
          </Section>

          <Section title="Transcript">
            <p className="max-h-48 overflow-y-auto whitespace-pre-wrap text-sm text-text-primary">
              {transcript?.full_text || "No transcript yet"}
            </p>
          </Section>

          <Section title="Open jobs">
            {jobs.length === 0 ? (
              <p className="text-sm text-text-secondary">None</p>
            ) : (
              <ul className="space-y-1 text-sm">
                {jobs.map((j) => (
                  <li key={j.id}>
                    {j.job_number || j.id.slice(0, 8)} · {j.status}
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section title="Appointments">
            {appointments.length === 0 ? (
              <p className="text-sm text-text-secondary">None</p>
            ) : (
              <ul className="space-y-1 text-sm">
                {appointments.map((a) => (
                  <li key={a.id}>
                    {a.confirmation_code || a.id.slice(0, 8)} · {a.status}
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section title="AI actions already performed">
            {actions.length === 0 ? (
              <p className="text-sm text-text-secondary">None recorded</p>
            ) : (
              <ul className="space-y-1 text-sm">
                {actions.map((a, i) => (
                  <li key={`${a.action}-${i}`}>
                    {a.action}
                    {a.created_at
                      ? ` · ${new Date(a.created_at).toLocaleString()}`
                      : ""}
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section title="History">
            <ul className="space-y-1 text-sm">
              {(row.history || []).map((h) => (
                <li key={h.id}>
                  {h.event_type}
                  {h.created_at
                    ? ` · ${new Date(h.created_at).toLocaleString()}`
                    : ""}
                </li>
              ))}
            </ul>
          </Section>
        </div>
      )}
    </AppShell>
  );
}

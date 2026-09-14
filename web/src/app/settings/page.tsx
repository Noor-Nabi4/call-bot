"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { Mic, ScrollText, Shield, Users } from "lucide-react";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import { errors, settings as copy } from "@/lib/ops-copy";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  DataTable,
  EmptyState,
  ErrorState,
  Field,
  Input,
  LoadingSkeleton,
  PageHeader,
  Surface,
  useToast,
  type DataTableColumn,
} from "@/components/ui";

const API =
  process.env.NEXT_PUBLIC_PLATFORM_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

type AuditEvent = {
  id: string;
  created_at?: string | null;
  actor?: string | null;
  action?: string | null;
};

export default function SettingsPage() {
  const { user, loading } = useAuth({ roles: ["admin"] });
  const toast = useToast();
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [retention, setRetention] = useState({
    recording_retention_days: 30,
    transcript_retention_days: 90,
    audit_retention_days: 365,
  });
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retentionBusy, setRetentionBusy] = useState(false);

  const refresh = useCallback(async () => {
    const [a, r] = await Promise.all([
      fetch(`${API}/api/admin/audit`, { credentials: "include" }).then((x) =>
        x.json(),
      ),
      fetch(`${API}/api/admin/retention`, { credentials: "include" }).then((x) =>
        x.json(),
      ),
    ]);
    setAudit(a.events || []);
    if (r.settings) setRetention(r.settings);
  }, []);

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

  const auditColumns: DataTableColumn<AuditEvent>[] = [
    {
      id: "time",
      header: "Time",
      cell: (e) => (
        <span className="font-mono text-xs">{String(e.created_at || "—")}</span>
      ),
      mono: true,
    },
    {
      id: "actor",
      header: "Actor",
      cell: (e) => <span>{String(e.actor || "—")}</span>,
    },
    {
      id: "action",
      header: "Action",
      cell: (e) => (
        <span className="font-mono text-xs">{String(e.action || "—")}</span>
      ),
      mono: true,
    },
  ];

  if (loading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  async function onRetention(e: FormEvent) {
    e.preventDefault();
    setRetentionBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/admin/retention`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(retention),
      });
      if (!res.ok) throw new Error(errors.saveFailed);
      toast.push("Retention saved", "success");
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    } finally {
      setRetentionBusy(false);
    }
  }

  return (
    <AppShell user={user}>
      <PageHeader title={copy.title} description={copy.description} />

      {error ? (
        <ErrorState
          className="mb-4"
          message={error}
          onRetry={() => {
            setError(null);
            setFetching(true);
            refresh()
              .catch((e) => setError(safeUserError(e, errors.loadFailed)))
              .finally(() => setFetching(false));
          }}
        />
      ) : null}

      {fetching ? (
        <LoadingSkeleton rows={6} />
      ) : (
        <div className="space-y-6">
          <p className="text-sm text-text-secondary">{copy.privacyData}</p>
          <Surface className="flex flex-wrap items-center justify-between gap-3 p-4">
            <div className="flex items-start gap-2">
              <Mic className="mt-0.5 size-4 text-text-muted" aria-hidden />
              <div>
                <h2 className="text-sm font-semibold text-text-primary">
                  {copy.assistantLink}
                </h2>
                <p className="text-sm text-text-secondary">
                  {copy.assistantLinkHint}
                </p>
              </div>
            </div>
            <Link
              href="/agents"
              className="rounded-[10px] border border-border bg-surface px-3 py-2 text-sm font-medium hover:bg-surface-2"
            >
              Open
            </Link>
          </Surface>
          <Surface className="flex flex-wrap items-center justify-between gap-3 p-4">
            <div className="flex items-start gap-2">
              <Users className="mt-0.5 size-4 text-text-muted" aria-hidden />
              <div>
                <h2 className="text-sm font-semibold text-text-primary">
                  {copy.teamLink}
                </h2>
                <p className="text-sm text-text-secondary">{copy.teamLinkHint}</p>
              </div>
            </div>
            <Link
              href="/settings/team"
              className="rounded-[10px] border border-border bg-surface px-3 py-2 text-sm font-medium hover:bg-surface-2"
            >
              Open
            </Link>
          </Surface>
          <Surface className="flex flex-wrap items-center justify-between gap-3 p-4">
            <div>
              <h2 className="text-sm font-semibold text-text-primary">
                {copy.billingLink}
              </h2>
              <p className="text-sm text-text-secondary">{copy.billingLinkHint}</p>
            </div>
            <Link
              href="/settings/billing"
              className="rounded-[10px] border border-border bg-surface px-3 py-2 text-sm font-medium hover:bg-surface-2"
            >
              Open
            </Link>
          </Surface>

          <section>
            <div className="mb-3 flex items-center gap-2">
              <Shield className="size-4 text-text-muted" aria-hidden />
              <h2 className="text-sm font-semibold text-text-primary">
                {copy.retention}
              </h2>
            </div>
            <Surface className="max-w-lg p-4">
              <p className="mb-3 text-sm text-text-secondary">
                {copy.privacyRecordings}
              </p>
              <form onSubmit={onRetention} className="grid gap-3">
                {(
                  [
                    ["recording_retention_days", copy.recordings],
                    ["transcript_retention_days", copy.transcripts],
                    ["audit_retention_days", copy.audit],
                  ] as const
                ).map(([key, label]) => (
                  <Field key={key} label={`${label} (days)`}>
                    <Input
                      type="number"
                      value={retention[key]}
                      onChange={(e) =>
                        setRetention({
                          ...retention,
                          [key]: Number(e.target.value),
                        })
                      }
                    />
                  </Field>
                ))}
                <Button type="submit" disabled={retentionBusy} className="w-fit">
                  {retentionBusy ? "Saving…" : "Save retention"}
                </Button>
              </form>
            </Surface>
          </section>

          <section>
            <div className="mb-3 flex items-center gap-2">
              <ScrollText className="size-4 text-text-muted" aria-hidden />
              <h2 className="text-sm font-semibold text-text-primary">
                {copy.audit}
              </h2>
            </div>
            <DataTable
              columns={auditColumns}
              rows={audit}
              className="max-h-96 overflow-y-auto"
              empty={
                <EmptyState
                  title={copy.noAudit}
                  description={copy.noAuditHint}
                />
              }
            />
          </section>
          <p className="text-sm text-text-muted">{copy.privacyConfig}</p>
        </div>
      )}
    </AppShell>
  );
}

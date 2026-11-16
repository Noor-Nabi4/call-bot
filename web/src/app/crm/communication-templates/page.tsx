"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import {
  listCommunicationTemplates,
  type CommunicationTemplate,
} from "@/lib/api/communication-templates";
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

export default function CommunicationTemplatesPage() {
  const { user, loading, forbidden } = useAuth({
    permission: "communication_templates.read",
  });
  const [channel, setChannel] = useState<string>("SMS");
  const [items, setItems] = useState<CommunicationTemplate[]>([]);
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setFetching(true);
    setError(null);
    try {
      const res = await listCommunicationTemplates({ channel });
      setItems(res.items || []);
    } catch (e) {
      setError(safeUserError(e, errors.loadFailed));
    } finally {
      setFetching(false);
    }
  }, [channel]);

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
        title="Communication templates"
        description="SMS and email copy for automations — rendered server-side, delivered via the existing notification outbox."
        actions={
          <Select value={channel} onChange={(e) => setChannel(e.target.value)}>
            <option value="SMS">SMS</option>
            <option value="EMAIL">Email</option>
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
          title="No templates"
          description="Default templates are seeded when you open this page."
        />
      ) : (
        <ul className="divide-y divide-border rounded-lg border border-border">
          {items.map((t) => (
            <li key={t.id}>
              <Link
                href={`/crm/communication-templates/${t.id}`}
                className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 hover:bg-surface-muted/50"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2 text-sm">
                    <StatusPill status={t.status.toLowerCase()} />
                    <span className="font-medium text-text-primary">{t.name}</span>
                    <span className="text-text-muted">{t.template_key}</span>
                  </div>
                  <p className="mt-1 text-xs text-text-secondary">
                    v{t.active_version}
                    {t.updated_at
                      ? ` · updated ${new Date(t.updated_at).toLocaleString()}`
                      : ""}
                  </p>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </AppShell>
  );
}

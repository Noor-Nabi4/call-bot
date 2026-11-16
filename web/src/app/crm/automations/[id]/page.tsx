"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import {
  activateAutomation,
  disableAutomation,
  getAutomation,
  listAutomationExecutions,
  type AutomationExecution,
  type AutomationWorkflow,
} from "@/lib/api/automations";
import { useAuth } from "@/lib/use-auth";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  ErrorState,
  LoadingSkeleton,
  PageHeader,
  StatusPill,
} from "@/components/ui";

export default function AutomationDetailPage() {
  const params = useParams();
  const id = String(params.id || "");
  const { user, loading: authLoading } = useAuth();
  const [workflow, setWorkflow] = useState<AutomationWorkflow | null>(null);
  const [executions, setExecutions] = useState<AutomationExecution[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const [wf, ex] = await Promise.all([
        getAutomation(id),
        listAutomationExecutions(id),
      ]);
      setWorkflow(wf.workflow);
      setExecutions(ex.executions);
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (!authLoading && user) void load();
  }, [authLoading, user, load]);

  async function toggle() {
    if (!workflow || busy) return;
    setBusy(true);
    setError(null);
    try {
      const next =
        workflow.status === "ACTIVE"
          ? await disableAutomation(id)
          : await activateAutomation(id);
      setWorkflow(next.workflow);
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

  return (
    <AppShell user={user}>
      <PageHeader
        title={workflow?.name || "Workflow"}
        description={workflow?.trigger_event}
      />
      <p className="mb-4 text-sm">
        <Link href="/crm/automations" className="underline-offset-2 hover:underline">
          Back to automations
        </Link>
      </p>
      {error ? <ErrorState message={error} /> : null}
      {loading || !workflow ? (
        <LoadingSkeleton />
      ) : (
        <div className="space-y-8">
          <section className="space-y-3">
            <div className="flex flex-wrap items-center gap-3">
              <StatusPill status={workflow.status} />
              <Button size="sm" variant="ghost" disabled={busy} onClick={() => void toggle()}>
                {workflow.status === "ACTIVE" ? "Disable" : "Activate"}
              </Button>
            </div>
            <div>
              <h2 className="text-sm font-medium text-neutral-500">WHEN</h2>
              <p className="text-base">{workflow.trigger_event}</p>
            </div>
            <div>
              <h2 className="text-sm font-medium text-neutral-500">THEN</h2>
              <ul className="mt-1 space-y-1 text-sm">
                {(workflow.definition?.actions || []).map((a, i) => (
                  <li key={`${a.type}-${i}`}>
                    <span className="font-medium">{a.type}</span>
                  </li>
                ))}
              </ul>
            </div>
          </section>
          <section className="space-y-2">
            <h2 className="text-base font-medium">Executions</h2>
            {executions.length === 0 ? (
              <p className="text-sm text-neutral-600">No executions yet.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {executions.map((ex) => (
                  <li key={ex.id} className="border-b border-neutral-200 pb-2">
                    <div className="flex flex-wrap gap-2">
                      <StatusPill status={ex.status} />
                      <span className="text-neutral-500">
                        {ex.completed_at
                          ? new Date(ex.completed_at).toLocaleString()
                          : "—"}
                      </span>
                    </div>
                    {ex.error_message ? (
                      <p className="text-neutral-600">{ex.error_message}</p>
                    ) : null}
                    <ul className="mt-1 text-neutral-700">
                      {ex.actions.map((a) => (
                        <li key={a.id}>
                          {a.action_key}: {a.status}
                        </li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </AppShell>
  );
}

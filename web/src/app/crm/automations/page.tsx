"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import {
  listAutomations,
  type AutomationWorkflow,
} from "@/lib/api/automations";
import { useAuth } from "@/lib/use-auth";
import { safeUserError } from "@/lib/safe-error";
import {
  DataTable,
  EmptyState,
  ErrorState,
  LoadingSkeleton,
  PageHeader,
  StatusPill,
  type DataTableColumn,
} from "@/components/ui";

export default function AutomationsListPage() {
  const { user, loading: authLoading } = useAuth();
  const [rows, setRows] = useState<AutomationWorkflow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listAutomations();
      setRows(res.workflows);
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!authLoading && user) void load();
  }, [authLoading, user, load]);

  const columns: DataTableColumn<AutomationWorkflow>[] = [
    {
      id: "name",
      header: "Workflow",
      cell: (row) => (
        <Link
          href={`/crm/automations/${row.id}`}
          className="font-medium underline-offset-2 hover:underline"
        >
          {row.name}
        </Link>
      ),
    },
    {
      id: "trigger",
      header: "When",
      cell: (row) => row.trigger_event,
    },
    {
      id: "status",
      header: "Status",
      cell: (row) => <StatusPill status={row.status} />,
    },
  ];

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
        title="Automations"
        description="WHEN an event occurs, IF conditions match, THEN run actions."
        actions={
          <Link
            href="/crm/automations/new"
            className="text-sm font-medium underline-offset-2 hover:underline"
          >
            New workflow
          </Link>
        }
      />
      {error ? <ErrorState message={error} /> : null}
      {loading ? (
        <LoadingSkeleton />
      ) : rows.length === 0 ? (
        <EmptyState title="No workflows yet" />
      ) : (
        <DataTable columns={columns} rows={rows} />
      )}
    </AppShell>
  );
}

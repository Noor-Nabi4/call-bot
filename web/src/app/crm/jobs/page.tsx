"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import {
  JOB_STATUSES,
  jobStatusLabel,
  listCrmJobs,
  type JobRow,
} from "@/lib/api/jobs-crm";
import { useAuth } from "@/lib/use-auth";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  DataTable,
  EmptyState,
  ErrorState,
  FilterBar,
  LoadingSkeleton,
  PageHeader,
  SearchInput,
  Select,
  StatusPill,
  type DataTableColumn,
} from "@/components/ui";

export default function CrmJobsPage() {
  const { user, loading: authLoading } = useAuth();
  const [rows, setRows] = useState<JobRow[]>([]);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [cursor, setCursor] = useState<string | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await listCrmJobs({
        q: q || undefined,
        status: status || undefined,
        limit: 50,
        cursor: cursor || undefined,
      });
      setRows(list.jobs);
      setNextCursor(list.next_cursor ?? null);
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setLoading(false);
    }
  }, [q, status, cursor]);

  useEffect(() => {
    if (!authLoading && user) void load();
  }, [authLoading, user, load]);

  const columns: DataTableColumn<JobRow>[] = [
    {
      id: "job_number",
      header: "Job",
      cell: (row) => (
        <Link
          href={`/crm/jobs/${row.id}`}
          className="font-medium underline-offset-2 hover:underline"
        >
          {row.job_number}
        </Link>
      ),
    },
    {
      id: "customer",
      header: "Customer",
      cell: (row) => row.customer?.display_name || row.customer?.name || "—",
    },
    {
      id: "service_type",
      header: "Service",
      cell: (row) => row.service_type,
    },
    {
      id: "status",
      header: "Status",
      cell: (row) => <StatusPill status={row.status} />,
    },
    {
      id: "technician",
      header: "Technician",
      cell: (row) => row.assigned_technician?.display_name || "Unassigned",
    },
    {
      id: "scheduled",
      header: "Scheduled",
      cell: (row) =>
        row.scheduled_starts_at
          ? new Date(row.scheduled_starts_at).toLocaleString()
          : "—",
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
        title="Jobs"
        description="Field service job records — lifecycle transitions go through the transition API."
      />
      <FilterBar>
        <SearchInput
          value={q}
          onChange={(e) => {
            setCursor(null);
            setQ(e.target.value);
          }}
          placeholder="Search job #, customer, service…"
          aria-label="Search jobs"
        />
        <Select
          value={status}
          onChange={(e) => {
            setCursor(null);
            setStatus(e.target.value);
          }}
          aria-label="Filter by status"
        >
          <option value="">All statuses</option>
          {JOB_STATUSES.map((s) => (
            <option key={s} value={s}>
              {jobStatusLabel(s)}
            </option>
          ))}
        </Select>
        <Button type="button" variant="secondary" onClick={() => void load()}>
          Refresh
        </Button>
      </FilterBar>

      {error ? <ErrorState message={error} /> : null}
      {loading ? <LoadingSkeleton /> : null}
      {!loading && !error && rows.length === 0 ? (
        <EmptyState
          title="No jobs"
          description="Jobs appear here after they are created from Dispatch, an appointment, or the API."
        />
      ) : null}
      {!loading && rows.length > 0 ? (
        <>
          <DataTable columns={columns} rows={rows} />
          <div className="mt-4 flex gap-2">
            <Button
              type="button"
              variant="secondary"
              disabled={!cursor}
              onClick={() => setCursor(null)}
            >
              First page
            </Button>
            <Button
              type="button"
              variant="secondary"
              disabled={!nextCursor}
              onClick={() => nextCursor && setCursor(nextCursor)}
            >
              Next
            </Button>
          </div>
        </>
      ) : null}
    </AppShell>
  );
}

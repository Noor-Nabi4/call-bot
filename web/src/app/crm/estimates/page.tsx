"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import {
  ESTIMATE_STATUSES,
  listEstimates,
  type EstimateRow,
} from "@/lib/api/estimates";
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

export default function EstimatesPage() {
  const { user, loading: authLoading } = useAuth();
  const [rows, setRows] = useState<EstimateRow[]>([]);
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
      const list = await listEstimates({
        q: q || undefined,
        status: status || undefined,
        limit: 50,
        cursor: cursor || undefined,
      });
      setRows(list.estimates);
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

  const columns: DataTableColumn<EstimateRow>[] = [
    {
      id: "estimate_number",
      header: "Estimate",
      cell: (row) => (
        <Link
          href={`/crm/estimates/${row.id}`}
          className="font-medium underline-offset-2 hover:underline"
        >
          {row.estimate_number}
        </Link>
      ),
    },
    {
      id: "title",
      header: "Title",
      cell: (row) => row.title || "—",
    },
    {
      id: "customer",
      header: "Customer",
      cell: (row) => row.customer?.display_name || row.customer?.name || "—",
    },
    {
      id: "status",
      header: "Status",
      cell: (row) => <StatusPill status={row.status} />,
    },
    {
      id: "total",
      header: "Total",
      cell: (row) => `${row.total} ${row.currency}`,
    },
    {
      id: "valid",
      header: "Valid until",
      cell: (row) =>
        row.valid_until ? new Date(row.valid_until).toLocaleDateString() : "—",
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
        title="Estimates"
        description="Quotes with historical price snapshots. Totals are calculated on the server."
        actions={
          <Link
            href="/crm/estimates/new"
            className="inline-flex h-9 items-center rounded-[var(--radius-md)] bg-teal px-3 text-sm font-semibold text-white"
          >
            New estimate
          </Link>
        }
      />
      <FilterBar>
        <SearchInput
          value={q}
          onChange={(e) => {
            setCursor(null);
            setQ(e.target.value);
          }}
          placeholder="Search estimates"
          aria-label="Search estimates"
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
          {ESTIMATE_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </Select>
      </FilterBar>
      {error ? <ErrorState message={error} /> : null}
      {loading ? (
        <LoadingSkeleton />
      ) : rows.length === 0 ? (
        <EmptyState
          title="No estimates"
          description="Create a draft estimate for a customer to get started."
        />
      ) : (
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
      )}
    </AppShell>
  );
}

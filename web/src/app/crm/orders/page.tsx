"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import {
  listOrders,
  ORDER_STATUSES,
  type OrderRow,
} from "@/lib/api/orders";
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

export default function OrdersPage() {
  const { user, loading: authLoading } = useAuth();
  const [rows, setRows] = useState<OrderRow[]>([]);
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
      const list = await listOrders({
        q: q || undefined,
        status: status || undefined,
        limit: 50,
        cursor: cursor || undefined,
      });
      setRows(list.orders);
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

  const columns: DataTableColumn<OrderRow>[] = [
    {
      id: "order_number",
      header: "Order",
      cell: (row) => (
        <Link
          href={`/crm/orders/${row.id}`}
          className="font-medium underline-offset-2 hover:underline"
        >
          {row.order_number}
        </Link>
      ),
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
      id: "created",
      header: "Created",
      cell: (row) =>
        row.created_at ? new Date(row.created_at).toLocaleString() : "—",
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
        title="Orders"
        description="Commercial transactions with inventory-backed lifecycle."
      />
      <FilterBar>
        <SearchInput
          value={q}
          onChange={(e) => {
            setCursor(null);
            setQ(e.target.value);
          }}
          placeholder="Search order #, customer, SKU…"
          aria-label="Search orders"
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
          {ORDER_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
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
          title="No orders"
          description="Orders appear here after they are created via API or CRM tools."
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

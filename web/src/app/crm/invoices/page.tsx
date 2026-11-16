"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import {
  INVOICE_STATUSES,
  listInvoices,
  type InvoiceRow,
} from "@/lib/api/invoices";
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

export default function InvoicesPage() {
  const { user, loading: authLoading } = useAuth();
  const [rows, setRows] = useState<InvoiceRow[]>([]);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await listInvoices({
        q: q || undefined,
        status: status || undefined,
        overdue_only: overdueOnly,
        limit: 50,
      });
      setRows(list.invoices);
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setLoading(false);
    }
  }, [q, status, overdueOnly]);

  useEffect(() => {
    if (!authLoading && user) void load();
  }, [authLoading, user, load]);

  const columns: DataTableColumn<InvoiceRow>[] = [
    {
      id: "invoice_number",
      header: "Invoice",
      cell: (row) => (
        <Link
          href={`/crm/invoices/${row.id}`}
          className="font-medium underline-offset-2 hover:underline"
        >
          {row.invoice_number}
        </Link>
      ),
    },
    {
      id: "customer",
      header: "Customer",
      cell: (row) => row.customer?.name || row.customer_id.slice(0, 8),
    },
    {
      id: "due_date",
      header: "Due",
      cell: (row) =>
        row.due_date ? new Date(row.due_date).toLocaleDateString() : "—",
    },
    {
      id: "total",
      header: "Total",
      cell: (row) => `${row.total_amount} ${row.currency}`,
    },
    {
      id: "balance",
      header: "Balance",
      cell: (row) => row.balance_due,
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
        title="Invoices"
        description="Server-calculated totals and balances. Payments update status authoritatively."
        actions={
          <Link href="/crm/invoices/new">
            <Button>New invoice</Button>
          </Link>
        }
      />
      <FilterBar className="mb-4">
        <SearchInput
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search invoice # or customer"
          aria-label="Search invoices"
        />
        <Select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          aria-label="Filter by status"
        >
          <option value="">All statuses</option>
          {INVOICE_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </Select>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={overdueOnly}
            onChange={(e) => setOverdueOnly(e.target.checked)}
          />
          Overdue only
        </label>
        <Button variant="secondary" onClick={() => void load()}>
          Apply
        </Button>
      </FilterBar>
      {error ? <ErrorState message={error} onRetry={() => void load()} /> : null}
      {loading ? (
        <LoadingSkeleton />
      ) : rows.length === 0 ? (
        <EmptyState title="No invoices" description="Create an invoice to get started." />
      ) : (
        <DataTable columns={columns} rows={rows} />
      )}
    </AppShell>
  );
}

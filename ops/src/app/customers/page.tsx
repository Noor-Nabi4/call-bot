"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Users } from "lucide-react";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import {
  DataTable,
  EmptyState,
  ErrorState,
  LoadingSkeleton,
  PageHeader,
  SearchInput,
  type DataTableColumn,
} from "@/components/ui";

const API =
  process.env.NEXT_PUBLIC_PLATFORM_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

type Customer = {
  id: string;
  name: string;
  email?: string | null;
  address?: string | null;
  phones: string[];
  updated_at?: string | null;
};

type JobRow = { id: string; customer_id: string; status: string };

function formatUpdated(iso?: string | null) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

export default function CustomersPage() {
  const { user, loading } = useAuth({ roles: ["admin", "dispatcher"] });
  const [rows, setRows] = useState<Customer[]>([]);
  const [openCounts, setOpenCounts] = useState<Record<string, number>>({});
  const [search, setSearch] = useState("");
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [custRes, jobsRes] = await Promise.all([
      fetch(`${API}/api/admin/customers`, { credentials: "include" }),
      fetch(`${API}/api/jobs`, { credentials: "include" }),
    ]);
    if (!custRes.ok) throw new Error(await custRes.text());
    const custData = await custRes.json();
    setRows(custData.customers || []);

    if (jobsRes.ok) {
      const jobsData = await jobsRes.json();
      const counts: Record<string, number> = {};
      for (const job of (jobsData.jobs || []) as JobRow[]) {
        if (["completed", "canceled"].includes(job.status)) continue;
        counts[job.customer_id] = (counts[job.customer_id] || 0) + 1;
      }
      setOpenCounts(counts);
    }
  }, []);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      load()
        .catch((e) => setError(e instanceof Error ? e.message : "Load failed"))
        .finally(() => {
          if (!cancelled) setFetching(false);
        });
    });
    return () => {
      cancelled = true;
    };
  }, [user, load]);

  const filtered = useMemo(() => {
    if (!search.trim()) return rows;
    const q = search.toLowerCase();
    return rows.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        (c.email || "").toLowerCase().includes(q) ||
        (c.address || "").toLowerCase().includes(q) ||
        c.phones.some((p) => p.includes(q)),
    );
  }, [rows, search]);

  const columns: DataTableColumn<Customer>[] = [
    {
      id: "name",
      header: "Customer",
      cell: (c) => (
        <div>
          <p className="font-medium">{c.name}</p>
          {c.email ? (
            <p className="text-xs text-text-muted">{c.email}</p>
          ) : null}
        </div>
      ),
    },
    {
      id: "phones",
      header: "Phones",
      cell: (c) => (
        <span className="text-text-secondary">
          {c.phones.length > 0 ? c.phones.join(", ") : "—"}
        </span>
      ),
    },
    {
      id: "address",
      header: "Address",
      cell: (c) => (
        <span className="text-text-secondary">{c.address || "—"}</span>
      ),
    },
    {
      id: "open",
      header: "Open jobs",
      cell: (c) => (
        <span className="font-mono text-xs">{openCounts[c.id] ?? 0}</span>
      ),
      className: "w-24",
    },
    {
      id: "updated",
      header: "Updated",
      cell: (c) => (
        <span className="text-xs text-text-muted">{formatUpdated(c.updated_at)}</span>
      ),
      className: "w-28",
    },
  ];

  if (loading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  return (
    <AppShell user={user}>
      <PageHeader
        title="Customers"
        description="Tenant customer records from calls, appointments, and jobs."
        actions={
          <SearchInput
            className="w-full sm:w-64"
            placeholder="Search customers…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onClear={() => setSearch("")}
          />
        }
      />

      {error ? (
        <ErrorState
          className="mb-4"
          message={error}
          onRetry={() => {
            setError(null);
            setFetching(true);
            load()
              .catch((e) => setError(e.message))
              .finally(() => setFetching(false));
          }}
        />
      ) : null}

      {fetching ? (
        <LoadingSkeleton rows={5} />
      ) : (
        <DataTable
          columns={columns}
          rows={filtered}
          empty={
            <EmptyState
              icon={<Users className="size-8" />}
              title={search ? "No matching customers" : "No customers yet"}
              description={
                search
                  ? "Try a different search term."
                  : "Customers appear when calls and jobs are created."
              }
            />
          }
        />
      )}
    </AppShell>
  );
}

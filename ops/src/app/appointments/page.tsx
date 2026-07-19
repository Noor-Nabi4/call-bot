"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Calendar } from "lucide-react";
import { AppShell } from "@/components/shell";
import { formatWhen } from "@/lib/api";
import { useAuth } from "@/lib/use-auth";
import { appointments as copy, errors } from "@/lib/copy";
import { safeUserError } from "@/lib/safe-error";
import {
  EmptyState,
  ErrorState,
  FilterBar,
  LoadingSkeleton,
  PageHeader,
  SavedViewSelector,
  SearchInput,
  Select,
  StatusPill,
  Surface,
} from "@/components/ui";

const API =
  process.env.NEXT_PUBLIC_PLATFORM_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

type Appointment = {
  id: string;
  confirmation_code: string;
  status: string;
  service_type: string;
  starts_at?: string | null;
  ends_at?: string | null;
  customer_id?: string | null;
};

type Customer = { id: string; name: string };

function dayKey(iso?: string | null): string {
  if (!iso) return "unscheduled";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "unscheduled";
  return d.toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

export default function AppointmentsPage() {
  const { user, loading } = useAuth({ roles: ["admin", "dispatcher"] });
  const [rows, setRows] = useState<Appointment[]>([]);
  const [customers, setCustomers] = useState<Record<string, string>>({});
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [view, setView] = useState("upcoming");
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [apptRes, custRes] = await Promise.all([
      fetch(`${API}/api/admin/appointments`, { credentials: "include" }),
      fetch(`${API}/api/admin/customers`, { credentials: "include" }),
    ]);
    if (!apptRes.ok) throw new Error(errors.loadFailed);
    const apptData = await apptRes.json();
    setRows(apptData.appointments || []);

    if (custRes.ok) {
      const custData = await custRes.json();
      const map: Record<string, string> = {};
      for (const c of (custData.customers || []) as Customer[]) {
        map[c.id] = c.name;
      }
      setCustomers(map);
    }
  }, []);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      load()
        .catch((e) => setError(safeUserError(e, errors.loadFailed)))
        .finally(() => {
          if (!cancelled) setFetching(false);
        });
    });
    return () => {
      cancelled = true;
    };
  }, [user, load]);

  const filtered = useMemo(() => {
    const now = new Date();
    return rows
      .filter((a) => {
        if (statusFilter && a.status !== statusFilter) return false;
        if (search.trim()) {
          const q = search.toLowerCase();
          const name = a.customer_id ? customers[a.customer_id] || "" : "";
          if (
            !a.confirmation_code.toLowerCase().includes(q) &&
            !a.service_type.toLowerCase().includes(q) &&
            !name.toLowerCase().includes(q)
          )
            return false;
        }
        if (view === "upcoming" && a.starts_at) {
          return new Date(a.starts_at) >= now;
        }
        if (view === "past" && a.starts_at) {
          return new Date(a.starts_at) < now;
        }
        return true;
      })
      .sort((a, b) => {
        const ta = a.starts_at ? new Date(a.starts_at).getTime() : Infinity;
        const tb = b.starts_at ? new Date(b.starts_at).getTime() : Infinity;
        return ta - tb;
      });
  }, [rows, search, statusFilter, view, customers]);

  const grouped = useMemo(() => {
    const groups = new Map<string, Appointment[]>();
    for (const a of filtered) {
      const key = dayKey(a.starts_at);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(a);
    }
    return Array.from(groups.entries());
  }, [filtered]);

  const statuses = useMemo(
    () => [...new Set(rows.map((a) => a.status))].sort(),
    [rows],
  );

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
        title={copy.title}
        description={copy.description}
      />

      <FilterBar>
        <SearchInput
          className="min-w-[12rem] flex-1"
          placeholder="Search code, service, customer…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onClear={() => setSearch("")}
        />
        <Select
          className="w-auto min-w-[8rem]"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          aria-label="Filter by status"
        >
          <option value="">All statuses</option>
          {statuses.map((s) => (
            <option key={s} value={s}>
              {s.replace(/_/g, " ")}
            </option>
          ))}
        </Select>
        <SavedViewSelector
          views={[
            { id: "upcoming", label: "Upcoming" },
            { id: "past", label: "Past" },
            { id: "all", label: "All" },
          ]}
          value={view}
          onChange={setView}
        />
      </FilterBar>

      {error ? (
        <ErrorState
          className="mb-4"
          message={error}
          onRetry={() => {
            setError(null);
            setFetching(true);
            load()
              .catch((e) => setError(safeUserError(e, errors.loadFailed)))
              .finally(() => setFetching(false));
          }}
        />
      ) : null}

      {fetching ? (
        <LoadingSkeleton rows={5} />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={<Calendar className="size-8" />}
          title={copy.empty}
          description={copy.emptyHint}
        />
      ) : (
        <div className="space-y-6">
          {grouped.map(([day, items]) => (
            <section key={day}>
              <h2 className="mb-2 text-sm font-semibold text-text-primary">{day}</h2>
              <ul className="space-y-2">
                {items.map((a) => (
                  <li key={a.id}>
                    <Surface className="flex flex-wrap items-center gap-3 p-3 sm:gap-4">
                      <div className="min-w-[4.5rem] font-mono text-xs text-text-muted">
                        {a.starts_at
                          ? new Date(a.starts_at).toLocaleTimeString(undefined, {
                              hour: "numeric",
                              minute: "2-digit",
                            })
                          : "—"}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-text-primary">{a.service_type}</p>
                        <p className="text-sm text-text-secondary">
                          {a.customer_id
                            ? customers[a.customer_id] || a.customer_id
                            : "—"}
                          {" · "}
                          <span className="font-mono text-xs">{a.confirmation_code}</span>
                        </p>
                        {a.ends_at ? (
                          <p className="text-xs text-text-muted">
                            Ends {formatWhen(a.ends_at)}
                          </p>
                        ) : null}
                      </div>
                      <StatusPill status={a.status} />
                    </Surface>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </AppShell>
  );
}

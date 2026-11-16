"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import {
  createLead,
  getPipelineCounts,
  listLeads,
  transitionLead,
  LEAD_PRIORITIES,
  LEAD_SOURCES,
  LEAD_STATUSES,
  type LeadRow,
  type PipelineCounts,
} from "@/lib/api/leads";
import { useAuth } from "@/lib/use-auth";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  DataTable,
  EmptyState,
  ErrorState,
  Field,
  FilterBar,
  Input,
  LoadingSkeleton,
  PageHeader,
  SearchInput,
  Select,
  StatusPill,
  Textarea,
  type DataTableColumn,
} from "@/components/ui";

type ViewMode = "pipeline" | "list";

export default function LeadsPage() {
  const { user, loading: authLoading } = useAuth();
  const [view, setView] = useState<ViewMode>("pipeline");
  const [rows, setRows] = useState<LeadRow[]>([]);
  const [counts, setCounts] = useState<PipelineCounts | null>(null);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [source, setSource] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [form, setForm] = useState({
    title: "",
    source: "PHONE",
    priority: "MEDIUM",
    description: "",
    prospect_name: "",
    prospect_phone: "",
  });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [list, pipe] = await Promise.all([
        listLeads({
          q: q || undefined,
          status: status || undefined,
          priority: priority || undefined,
          source: source || undefined,
          limit: 200,
        }),
        getPipelineCounts({
          priority: priority || undefined,
          source: source || undefined,
        }),
      ]);
      setRows(list.leads);
      setCounts(pipe);
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setLoading(false);
    }
  }, [q, status, priority, source]);

  useEffect(() => {
    if (!authLoading && user) void load();
  }, [authLoading, user, load]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    if (!form.title.trim()) return;
    setCreating(true);
    setError(null);
    try {
      await createLead({
        title: form.title.trim(),
        source: form.source,
        priority: form.priority,
        description: form.description || undefined,
        prospect_name: form.prospect_name || undefined,
        prospect_phone: form.prospect_phone || undefined,
      });
      setForm({
        title: "",
        source: "PHONE",
        priority: "MEDIUM",
        description: "",
        prospect_name: "",
        prospect_phone: "",
      });
      await load();
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setCreating(false);
    }
  }

  async function onTransition(leadId: string, toStatus: string) {
    if (busyId) return;
    setBusyId(leadId);
    setError(null);
    const prev = rows;
    setRows((cur) =>
      cur.map((r) => (r.id === leadId ? { ...r, status: toStatus } : r)),
    );
    try {
      await transitionLead(leadId, toStatus);
      await load();
    } catch (err) {
      setRows(prev);
      setError(safeUserError(err));
      await load();
    } finally {
      setBusyId(null);
    }
  }

  const columns: DataTableColumn<LeadRow>[] = [
    {
      id: "title",
      header: "Lead",
      cell: (r) => (
        <Link href={`/crm/leads/${r.id}`} className="font-medium underline-offset-2 hover:underline">
          {r.title}
        </Link>
      ),
    },
    {
      id: "status",
      header: "Status",
      cell: (r) => <StatusPill status={r.status} />,
    },
    {
      id: "priority",
      header: "Priority",
      cell: (r) => r.priority,
    },
    {
      id: "source",
      header: "Source",
      cell: (r) => r.source,
    },
    {
      id: "customer",
      header: "Customer",
      cell: (r) =>
        r.customer?.display_name ||
        r.customer?.name ||
        r.prospect_name ||
        "—",
    },
    {
      id: "owner",
      header: "Owner",
      cell: (r) => r.owner?.name || "—",
    },
    {
      id: "updated",
      header: "Updated",
      cell: (r) =>
        r.updated_at ? new Date(r.updated_at).toLocaleString() : "—",
    },
  ];

  if (authLoading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={8} />
      </div>
    );
  }

  const byStatus = LEAD_STATUSES.reduce(
    (acc, s) => {
      acc[s] = rows.filter((r) => r.status === s);
      return acc;
    },
    {} as Record<string, LeadRow[]>,
  );

  return (
    <AppShell user={user}>
      <PageHeader
        title="Leads"
        description="Pipeline and list views for inbound opportunities."
        actions={
          <div className="flex gap-2">
            <Button
              variant={view === "pipeline" ? "primary" : "secondary"}
              onClick={() => setView("pipeline")}
            >
              Pipeline
            </Button>
            <Button
              variant={view === "list" ? "primary" : "secondary"}
              onClick={() => setView("list")}
            >
              List
            </Button>
          </div>
        }
      />

      {error ? <ErrorState message={error} /> : null}

      <FilterBar>
        <SearchInput
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onClear={() => setQ("")}
          placeholder="Search leads…"
          aria-label="Search leads"
        />
        <Select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          aria-label="Status"
        >
          <option value="">All statuses</option>
          {LEAD_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </Select>
        <Select
          value={priority}
          onChange={(e) => setPriority(e.target.value)}
          aria-label="Priority"
        >
          <option value="">All priorities</option>
          {LEAD_PRIORITIES.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </Select>
        <Select
          value={source}
          onChange={(e) => setSource(e.target.value)}
          aria-label="Source"
        >
          <option value="">All sources</option>
          {LEAD_SOURCES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </Select>
        <Button variant="secondary" onClick={() => void load()}>
          Refresh
        </Button>
      </FilterBar>

      <form
        onSubmit={onCreate}
        className="mb-6 grid gap-3 rounded-lg border border-zinc-200 p-4 md:grid-cols-3"
      >
        <Field label="Title">
          <Input
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            required
          />
        </Field>
        <Field label="Source">
          <Select
            value={form.source}
            onChange={(e) => setForm({ ...form, source: e.target.value })}
          >
            {LEAD_SOURCES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Priority">
          <Select
            value={form.priority}
            onChange={(e) => setForm({ ...form, priority: e.target.value })}
          >
            {LEAD_PRIORITIES.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Prospect name">
          <Input
            value={form.prospect_name}
            onChange={(e) =>
              setForm({ ...form, prospect_name: e.target.value })
            }
          />
        </Field>
        <Field label="Prospect phone">
          <Input
            value={form.prospect_phone}
            onChange={(e) =>
              setForm({ ...form, prospect_phone: e.target.value })
            }
          />
        </Field>
        <Field label="Description">
          <Textarea
            value={form.description}
            onChange={(e) =>
              setForm({ ...form, description: e.target.value })
            }
            rows={2}
          />
        </Field>
        <div className="md:col-span-3">
          <Button type="submit" disabled={creating}>
            {creating ? "Creating…" : "Create lead"}
          </Button>
        </div>
      </form>

      {loading ? (
        <LoadingSkeleton />
      ) : view === "list" ? (
        rows.length === 0 ? (
          <EmptyState title="No leads" description="Create a lead to get started." />
        ) : (
          <DataTable columns={columns} rows={rows} />
        )
      ) : (
        <div className="grid gap-3 overflow-x-auto md:grid-cols-3 xl:grid-cols-6">
          {LEAD_STATUSES.map((col) => (
            <div
              key={col}
              className="min-w-[200px] rounded-lg border border-zinc-200 bg-zinc-50/60 p-2"
            >
              <div className="mb-2 flex items-center justify-between px-1">
                <span className="text-xs font-semibold tracking-wide text-zinc-700">
                  {col}
                </span>
                <span className="text-xs text-zinc-500">
                  {counts?.counts?.[col] ?? byStatus[col].length}
                </span>
              </div>
              <div className="flex max-h-[70vh] flex-col gap-2 overflow-y-auto">
                {byStatus[col].length === 0 ? (
                  <p className="px-1 text-xs text-zinc-400">Empty</p>
                ) : (
                  byStatus[col].map((lead) => (
                    <PipelineCard
                      key={lead.id}
                      lead={lead}
                      busy={busyId === lead.id}
                      onTransition={onTransition}
                    />
                  ))
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </AppShell>
  );
}

function PipelineCard({
  lead,
  busy,
  onTransition,
}: {
  lead: LeadRow;
  busy: boolean;
  onTransition: (id: string, status: string) => void;
}) {
  const nextOptions = nextStatuses(lead.status);
  return (
    <div className="rounded-md border border-zinc-200 bg-white p-3 shadow-sm">
      <Link
        href={`/crm/leads/${lead.id}`}
        className="block text-sm font-medium text-zinc-900 hover:underline"
      >
        {lead.title}
      </Link>
      <p className="mt-1 text-xs text-zinc-500">
        {lead.customer?.display_name ||
          lead.customer?.name ||
          lead.prospect_name ||
          "No customer"}
      </p>
      <div className="mt-2 flex flex-wrap gap-1 text-[10px] uppercase tracking-wide text-zinc-500">
        <span>{lead.source}</span>
        <span>·</span>
        <span>{lead.priority}</span>
        {lead.service?.name ? (
          <>
            <span>·</span>
            <span>{lead.service.name}</span>
          </>
        ) : null}
        {lead.product?.name ? (
          <>
            <span>·</span>
            <span>{lead.product.name}</span>
          </>
        ) : null}
      </div>
      {lead.owner?.name ? (
        <p className="mt-1 text-xs text-zinc-500">Owner: {lead.owner.name}</p>
      ) : null}
      {lead.updated_at ? (
        <p className="mt-1 text-[10px] text-zinc-400">
          {new Date(lead.updated_at).toLocaleString()}
        </p>
      ) : null}
      {nextOptions.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-1">
          {nextOptions.map((s) => (
            <Button
              key={s}
              variant="secondary"
              disabled={busy}
              onClick={() => onTransition(lead.id, s)}
            >
              → {s}
            </Button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function nextStatuses(current: string): string[] {
  const map: Record<string, string[]> = {
    NEW: ["QUALIFIED", "LOST"],
    QUALIFIED: ["CONTACTED", "LOST"],
    CONTACTED: ["BOOKED", "LOST"],
    BOOKED: ["WON", "LOST"],
    LOST: ["NEW"],
    WON: [],
  };
  return map[current] || [];
}

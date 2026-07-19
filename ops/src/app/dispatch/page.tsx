"use client";

import Link from "next/link";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { LayoutGrid, MoreHorizontal, Plus, RefreshCw } from "lucide-react";
import { AppShell } from "@/components/shell";
import {
  KanbanBoard,
  KanbanColumn,
  JobCard,
  QuickFilterTabs,
  StatusStrip,
} from "@/components/ops/dispatch";
import {
  assignJob,
  createJob,
  createTechnician,
  formatWhen,
  listJobs,
  listTechnicians,
  transitionJob,
  type Job,
  type Technician,
} from "@/lib/api";
import { deriveUrgency } from "@/lib/schedule";
import { cn } from "@/lib/cn";
import { useAuth } from "@/lib/use-auth";
import { dispatch as copy, errors } from "@/lib/copy";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  DetailDrawer,
  EmptyState,
  ErrorState,
  Field,
  Input,
  LoadingSkeleton,
  SearchInput,
  Select,
  StatusPill,
  useToast,
} from "@/components/ui";

const API =
  process.env.NEXT_PUBLIC_PLATFORM_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

const COLUMNS = [
  "new",
  "scheduled",
  "dispatched",
  "in_progress",
  "completed",
] as const;

const SAVED_VIEWS = [
  { id: "all", label: "All" },
  { id: "unassigned", label: "Unassigned" },
  { id: "today", label: "Today" },
  { id: "overdue", label: "Overdue" },
] as const;

const SAVED_VIEW_IDS = new Set<string>(SAVED_VIEWS.map((v) => v.id));

type CustomerOption = {
  id: string;
  name: string;
};

function matchesSearch(job: Job, q: string): boolean {
  if (!q.trim()) return true;
  const needle = q.toLowerCase();
  return (
    job.reference_code.toLowerCase().includes(needle) ||
    (job.customer?.name || "").toLowerCase().includes(needle) ||
    job.service_type.toLowerCase().includes(needle) ||
    (job.customer?.address || "").toLowerCase().includes(needle)
  );
}

function matchesDate(job: Job, dateFilter: string): boolean {
  if (!dateFilter) return true;
  if (!job.scheduled_starts_at) return false;
  const d = new Date(job.scheduled_starts_at);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}` === dateFilter;
}

function isActiveJob(job: Job): boolean {
  return !["completed", "canceled", "cancelled"].includes(job.status);
}

function DispatchWorkspace() {
  const searchParams = useSearchParams();
  const { user, loading } = useAuth({ roles: ["admin", "dispatcher"] });
  const toast = useToast();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [techs, setTechs] = useState<Technician[]>([]);
  const [customers, setCustomers] = useState<CustomerOption[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [fetching, setFetching] = useState(true);
  const [search, setSearch] = useState("");
  const [dateFilter, setDateFilter] = useState("");
  const [techFilter, setTechFilter] = useState("");
  const [urgencyFilter, setUrgencyFilter] = useState("");
  const [areaFilter, setAreaFilter] = useState("");
  const [savedView, setSavedView] = useState(() => {
    const view = searchParams.get("view");
    return view && SAVED_VIEW_IDS.has(view) ? view : "all";
  });
  const statusFilter = (searchParams.get("status") || "").toLowerCase().trim();
  const [moreOpen, setMoreOpen] = useState(false);
  const [previewJob, setPreviewJob] = useState<Job | null>(null);
  const [jobDrawerOpen, setJobDrawerOpen] = useState(false);
  const [techDrawerOpen, setTechDrawerOpen] = useState(false);
  const [jobForm, setJobForm] = useState({
    customer_id: "",
    service_type: "",
    scheduled_starts_at: "",
  });
  const [techForm, setTechForm] = useState({
    name: "",
    email: "",
    password: "",
    phone: "",
  });
  const [formBusy, setFormBusy] = useState(false);

  const refresh = useCallback(async () => {
    const [j, t] = await Promise.all([listJobs(), listTechnicians()]);
    setJobs(j.jobs);
    setTechs(t.technicians);
  }, []);

  const loadCustomers = useCallback(async () => {
    const res = await fetch(`${API}/api/admin/customers`, {
      credentials: "include",
    });
    if (!res.ok) return;
    const data = await res.json();
    const rows = (data.customers || []) as { id: string; name: string }[];
    setCustomers(rows.map((c) => ({ id: c.id, name: c.name })));
  }, []);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      Promise.all([refresh(), loadCustomers()])
        .catch((e) => setError(safeUserError(e, errors.loadFailed)))
        .finally(() => {
          if (!cancelled) setFetching(false);
        });
    });
    const id = setInterval(() => {
      refresh().catch(() => undefined);
    }, 5000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [user, refresh, loadCustomers]);

  const activeJobCount = useMemo(
    () => jobs.filter(isActiveJob).length,
    [jobs],
  );

  const filteredJobs = useMemo(() => {
    return jobs.filter((job) => {
      if (!matchesSearch(job, search)) return false;
      if (!matchesDate(job, dateFilter)) return false;
      if (techFilter === "unassigned" && job.assigned_technician_id) return false;
      if (
        techFilter &&
        techFilter !== "unassigned" &&
        job.assigned_technician_id !== techFilter
      )
        return false;
      if (
        urgencyFilter &&
        deriveUrgency(job.scheduled_starts_at) !== urgencyFilter
      )
        return false;
      if (
        areaFilter &&
        !(job.customer?.address || "")
          .toLowerCase()
          .includes(areaFilter.toLowerCase())
      )
        return false;
      if (savedView === "unassigned" && job.assigned_technician_id) return false;
      if (
        savedView === "today" &&
        deriveUrgency(job.scheduled_starts_at) !== "today"
      )
        return false;
      if (
        savedView === "overdue" &&
        deriveUrgency(job.scheduled_starts_at) !== "overdue"
      )
        return false;
      if (statusFilter && job.status.toLowerCase() !== statusFilter) return false;
      return true;
    });
  }, [
    jobs,
    search,
    dateFilter,
    techFilter,
    urgencyFilter,
    areaFilter,
    savedView,
    statusFilter,
  ]);

  const boardColumns = useMemo(() => {
    if (
      statusFilter &&
      !(COLUMNS as readonly string[]).includes(statusFilter)
    ) {
      return [...COLUMNS, statusFilter] as string[];
    }
    return [...COLUMNS] as string[];
  }, [statusFilter]);

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const col of boardColumns) counts[col] = 0;
    for (const job of filteredJobs) {
      if (counts[job.status] !== undefined) counts[job.status] += 1;
    }
    return counts;
  }, [filteredJobs, boardColumns]);

  const moreActive = Boolean(urgencyFilter || areaFilter);

  if (loading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  async function onAssign(jobId: string, technicianId: string) {
    setError(null);
    try {
      await assignJob(jobId, technicianId);
      await refresh();
      toast.push("Technician assigned", "success");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Assign failed");
    }
  }

  async function onDispatch(jobId: string) {
    setError(null);
    try {
      await transitionJob(jobId, "dispatched");
      await refresh();
      toast.push("Job dispatched", "success");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Dispatch failed");
    }
  }

  async function onCreateJob(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setFormBusy(true);
    try {
      await createJob({
        customer_id: jobForm.customer_id,
        service_type: jobForm.service_type,
        status: "new",
        scheduled_starts_at: jobForm.scheduled_starts_at
          ? new Date(jobForm.scheduled_starts_at).toISOString()
          : null,
      });
      setJobForm({ customer_id: "", service_type: "", scheduled_starts_at: "" });
      setJobDrawerOpen(false);
      await refresh();
      toast.push("Job created", "success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create job failed");
    } finally {
      setFormBusy(false);
    }
  }

  async function onCreateTech(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setFormBusy(true);
    try {
      await createTechnician({
        name: techForm.name,
        email: techForm.email,
        password: techForm.password,
        phone: techForm.phone || undefined,
      });
      setTechForm({ name: "", email: "", password: "", phone: "" });
      setTechDrawerOpen(false);
      await refresh();
      toast.push("Technician created", "success");
    } catch (err) {
      setError(safeUserError(err, errors.createFailed));
    } finally {
      setFormBusy(false);
    }
  }

  return (
    <AppShell user={user}>
      <header className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-lg font-semibold tracking-tight text-text-primary">
            {copy.title}
          </h1>
          <p className="mt-0.5 text-sm text-text-secondary">
            {copy.description}
          </p>
          <p className="mt-1 text-xs text-text-muted">
            {activeJobCount} active job{activeJobCount === 1 ? "" : "s"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() =>
              refresh().catch((e) => setError(safeUserError(e, errors.loadFailed)))
            }
          >
            <RefreshCw className="size-3.5" aria-hidden />
            Refresh
          </Button>
          <Button size="sm" onClick={() => setJobDrawerOpen(true)}>
            <Plus className="size-3.5" aria-hidden />
            Create job
          </Button>
        </div>
      </header>

      {error ? (
        <ErrorState
          className="mb-3"
          message={error}
          onRetry={() => {
            setError(null);
            refresh().catch((e) => setError(safeUserError(e, errors.loadFailed)));
          }}
        />
      ) : null}

      <StatusStrip columns={boardColumns} counts={statusCounts} className="mb-2" />

      {statusFilter ? (
        <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
          <span className="rounded-lg border border-border bg-surface-muted px-2.5 py-1 text-text-secondary">
            Status:{" "}
            <span className="font-medium text-text-primary">
              {statusFilter.replace(/_/g, " ")}
            </span>
          </span>
          <Link
            href="/dispatch"
            className="text-xs text-brand hover:underline"
          >
            Clear status filter
          </Link>
        </div>
      ) : null}

      <div
        className="mb-2 flex flex-wrap items-center gap-2"
        role="toolbar"
        aria-label="Dispatch filters"
      >
        <SearchInput
          className="w-full min-w-[10rem] sm:max-w-[14rem] sm:flex-none"
          placeholder="Search…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onClear={() => setSearch("")}
        />
        <Input
          type="date"
          className="h-8 w-auto min-w-[9.5rem] text-xs"
          value={dateFilter}
          onChange={(e) => setDateFilter(e.target.value)}
          aria-label="Date"
        />
        <Select
          className="h-8 w-auto min-w-[8rem] text-xs"
          value={techFilter}
          onChange={(e) => setTechFilter(e.target.value)}
          aria-label="Technician"
        >
          <option value="">Technician</option>
          <option value="unassigned">Unassigned</option>
          {techs.map((t) => (
            <option key={t.id} value={t.id}>
              {t.display_name}
            </option>
          ))}
        </Select>
        <div className="relative">
          <Button
            variant="secondary"
            size="sm"
            className={cn(moreActive && "border-brand text-brand")}
            aria-expanded={moreOpen}
            aria-controls="dispatch-more-filters"
            onClick={() => setMoreOpen((v) => !v)}
          >
            <MoreHorizontal className="size-3.5" aria-hidden />
            More Filters
          </Button>
          {moreOpen ? (
            <>
              <button
                type="button"
                className="fixed inset-0 z-10 cursor-default"
                aria-label="Close more filters"
                onClick={() => setMoreOpen(false)}
              />
              <div
                id="dispatch-more-filters"
                className="absolute top-full left-0 z-20 mt-1 w-64 rounded-xl border border-border bg-surface p-3 shadow-[var(--shadow-elevated)]"
              >
                <div className="grid gap-2">
                  <Field label="Urgency">
                    <Select
                      className="h-8 text-xs"
                      value={urgencyFilter}
                      onChange={(e) => setUrgencyFilter(e.target.value)}
                    >
                      <option value="">Any</option>
                      <option value="overdue">Overdue</option>
                      <option value="today">Today</option>
                      <option value="upcoming">Upcoming</option>
                      <option value="none">Unscheduled</option>
                    </Select>
                  </Field>
                  <Field label="Area">
                    <Input
                      className="h-8 text-xs"
                      placeholder="Address contains…"
                      value={areaFilter}
                      onChange={(e) => setAreaFilter(e.target.value)}
                    />
                  </Field>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="justify-start"
                    onClick={() => {
                      setMoreOpen(false);
                      setTechDrawerOpen(true);
                    }}
                  >
                    Add technician…
                  </Button>
                </div>
              </div>
            </>
          ) : null}
        </div>
        <div className="ml-auto">
          <QuickFilterTabs
            views={[...SAVED_VIEWS]}
            value={savedView}
            onChange={setSavedView}
          />
        </div>
      </div>

      {fetching && jobs.length === 0 ? (
        <LoadingSkeleton rows={5} />
      ) : filteredJobs.length === 0 ? (
        <EmptyState
          className="py-10"
          icon={<LayoutGrid className="size-7" />}
          title={copy.noMatch}
          description={copy.noMatchHint}
          action={
            <Button size="sm" onClick={() => setJobDrawerOpen(true)}>
              Create job
            </Button>
          }
        />
      ) : (
        <KanbanBoard>
          {boardColumns.map((status) => {
            const columnJobs = filteredJobs.filter((j) => j.status === status);
            return (
              <KanbanColumn
                key={status}
                status={status}
                count={columnJobs.length}
              >
                {columnJobs.map((job) => (
                  <li key={job.id}>
                    <JobCard
                      job={job}
                      technicians={techs}
                      onPreview={setPreviewJob}
                      onAssign={onAssign}
                      onDispatch={onDispatch}
                      showAssign={
                        status === "new" ||
                        status === "scheduled" ||
                        status === "dispatched"
                      }
                      showDispatch={
                        status === "scheduled" && !!job.assigned_technician_id
                      }
                    />
                  </li>
                ))}
                {columnJobs.length === 0 ? (
                  <li className="px-1 py-4 text-center text-[11px] text-text-muted">
                    {copy.emptyStage}
                  </li>
                ) : null}
              </KanbanColumn>
            );
          })}
        </KanbanBoard>
      )}

      <DetailDrawer
        open={!!previewJob}
        onClose={() => setPreviewJob(null)}
        title={previewJob?.reference_code || "Job"}
        description={previewJob?.service_type}
        footer={
          previewJob ? (
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => setPreviewJob(null)}>
                Close
              </Button>
              <Link href={`/jobs/${previewJob.id}`} className="inline-flex">
                <Button>Open full detail</Button>
              </Link>
            </div>
          ) : null
        }
      >
        {previewJob ? (
          <div className="space-y-3 text-sm">
            <div className="flex items-center justify-between gap-2">
              <StatusPill status={previewJob.status} />
              <span className="text-xs text-text-muted">
                {formatWhen(previewJob.scheduled_starts_at)}
              </span>
            </div>
            <div>
              <p className="text-xs font-medium text-text-muted uppercase">
                Customer
              </p>
              <p className="font-medium">{previewJob.customer?.name || "—"}</p>
              {previewJob.customer?.address ? (
                <p className="text-text-secondary">
                  {previewJob.customer.address}
                </p>
              ) : null}
            </div>
            <div>
              <p className="text-xs font-medium text-text-muted uppercase">
                Technician
              </p>
              <p>
                {previewJob.assigned_technician?.display_name || "Unassigned"}
              </p>
            </div>
          </div>
        ) : null}
      </DetailDrawer>

      <DetailDrawer
        open={jobDrawerOpen}
        onClose={() => setJobDrawerOpen(false)}
        title="Create job"
        description="Create a new job for an existing customer."
        width="sm"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setJobDrawerOpen(false)}>
              Cancel
            </Button>
            <Button form="add-job-form" type="submit" disabled={formBusy}>
              {formBusy ? "Creating…" : "Create job"}
            </Button>
          </div>
        }
      >
        <form id="add-job-form" onSubmit={onCreateJob} className="grid gap-3">
          <Field label="Customer">
            <Select
              value={jobForm.customer_id}
              onChange={(e) =>
                setJobForm({ ...jobForm, customer_id: e.target.value })
              }
              required
            >
              <option value="">Select customer…</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Service type">
            <Input
              value={jobForm.service_type}
              onChange={(e) =>
                setJobForm({ ...jobForm, service_type: e.target.value })
              }
              required
              placeholder="e.g. AC repair"
            />
          </Field>
          <Field label="Scheduled start" hint="Optional">
            <Input
              type="datetime-local"
              value={jobForm.scheduled_starts_at}
              onChange={(e) =>
                setJobForm({
                  ...jobForm,
                  scheduled_starts_at: e.target.value,
                })
              }
            />
          </Field>
          {customers.length === 0 ? (
            <p className="text-xs text-text-muted">
              No customers yet. Create a customer before adding a job.
            </p>
          ) : null}
        </form>
      </DetailDrawer>

      <DetailDrawer
        open={techDrawerOpen}
        onClose={() => setTechDrawerOpen(false)}
        title="Add technician"
        description="Create a field technician account for your organization."
        width="sm"
        footer={
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              onClick={() => setTechDrawerOpen(false)}
            >
              Cancel
            </Button>
            <Button form="add-tech-form" type="submit" disabled={formBusy}>
              {formBusy ? "Creating…" : "Create"}
            </Button>
          </div>
        }
      >
        <form id="add-tech-form" onSubmit={onCreateTech} className="grid gap-3">
          <Field label="Name">
            <Input
              value={techForm.name}
              onChange={(e) =>
                setTechForm({ ...techForm, name: e.target.value })
              }
              required
            />
          </Field>
          <Field label="Email">
            <Input
              type="email"
              value={techForm.email}
              onChange={(e) =>
                setTechForm({ ...techForm, email: e.target.value })
              }
              required
            />
          </Field>
          <Field label="Password" hint="Minimum 8 characters">
            <Input
              type="password"
              value={techForm.password}
              onChange={(e) =>
                setTechForm({ ...techForm, password: e.target.value })
              }
              required
              minLength={8}
            />
          </Field>
          <Field label="Phone">
            <Input
              value={techForm.phone}
              onChange={(e) =>
                setTechForm({ ...techForm, phone: e.target.value })
              }
              placeholder="Optional"
            />
          </Field>
        </form>
      </DetailDrawer>
    </AppShell>
  );
}

export default function DispatchPage() {
  return (
    <Suspense
      fallback={
        <div className="p-6">
          <LoadingSkeleton rows={6} />
        </div>
      }
    >
      <DispatchWorkspace />
    </Suspense>
  );
}

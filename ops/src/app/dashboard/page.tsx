"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { CalendarPlus, Plus, UserPlus } from "lucide-react";
import { AppShell } from "@/components/shell";
import {
  ActivityFeed,
  AttentionList,
  Panel,
  SummaryStrip,
} from "@/components/ops/dashboard";
import {
  CallsBookingChart,
  JobsActivityChart,
  TechnicianWorkloadChart,
} from "@/components/ops/charts";
import {
  DistributionPieChart,
  colorForCallStatus,
  colorForJobStatus,
} from "@/components/ops/raffle-charts";
import type { DateRangeDays } from "@/components/ops/charts-shared";
import {
  buildDayBuckets,
  countByDay,
  inRange,
  isHandledCall,
  rangeStart,
} from "@/lib/chart-data";
import { useRouter } from "next/navigation";
import {
  Button,
  DetailDrawer,
  EmptyState,
  ErrorState,
  Field,
  Input,
  LoadingSkeleton,
  Select,
  StatusPill,
  useToast,
} from "@/components/ui";
import {
  createJob,
  formatWhen,
  listJobs,
  listTechnicians,
  type Job,
  type Technician,
} from "@/lib/api";
import { deriveUrgency } from "@/lib/schedule";
import { buildAttentionItems } from "@/lib/attention";
import { useAuth } from "@/lib/use-auth";
import { dashboard as copy, errors } from "@/lib/copy";
import { safeUserError } from "@/lib/safe-error";

const API =
  process.env.NEXT_PUBLIC_PLATFORM_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

type CustomerOption = { id: string; name: string };
type Appointment = {
  id: string;
  confirmation_code: string;
  status: string;
  service_type: string;
  starts_at?: string | null;
  ends_at?: string | null;
  customer_id: string;
};
type Call = {
  id: string;
  status: string;
  caller_number?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
};

function greetingFor(now: Date): string {
  const h = now.getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

function isSameDay(iso: string | null | undefined, day: Date): boolean {
  if (!iso) return false;
  const d = new Date(iso);
  return (
    d.getFullYear() === day.getFullYear() &&
    d.getMonth() === day.getMonth() &&
    d.getDate() === day.getDate()
  );
}

export default function DashboardPage() {
  const { user, loading } = useAuth({ roles: ["admin", "dispatcher"] });
  const router = useRouter();
  const toast = useToast();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [techs, setTechs] = useState<Technician[]>([]);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [calls, setCalls] = useState<Call[]>([]);
  const [customers, setCustomers] = useState<CustomerOption[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [fetching, setFetching] = useState(true);
  const [chartRange, setChartRange] = useState<DateRangeDays>(7);
  const [jobDrawerOpen, setJobDrawerOpen] = useState(false);
  const [formBusy, setFormBusy] = useState(false);
  const [jobForm, setJobForm] = useState({
    customer_id: "",
    service_type: "",
    scheduled_starts_at: "",
  });
  const now = useMemo(() => new Date(), []);

  const load = useCallback(async () => {
    const [j, t, apptRes, callRes, custRes] = await Promise.all([
      listJobs(),
      listTechnicians(),
      fetch(`${API}/api/admin/appointments`, { credentials: "include" }),
      fetch(`${API}/api/admin/calls`, { credentials: "include" }),
      fetch(`${API}/api/admin/customers`, { credentials: "include" }),
    ]);
    setJobs(j.jobs);
    setTechs(t.technicians);
    if (apptRes.ok) {
      const d = await apptRes.json();
      setAppointments(d.appointments || []);
    }
    if (callRes.ok) {
      const d = await callRes.json();
      setCalls(d.calls || []);
    }
    if (custRes.ok) {
      const d = await custRes.json();
      setCustomers(
        ((d.customers || []) as { id: string; name: string }[]).map((c) => ({
          id: c.id,
          name: c.name,
        })),
      );
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
    const id = setInterval(() => {
      load().catch(() => undefined);
    }, 15000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [user, load]);

  const activeJobs = useMemo(
    () =>
      jobs.filter((j) =>
        ["new", "scheduled", "dispatched", "in_progress"].includes(j.status),
      ),
    [jobs],
  );

  const apptsToday = useMemo(
    () => appointments.filter((a) => isSameDay(a.starts_at, now)),
    [appointments, now],
  );

  const availableTechs = useMemo(
    () => techs.filter((t) => t.is_active),
    [techs],
  );

  const callsToday = useMemo(
    () => calls.filter((c) => isSameDay(c.started_at, now)),
    [calls, now],
  );

  const unassigned = useMemo(
    () => activeJobs.filter((j) => !j.assigned_technician_id),
    [activeJobs],
  );

  const overdue = useMemo(
    () =>
      activeJobs.filter((j) => deriveUrgency(j.scheduled_starts_at) === "overdue"),
    [activeJobs],
  );

  const attention = useMemo(() => {
    const base = buildAttentionItems({ jobs, technicians: techs });
    const items = base.map(({ tone: _tone, ...rest }) => rest);
    if (callsToday.length > 0) {
      items.push({
        id: "calls-today",
        title: "Calls today",
        count: callsToday.length,
        explanation: "Customer calls received today.",
        href: "/calls",
      });
    }
    return items;
  }, [jobs, techs, callsToday]);

  const todayWork = useMemo(() => {
    const rows: {
      id: string;
      kind: string;
      title: string;
      meta: string;
      when: string;
      href: string;
      status?: string;
    }[] = [];

    for (const a of apptsToday) {
      rows.push({
        id: `appt-${a.id}`,
        kind: "Appointment",
        title: a.service_type,
        meta: a.confirmation_code,
        when: formatWhen(a.starts_at),
        href: "/appointments",
        status: a.status,
      });
    }

    const todayJobs = activeJobs.filter(
      (j) =>
        deriveUrgency(j.scheduled_starts_at) === "today" ||
        deriveUrgency(j.scheduled_starts_at) === "overdue" ||
        j.status === "in_progress" ||
        j.status === "dispatched",
    );
    for (const j of todayJobs) {
      rows.push({
        id: `job-${j.id}`,
        kind: "Job",
        title: j.service_type,
        meta: [
          j.customer?.name,
          j.assigned_technician?.display_name || "Unassigned",
          j.customer?.address,
        ]
          .filter(Boolean)
          .join(" · "),
        when: formatWhen(j.scheduled_starts_at),
        href: `/jobs/${j.id}`,
        status: j.status,
      });
    }

    return rows.slice(0, 8);
  }, [apptsToday, activeJobs]);

  const activity = useMemo(() => {
    const items: {
      id: string;
      title: string;
      detail?: string;
      time?: string | null;
      sort: number;
    }[] = [];

    for (const j of jobs) {
      if (j.created_at) {
        items.push({
          id: `created-${j.id}`,
          title: `Job created · ${j.reference_code}`,
          detail: j.service_type,
          time: formatWhen(j.created_at),
          sort: new Date(j.created_at).getTime(),
        });
      }
      if (j.assigned_technician && j.updated_at) {
        items.push({
          id: `assigned-${j.id}-${j.updated_at}`,
          title: `Assigned · ${j.reference_code}`,
          detail: j.assigned_technician.display_name,
          time: formatWhen(j.updated_at),
          sort: new Date(j.updated_at).getTime(),
        });
      }
      if (j.status === "completed" && j.updated_at) {
        items.push({
          id: `completed-${j.id}`,
          title: `Completed · ${j.reference_code}`,
          detail: j.service_type,
          time: formatWhen(j.updated_at),
          sort: new Date(j.updated_at).getTime(),
        });
      }
    }

    for (const c of calls) {
      if (c.ended_at) {
        items.push({
          id: `call-${c.id}`,
          title: `Call ended · ${c.status}`,
          detail: c.caller_number || undefined,
          time: formatWhen(c.ended_at),
          sort: new Date(c.ended_at).getTime(),
        });
      } else if (c.started_at) {
        items.push({
          id: `call-start-${c.id}`,
          title: `Call started · ${c.status}`,
          detail: c.caller_number || undefined,
          time: formatWhen(c.started_at),
          sort: new Date(c.started_at).getTime(),
        });
      }
    }

    for (const a of appointments) {
      if (a.starts_at) {
        items.push({
          id: `appt-act-${a.id}`,
          title: `Appointment · ${a.confirmation_code}`,
          detail: a.service_type,
          time: formatWhen(a.starts_at),
          sort: new Date(a.starts_at).getTime(),
        });
      }
    }

    return items
      .sort((a, b) => b.sort - a.sort)
      .slice(0, 10)
      .map(({ id, title, detail, time }) => ({ id, title, detail, time }));
  }, [jobs, calls, appointments]);

  const jobsActivitySeries = useMemo(() => {
    const buckets = buildDayBuckets(chartRange, now);
    const created = countByDay(
      jobs.map((j) => j.created_at),
      buckets,
    );
    const completed = countByDay(
      jobs
        .filter((j) => j.status === "completed")
        .map((j) => j.updated_at),
      buckets,
    );
    return buckets.map((b, i) => ({
      label: b.label,
      created: created[i] ?? 0,
      completed: completed[i] ?? 0,
    }));
  }, [jobs, chartRange, now]);

  const callsBookingSeries = useMemo(() => {
    const buckets = buildDayBuckets(chartRange, now);
    const callsByDay = countByDay(
      calls.map((c) => c.started_at),
      buckets,
    );
    const endedByDay = countByDay(
      calls.filter((c) => isHandledCall(c)).map((c) => c.ended_at || c.started_at),
      buckets,
    );
    const apptsByDay = countByDay(
      appointments.map((a) => a.starts_at),
      buckets,
    );

    return buckets.map((b, i) => ({
      label: b.label,
      calls: callsByDay[i] ?? 0,
      ended: endedByDay[i] ?? 0,
      appointments: apptsByDay[i] ?? 0,
    }));
  }, [calls, appointments, chartRange, now]);

  const technicianWorkload = useMemo(() => {
    const rows = techs.map((t) => {
      const assigned = jobs.filter((j) => j.assigned_technician_id === t.id);
      const active = assigned.filter(
        (j) => !["completed", "canceled"].includes(j.status),
      );
      return {
        name: t.display_name,
        assigned: assigned.length,
        active: active.length,
      };
    });
    return rows
      .filter((r) => r.assigned > 0 || r.active > 0)
      .sort((a, b) => b.active - a.active || b.assigned - a.assigned)
      .slice(0, 6);
  }, [techs, jobs]);

  const jobsByStatusPie = useMemo(() => {
    const start = rangeStart(chartRange, now);
    const end = now;
    const counts = new Map<string, number>();
    for (const j of jobs) {
      const ts = j.created_at || j.updated_at;
      if (!inRange(ts, start, end)) continue;
      counts.set(j.status, (counts.get(j.status) || 0) + 1);
    }
    return Array.from(counts.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([status, value]) => ({
        name: status.replace(/_/g, " "),
        status,
        value,
        color: colorForJobStatus(status),
      }));
  }, [jobs, chartRange, now]);

  const callsByStatusPie = useMemo(() => {
    const start = rangeStart(chartRange, now);
    const end = now;
    const counts = new Map<string, number>();
    for (const c of calls) {
      if (!inRange(c.started_at, start, end)) continue;
      const key = (c.status || "unknown").toLowerCase();
      counts.set(key, (counts.get(key) || 0) + 1);
    }
    return Array.from(counts.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([status, value]) => ({
        name: status.replace(/_/g, " "),
        status,
        value,
        color: colorForCallStatus(status),
      }));
  }, [calls, chartRange, now]);

  if (loading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={8} />
      </div>
    );
  }

  async function onCreateJob(e: React.FormEvent) {
    e.preventDefault();
    setFormBusy(true);
    setError(null);
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
      await load();
      toast.push("Job created", "success");
    } catch (err) {
      setError(safeUserError(err, errors.createFailed));
    } finally {
      setFormBusy(false);
    }
  }

  return (
    <AppShell user={user}>
      <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm text-text-secondary">
            {greetingFor(now)}, {user.name.split(" ")[0]}
          </p>
          <h1 className="mt-0.5 font-heading text-3xl font-semibold tracking-tight text-text-primary">
            {user.tenant_name}
          </h1>
          <p className="mt-1 text-sm text-text-secondary">
            {copy.attentionLead}
          </p>
          <p className="mt-1 text-sm text-text-muted">
            {activeJobs.length} active job
            {activeJobs.length === 1 ? "" : "s"} ·{" "}
            {now.toLocaleDateString(undefined, {
              weekday: "long",
              month: "short",
              day: "numeric",
            })}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/customers">
            <Button variant="secondary" size="sm">
              <UserPlus className="size-3.5" aria-hidden />
              Add customer
            </Button>
          </Link>
          <Link href="/appointments">
            <Button variant="secondary" size="sm">
              <CalendarPlus className="size-3.5" aria-hidden />
              Schedule
            </Button>
          </Link>
          <Button size="sm" onClick={() => setJobDrawerOpen(true)}>
            <Plus className="size-3.5" aria-hidden />
            Create job
          </Button>
        </div>
      </header>

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

      {fetching && jobs.length === 0 ? (
        <LoadingSkeleton rows={6} />
      ) : (
        <div className="grid gap-4">
          <SummaryStrip
            items={[
              { label: copy.activeJobs, value: activeJobs.length },
              { label: copy.appointmentsToday, value: apptsToday.length },
              {
                label: copy.availableTechnicians,
                value: availableTechs.length,
              },
              { label: copy.callsToday, value: callsToday.length },
            ]}
          />

          <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
            <Panel title={copy.needsAttention}>
              <AttentionList items={attention} />
            </Panel>

            <Panel
              title={copy.todaysSchedule}
              action={
                <Link
                  href="/dispatch?view=today"
                  className="text-xs font-medium text-brand hover:underline"
                >
                  {copy.viewAll}
                </Link>
              }
            >
              {todayWork.length === 0 ? (
                <EmptyState
                  className="border-0 py-6"
                  title={copy.noWorkToday}
                  description={copy.noWorkHint}
                />
              ) : (
                <ul className="divide-y divide-border">
                  {todayWork.map((row) => (
                    <li key={row.id}>
                      <Link
                        href={row.href}
                        className="flex items-start justify-between gap-3 py-2.5 transition-colors duration-150 hover:bg-surface-muted/50"
                      >
                        <div className="min-w-0">
                          <p className="text-[10px] font-medium tracking-wide text-text-muted uppercase">
                            {row.kind}
                          </p>
                          <p className="text-sm font-medium text-text-primary">
                            {row.title}
                          </p>
                          <p className="truncate text-xs text-text-secondary">
                            {row.meta}
                          </p>
                        </div>
                        <div className="shrink-0 text-right">
                          {row.status ? (
                            <StatusPill status={row.status} />
                          ) : null}
                          <p className="mt-1 font-mono text-[10px] text-text-muted">
                            {row.when}
                          </p>
                        </div>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <JobsActivityChart
              data={jobsActivitySeries}
              rangeDays={chartRange}
              onRangeChange={setChartRange}
              loading={fetching && jobs.length === 0}
            />
            <CallsBookingChart
              data={callsBookingSeries}
              rangeDays={chartRange}
              onRangeChange={setChartRange}
              loading={fetching && jobs.length === 0}
            />
          </div>

          <TechnicianWorkloadChart
            data={technicianWorkload}
            loading={fetching && jobs.length === 0}
          />

          <div className="grid gap-4 lg:grid-cols-2">
            <DistributionPieChart
              title="Jobs by status"
              description={`Job mix for the last ${chartRange} days. Click a slice to open dispatch.`}
              data={jobsByStatusPie}
              loading={fetching && jobs.length === 0}
              onSliceClick={(point) => {
                const status = point.status || point.name.replace(/ /g, "_");
                router.push(`/dispatch?status=${encodeURIComponent(status)}`);
              }}
            />
            <DistributionPieChart
              title="Calls by status"
              description={`Call outcomes for the last ${chartRange} days. Click a slice to open the call log.`}
              data={callsByStatusPie}
              loading={fetching && jobs.length === 0}
              emptyMessage="No call status data is available for this period."
              onSliceClick={(point) => {
                const status = point.status || point.name.replace(/ /g, "_");
                router.push(`/calls?status=${encodeURIComponent(status)}`);
              }}
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
            <Panel title={copy.recentActivity}>
              <ActivityFeed items={activity} />
            </Panel>
            <Panel title="Quick links">
              <div className="flex flex-wrap gap-2">
                <Link
                  href="/dispatch"
                  className="rounded-[10px] border border-border px-3 py-2 text-sm text-text-primary hover:bg-surface-muted"
                >
                  Open dispatch
                </Link>
                <Link
                  href="/metrics"
                  className="rounded-[10px] border border-border px-3 py-2 text-sm text-text-primary hover:bg-surface-muted"
                >
                  View metrics
                </Link>
                <Link
                  href="/calls"
                  className="rounded-[10px] border border-border px-3 py-2 text-sm text-text-primary hover:bg-surface-muted"
                >
                  Call log
                </Link>
              </div>
            </Panel>
          </div>
        </div>
      )}

      <DetailDrawer
        open={jobDrawerOpen}
        onClose={() => setJobDrawerOpen(false)}
        title="Create job"
        description="Creates a new job for an existing customer."
        width="sm"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setJobDrawerOpen(false)}>
              Cancel
            </Button>
            <Button form="dash-job-form" type="submit" disabled={formBusy}>
              {formBusy ? "Creating…" : "Create"}
            </Button>
          </div>
        }
      >
        <form id="dash-job-form" onSubmit={onCreateJob} className="grid gap-3">
          <Field label="Customer">
            <Select
              value={jobForm.customer_id}
              onChange={(e) =>
                setJobForm({ ...jobForm, customer_id: e.target.value })
              }
              required
            >
              <option value="">Select…</option>
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
        </form>
      </DetailDrawer>
    </AppShell>
  );
}

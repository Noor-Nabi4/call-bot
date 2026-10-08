"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { DateRangeDays } from "@/components/ops/charts-shared";
import {
  colorForCallStatus,
  colorForJobStatus,
} from "@/components/ops/raffle-charts";
import {
  buildDayBuckets,
  countByDay,
  inRange,
  isHandledCall,
  rangeStart,
} from "@/lib/chart-data";
import {
  createJob,
  formatWhen,
  listAppointments,
  listCalls,
  listCustomers,
  listJobs,
  listTechnicians,
} from "@/lib/api";
import { getInventoryDashboard } from "@/lib/api/inventory";
import {
  getAdminMetrics,
  type AdminMetrics,
} from "@/lib/api/metrics";
import { JOB_TERMINAL_STATUSES } from "@/lib/api/job-constants";
import { buildAttentionItems } from "@/lib/attention";
import { deriveUrgency } from "@/lib/schedule";
import { errors } from "@/lib/ops-copy";
import { safeUserError } from "@/lib/safe-error";
import type {
  Appointment,
  Call,
  CustomerOption,
  Job,
  OpsUser,
  Technician,
} from "@/types";
import {
  EMPTY_JOB_FORM,
  type CreateJobForm,
} from "@/components/ops/create-job-drawer";

function isSameDay(iso: string | null | undefined, day: Date): boolean {
  if (!iso) return false;
  const d = new Date(iso);
  return (
    d.getFullYear() === day.getFullYear() &&
    d.getMonth() === day.getMonth() &&
    d.getDate() === day.getDate()
  );
}

export function useDashboardData(user: OpsUser | null) {
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
  const [jobForm, setJobForm] = useState<CreateJobForm>(EMPTY_JOB_FORM);
  const [inventoryLow, setInventoryLow] = useState(0);
  const [inventoryOut, setInventoryOut] = useState(0);
  const [metrics, setMetrics] = useState<AdminMetrics | null>(null);
  const [metricsLoading, setMetricsLoading] = useState(true);
  const now = useMemo(() => new Date(), []);

  const load = useCallback(async () => {
    const [j, t, appts, callData, custs, invDash, adminMetrics] =
      await Promise.all([
        listJobs(),
        listTechnicians(),
        listAppointments().catch(() => ({ appointments: [] as Appointment[] })),
        listCalls().catch(() => ({ calls: [] as Call[] })),
        listCustomers().catch(() => ({ customers: [] as CustomerOption[] })),
        getInventoryDashboard().catch(() => null),
        getAdminMetrics(chartRange).catch(() => null),
      ]);
    setJobs(j.jobs);
    setTechs(t.technicians);
    setAppointments(appts.appointments || []);
    setCalls(callData.calls || []);
    setCustomers(custs.customers || []);
    setInventoryLow(invDash?.low_stock_balances ?? 0);
    setInventoryOut(invDash?.out_of_stock_balances ?? 0);
    setMetrics(adminMetrics);
    setMetricsLoading(false);
  }, [chartRange]);

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
        ["NEW", "SCHEDULED", "DISPATCHED", "IN_PROGRESS"].includes(j.status),
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

  const attention = useMemo(() => {
    const base = buildAttentionItems({ jobs, technicians: techs });
    const items = base.map(({ tone: _, ...rest }) => {
      void _;
      return rest;
    });
    if (callsToday.length > 0) {
      items.push({
        id: "calls-today",
        title: "Calls today",
        count: callsToday.length,
        explanation: "Customer calls received today.",
        href: "/calls",
      });
    }
    if (inventoryOut > 0) {
      items.push({
        id: "inventory-out",
        title: "Out of stock",
        count: inventoryOut,
        explanation: "Inventory balances with zero available quantity.",
        href: "/crm/inventory?out_of_stock=true",
      });
    }
    if (inventoryLow > 0) {
      items.push({
        id: "inventory-low",
        title: "Low stock",
        count: inventoryLow,
        explanation: "Inventory at or below minimum threshold.",
        href: "/crm/inventory?low_stock=true",
      });
    }
    return items;
  }, [jobs, techs, callsToday, inventoryLow, inventoryOut]);

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
        j.status === "IN_PROGRESS" ||
        j.status === "DISPATCHED",
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
      if (j.status === "COMPLETED" && j.updated_at) {
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
        .filter((j) => j.status === "COMPLETED")
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
        (j) => !JOB_TERMINAL_STATUSES.has(j.status),
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

  async function onCreateJob(
    e: React.FormEvent,
    onSuccess: (message: string) => void,
  ) {
    e.preventDefault();
    setFormBusy(true);
    setError(null);
    try {
      await createJob({
        customer_id: jobForm.customer_id,
        service_type: jobForm.service_type,
        status: "NEW",
        scheduled_starts_at: jobForm.scheduled_starts_at
          ? new Date(jobForm.scheduled_starts_at).toISOString()
          : null,
      });
      setJobForm(EMPTY_JOB_FORM);
      setJobDrawerOpen(false);
      await load();
      onSuccess("Job created");
    } catch (err) {
      setError(safeUserError(err, errors.createFailed));
    } finally {
      setFormBusy(false);
    }
  }

  function retryLoad() {
    setError(null);
    setFetching(true);
    setMetricsLoading(true);
    load()
      .catch((e) => setError(safeUserError(e, errors.loadFailed)))
      .finally(() => setFetching(false));
  }

  const leadFunnel = useMemo(() => {
    // Actual LeadStatus values from the CRM model (not invented).
    const order = ["NEW", "CONTACTED", "QUALIFIED", "BOOKED", "WON", "LOST"];
    const byStatus = metrics?.leads_by_status || {};
    const hasAny = Object.values(byStatus).some((n) => n > 0);
    if (!hasAny) return [];
    return order.map((status) => ({
      name: status.replace(/_/g, " "),
      status,
      value: byStatus[status] || 0,
    }));
  }, [metrics]);

  const revenueSeries = useMemo(() => {
    if (!metrics?.revenue_by_day?.length) return [];
    return metrics.revenue_by_day.map((d) => ({
      label: d.date.slice(5),
      revenue: d.revenue,
    }));
  }, [metrics]);

  const metricsCallsSeries = useMemo(() => {
    if (!metrics?.calls_by_day?.length) return [];
    return metrics.calls_by_day.map((d) => ({
      label: d.date.slice(5),
      calls: d.calls,
    }));
  }, [metrics]);

  return {
    jobs,
    customers,
    error,
    fetching,
    chartRange,
    setChartRange,
    jobDrawerOpen,
    setJobDrawerOpen,
    formBusy,
    jobForm,
    setJobForm,
    now,
    activeJobs,
    apptsToday,
    availableTechs,
    callsToday,
    attention,
    todayWork,
    activity,
    jobsActivitySeries,
    callsBookingSeries,
    technicianWorkload,
    jobsByStatusPie,
    callsByStatusPie,
    onCreateJob,
    retryLoad,
    inventoryLow,
    inventoryOut,
    metrics,
    metricsLoading,
    leadFunnel,
    revenueSeries,
    metricsCallsSeries,
  };
}

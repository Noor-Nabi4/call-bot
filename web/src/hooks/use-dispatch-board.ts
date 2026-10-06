"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  assignJob,
  createJob,
  createTechnician,
  listCustomers,
  listJobs,
  listTechnicians,
  transitionJob,
} from "@/lib/api";
import { deriveUrgency } from "@/lib/schedule";
import { errors } from "@/lib/ops-copy";
import { safeUserError } from "@/lib/safe-error";
import type { CustomerOption, Job, OpsUser, Technician } from "@/types";
import {
  EMPTY_JOB_FORM,
  type CreateJobForm,
} from "@/components/ops/create-job-drawer";
import {
  EMPTY_TECH_FORM,
  type CreateTechForm,
} from "@/components/ops/create-tech-drawer";
import { JOB_TERMINAL_STATUSES } from "@/lib/api/job-constants";

export const DISPATCH_COLUMNS = [
  "NEW",
  "SCHEDULED",
  "DISPATCHED",
  "IN_PROGRESS",
  "COMPLETED",
] as const;

export const DISPATCH_SAVED_VIEWS = [
  { id: "all", label: "All" },
  { id: "unassigned", label: "Unassigned" },
  { id: "today", label: "Today" },
  { id: "overdue", label: "Overdue" },
] as const;

const SAVED_VIEW_IDS = new Set<string>(
  DISPATCH_SAVED_VIEWS.map((v) => v.id),
);

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
  return !JOB_TERMINAL_STATUSES.has(job.status);
}

export function useDispatchBoard(user: OpsUser | null) {
  const searchParams = useSearchParams();
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
  const statusFilter = (searchParams.get("status") || "").toUpperCase().trim();
  const [moreOpen, setMoreOpen] = useState(false);
  const [previewJob, setPreviewJob] = useState<Job | null>(null);
  const [jobDrawerOpen, setJobDrawerOpen] = useState(false);
  const [techDrawerOpen, setTechDrawerOpen] = useState(false);
  const [jobForm, setJobForm] = useState<CreateJobForm>(EMPTY_JOB_FORM);
  const [techForm, setTechForm] = useState<CreateTechForm>(EMPTY_TECH_FORM);
  const [formBusy, setFormBusy] = useState(false);

  const refresh = useCallback(async () => {
    const [j, t] = await Promise.all([listJobs(), listTechnicians()]);
    setJobs(j.jobs);
    setTechs(t.technicians);
  }, []);

  const loadCustomers = useCallback(async () => {
    try {
      const data = await listCustomers();
      setCustomers(data.customers || []);
    } catch {
      /* soft-fail — create job drawer can still open empty */
    }
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
      if (statusFilter && job.status.toUpperCase() !== statusFilter) return false;
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
      !(DISPATCH_COLUMNS as readonly string[]).includes(statusFilter)
    ) {
      return [...DISPATCH_COLUMNS, statusFilter] as string[];
    }
    return [...DISPATCH_COLUMNS] as string[];
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

  async function onAssign(
    jobId: string,
    technicianId: string,
    onSuccess: (msg: string) => void,
  ) {
    setError(null);
    try {
      await assignJob(jobId, technicianId);
      await refresh();
      onSuccess("Technician assigned");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Assign failed");
    }
  }

  async function onDispatch(
    jobId: string,
    onSuccess: (msg: string) => void,
  ) {
    setError(null);
    try {
      await transitionJob(jobId, "DISPATCHED");
      await refresh();
      onSuccess("Job dispatched");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Dispatch failed");
    }
  }

  async function onCreateJob(
    e: React.FormEvent,
    onSuccess: (msg: string) => void,
  ) {
    e.preventDefault();
    setError(null);
    setFormBusy(true);
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
      await refresh();
      onSuccess("Job created");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create job failed");
    } finally {
      setFormBusy(false);
    }
  }

  async function onCreateTech(
    e: React.FormEvent,
    onSuccess: (msg: string) => void,
  ) {
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
      setTechForm(EMPTY_TECH_FORM);
      setTechDrawerOpen(false);
      await refresh();
      onSuccess("Technician created");
    } catch (err) {
      setError(safeUserError(err, errors.createFailed));
    } finally {
      setFormBusy(false);
    }
  }

  return {
    jobs,
    techs,
    customers,
    error,
    setError,
    fetching,
    search,
    setSearch,
    dateFilter,
    setDateFilter,
    techFilter,
    setTechFilter,
    urgencyFilter,
    setUrgencyFilter,
    areaFilter,
    setAreaFilter,
    savedView,
    setSavedView,
    statusFilter,
    moreOpen,
    setMoreOpen,
    previewJob,
    setPreviewJob,
    jobDrawerOpen,
    setJobDrawerOpen,
    techDrawerOpen,
    setTechDrawerOpen,
    jobForm,
    setJobForm,
    techForm,
    setTechForm,
    formBusy,
    refresh,
    activeJobCount,
    filteredJobs,
    boardColumns,
    statusCounts,
    moreActive,
    onAssign,
    onDispatch,
    onCreateJob,
    onCreateTech,
  };
}

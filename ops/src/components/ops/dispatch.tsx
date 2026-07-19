"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { StatusPill, TechnicianAvatar, urgencyEdgeClass } from "@/components/ui";
import { formatWhen, type Job, type Technician } from "@/lib/api";
import { Select } from "@/components/ui";
import { jobStatusLabels } from "@/lib/copy";

export function StatusStrip({
  columns,
  counts,
  className,
}: {
  columns: readonly string[];
  counts: Record<string, number>;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-border pb-2 text-sm",
        className,
      )}
      role="status"
      aria-label="Job counts by status"
    >
      {columns.map((status) => (
        <span key={status} className="inline-flex items-center gap-1.5">
          <span className="text-text-secondary">
            {jobStatusLabels[status] || status.replace(/_/g, " ")}
          </span>
          <span className="font-mono text-xs font-semibold tabular-nums text-text-primary">
            {counts[status] ?? 0}
          </span>
        </span>
      ))}
    </div>
  );
}

export function QuickFilterTabs({
  views,
  value,
  onChange,
}: {
  views: { id: string; label: string }[];
  value: string;
  onChange: (id: string) => void;
}) {
  return (
    <div
      className="inline-flex rounded-[10px] border border-border bg-surface-muted p-0.5"
      role="group"
      aria-label="Saved views"
    >
      {views.map((view) => (
        <button
          key={view.id}
          type="button"
          onClick={() => onChange(view.id)}
          className={cn(
            "rounded-md px-2.5 py-1 text-xs font-medium transition-colors duration-150",
            value === view.id
              ? "bg-surface text-text-primary shadow-sm"
              : "text-text-secondary hover:text-text-primary",
          )}
        >
          {view.label}
        </button>
      ))}
    </div>
  );
}

export function JobCard({
  job,
  technicians,
  onPreview,
  onAssign,
  onDispatch,
  showAssign,
  showDispatch,
}: {
  job: Job;
  technicians: Technician[];
  onPreview: (job: Job) => void;
  onAssign: (jobId: string, technicianId: string) => void;
  onDispatch: (jobId: string) => void;
  showAssign?: boolean;
  showDispatch?: boolean;
}) {
  return (
    <article
      className={cn(
        "rounded-[10px] border border-border border-l-2 bg-background p-2 text-xs transition-colors duration-150 hover:bg-surface-muted/80",
        urgencyEdgeClass(job.scheduled_starts_at),
      )}
    >
      <button
        type="button"
        className="w-full text-left"
        onClick={() => onPreview(job)}
      >
        <div className="flex items-start justify-between gap-1">
          <p className="font-mono text-[10px] text-text-muted">
            {job.reference_code}
          </p>
          <StatusPill status={job.status} className="scale-90 origin-right" />
        </div>
        <p className="mt-0.5 font-medium text-text-primary">{job.service_type}</p>
        <p className="text-text-secondary">{job.customer?.name || "Customer"}</p>
        <p className="mt-0.5 text-[10px] text-text-muted">
          {formatWhen(job.scheduled_starts_at)}
        </p>
        {job.customer?.address ? (
          <p className="mt-0.5 line-clamp-1 text-[10px] text-text-muted">
            {job.customer.address}
          </p>
        ) : null}
        <div className="mt-1 flex items-center gap-1 text-[10px] text-text-secondary">
          {job.assigned_technician ? (
            <>
              <TechnicianAvatar
                name={job.assigned_technician.display_name}
                size="sm"
              />
              <span className="truncate">
                {job.assigned_technician.display_name}
              </span>
            </>
          ) : (
            <span className="text-text-muted">Unassigned</span>
          )}
        </div>
      </button>

      {showAssign ? (
        <Select
          className="mt-1.5 h-7 text-[11px]"
          value={job.assigned_technician_id || ""}
          onChange={(e) => {
            if (e.target.value) onAssign(job.id, e.target.value);
          }}
          aria-label={`Assign ${job.reference_code}`}
        >
          <option value="">Assign…</option>
          {technicians.map((t) => (
            <option key={t.id} value={t.id}>
              {t.display_name}
            </option>
          ))}
        </Select>
      ) : null}
      {showDispatch ? (
        <button
          type="button"
          className="mt-1.5 h-7 w-full rounded-[10px] bg-brand text-[11px] font-medium text-white transition-colors duration-150 hover:bg-brand-hover"
          onClick={() => onDispatch(job.id)}
        >
          Dispatch
        </button>
      ) : null}
    </article>
  );
}

export function KanbanColumn({
  status,
  count,
  children,
}: {
  status: string;
  count: number;
  children: ReactNode;
}) {
  return (
    <section
      className="glass-panel flex w-[13.5rem] shrink-0 flex-col"
      aria-label={`${jobStatusLabels[status] || status.replace(/_/g, " ")} column`}
    >
      <header className="sticky top-0 z-10 flex items-center justify-between gap-2 border-b border-border bg-surface px-2.5 py-2">
        <span className="flex items-center gap-1.5 text-xs font-semibold tracking-wide text-text-secondary">
          <span
            className={cn(
              "size-1.5 rounded-full",
              status === "new" && "bg-text-muted",
              status === "scheduled" && "bg-brand",
              status === "dispatched" && "bg-warn",
              status === "in_progress" && "bg-warn",
              status === "completed" && "bg-brand",
            )}
            aria-hidden
          />
          {jobStatusLabels[status] || status.replace(/_/g, " ")}
        </span>
        <span className="font-mono text-[11px] tabular-nums text-text-muted">
          {count}
        </span>
      </header>
      <ul className="flex-1 space-y-1.5 overflow-y-auto p-1.5">{children}</ul>
    </section>
  );
}

export function KanbanBoard({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("-mx-4 overflow-x-auto px-4 sm:-mx-6 sm:px-6", className)}>
      <div className="flex min-h-[calc(100vh-13rem)] min-w-[68rem] gap-2 pb-2">
        {children}
      </div>
    </div>
  );
}

"use client";

import { cn } from "@/lib/cn";
import { deriveUrgency } from "@/lib/schedule";

const tones: Record<string, string> = {
  new: "bg-surface-muted text-text-secondary",
  scheduled: "bg-brand-soft text-brand",
  dispatched: "bg-warn-soft text-warn",
  in_progress: "bg-warn-soft text-warn",
  completed: "bg-success-soft text-success",
  canceled: "bg-danger-soft text-danger",
  cancelled: "bg-danger-soft text-danger",
  active: "bg-brand-soft text-brand",
  trialing: "bg-blue-soft text-blue",
  past_due: "bg-warn-soft text-warn",
  unpaid: "bg-danger-soft text-danger",
  incomplete: "bg-warn-soft text-warn",
  incomplete_expired: "bg-danger-soft text-danger",
  inactive: "bg-surface-muted text-text-muted",
  ready: "bg-success-soft text-success",
  needs_attention: "bg-warn-soft text-warn",
  connected: "bg-success-soft text-success",
  failed: "bg-danger-soft text-danger",
  pending: "bg-warn-soft text-warn",
  verified: "bg-success-soft text-success",
  warm: "bg-brand-soft text-brand",
  cold: "bg-surface-muted text-text-secondary",
};

export function StatusPill({
  status,
  className,
}: {
  status: string;
  className?: string;
}) {
  const key = status.toLowerCase().replace(/\s+/g, "_");
  return (
    <span
      className={cn(
        "status-pill",
        tones[key] || "bg-surface-muted text-text-secondary",
        className,
      )}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}

/** Schedule urgency derived from real scheduled_starts_at — not a stored priority field. */
export function PriorityIndicator({
  scheduledStartsAt,
  className,
}: {
  scheduledStartsAt?: string | null;
  className?: string;
}) {
  const urgency = deriveUrgency(scheduledStartsAt);
  const colors = {
    overdue: "bg-danger",
    today: "bg-warn",
    upcoming: "bg-brand",
    none: "bg-border-strong",
  };
  const labels = {
    overdue: "Overdue",
    today: "Today",
    upcoming: "Upcoming",
    none: "Unscheduled",
  };
  return (
    <span
      className={cn("inline-flex items-center gap-1.5", className)}
      title={labels[urgency]}
    >
      <span
        className={cn("h-full w-0.5 self-stretch rounded-full", colors[urgency])}
        aria-hidden
      />
      <span className="sr-only">Schedule: {labels[urgency]}</span>
    </span>
  );
}

export function urgencyEdgeClass(scheduledStartsAt?: string | null): string {
  const urgency = deriveUrgency(scheduledStartsAt);
  if (urgency === "overdue") return "border-l-danger";
  if (urgency === "today") return "border-l-warn";
  if (urgency === "upcoming") return "border-l-brand";
  return "border-l-border-strong";
}

"use client";

import { cn } from "@/lib/cn";
import { deriveUrgency } from "@/lib/schedule";

const tones: Record<string, string> = {
  new: "bg-white/5 text-text-secondary",
  scheduled: "bg-brand/20 text-cyan",
  dispatched: "bg-warn-soft text-warn",
  in_progress: "bg-warn-soft text-warn",
  completed: "bg-success-soft text-success",
  canceled: "bg-danger-soft text-danger",
  active: "bg-brand/20 text-cyan",
  inactive: "bg-white/5 text-text-muted",
  connected: "bg-success-soft text-success",
  failed: "bg-danger-soft text-danger",
  pending: "bg-warn-soft text-warn",
  verified: "bg-success-soft text-success",
  warm: "bg-brand/20 text-cyan",
  cold: "bg-white/5 text-text-secondary",
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

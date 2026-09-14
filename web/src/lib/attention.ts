/** Build ops attention notifications from live tenant records. */

import type { Job, Technician } from "@/lib/api";
import { deriveUrgency } from "@/lib/schedule";

export type AttentionItem = {
  id: string;
  title: string;
  count: number;
  explanation: string;
  href: string;
  tone: "urgent" | "warn" | "info";
};

const ACTIVE_STATUSES = new Set([
  "new",
  "scheduled",
  "dispatched",
  "in_progress",
]);

export function activeJobs(jobs: Job[]): Job[] {
  return jobs.filter((j) => ACTIVE_STATUSES.has(j.status));
}

export function buildAttentionItems(input: {
  jobs: Job[];
  technicians: Technician[];
  handoff?: {
    enabled: boolean;
    escalation_phone_e164?: string | null;
  } | null;
}): AttentionItem[] {
  const active = activeJobs(input.jobs);
  const unassigned = active.filter((j) => !j.assigned_technician_id);
  const overdue = active.filter(
    (j) => deriveUrgency(j.scheduled_starts_at) === "overdue",
  );
  const inactiveTechs = input.technicians.filter((t) => !t.is_active);

  const items: AttentionItem[] = [];

  if (unassigned.length > 0) {
    items.push({
      id: "unassigned",
      title: "Unassigned jobs",
      count: unassigned.length,
      explanation: "Active jobs waiting for a technician.",
      href: "/dispatch?view=unassigned",
      tone: "urgent",
    });
  }

  if (overdue.length > 0) {
    items.push({
      id: "overdue",
      title: "Overdue jobs",
      count: overdue.length,
      explanation: "Scheduled start time has passed.",
      href: "/dispatch?view=overdue",
      tone: "urgent",
    });
  }

  if (inactiveTechs.length > 0) {
    items.push({
      id: "inactive-techs",
      title: "Inactive technicians",
      count: inactiveTechs.length,
      explanation: "Technicians marked inactive for your organization.",
      href: "/dispatch",
      tone: "info",
    });
  }

  if (input.handoff) {
    if (!input.handoff.enabled) {
      items.push({
        id: "handoff-disabled",
        title: "Human handoff is off",
        count: 1,
        explanation: "Callers cannot be transferred to your team yet.",
        href: "/handoff",
        tone: "warn",
      });
    } else if (!input.handoff.escalation_phone_e164?.trim()) {
      items.push({
        id: "handoff-phone",
        title: "Handoff phone missing",
        count: 1,
        explanation: "Transfer is enabled but no escalation number is set.",
        href: "/handoff",
        tone: "urgent",
      });
    }
  }

  return items;
}

/** Badge count: only actionable work items (jobs), not config tips. */
export function attentionBadgeCount(items: AttentionItem[]): number {
  return items
    .filter((i) => i.id === "unassigned" || i.id === "overdue")
    .reduce((sum, i) => sum + i.count, 0);
}

export function buildJobAlerts(jobs: Job[], limit = 6): AttentionItem[] {
  const active = activeJobs(jobs);
  const alerts: AttentionItem[] = [];

  const overdue = active
    .filter((j) => deriveUrgency(j.scheduled_starts_at) === "overdue")
    .slice(0, limit);
  for (const job of overdue) {
    alerts.push({
      id: `job-overdue-${job.id}`,
      title: `${job.service_type} overdue`,
      count: 1,
      explanation: [
        job.customer?.name,
        job.reference_code,
        job.assigned_technician?.display_name || "Unassigned",
      ]
        .filter(Boolean)
        .join(" · "),
      href: `/jobs/${job.id}`,
      tone: "urgent",
    });
  }

  if (alerts.length >= limit) return alerts;

  const unassigned = active
    .filter(
      (j) =>
        !j.assigned_technician_id &&
        deriveUrgency(j.scheduled_starts_at) !== "overdue",
    )
    .slice(0, limit - alerts.length);
  for (const job of unassigned) {
    alerts.push({
      id: `job-unassigned-${job.id}`,
      title: `${job.service_type} unassigned`,
      count: 1,
      explanation: [job.customer?.name, job.reference_code]
        .filter(Boolean)
        .join(" · "),
      href: `/jobs/${job.id}`,
      tone: "warn",
    });
  }

  return alerts;
}

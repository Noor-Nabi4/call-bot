/**
 * Job (field service) lifecycle constants shared by UI and tests (no HTTP client).
 *
 * Mirrors the backend status enum in
 * `callbot_platform.crm.jobs.constants.JobStatus` (Phase 10). Values are
 * UPPERCASE — the backend normalizes any case on input but always returns
 * these canonical uppercase values, so the frontend must compare against
 * uppercase literals rather than the legacy lowercase strings used before
 * Phase 10.
 */

export type JobStatus =
  | "NEW"
  | "SCHEDULED"
  | "CONFIRMED"
  | "DISPATCHED"
  | "EN_ROUTE"
  | "ARRIVED"
  | "IN_PROGRESS"
  | "COMPLETED"
  | "CANCELLED"
  | "NO_SHOW";

export const JOB_STATUSES: JobStatus[] = [
  "NEW",
  "SCHEDULED",
  "CONFIRMED",
  "DISPATCHED",
  "EN_ROUTE",
  "ARRIVED",
  "IN_PROGRESS",
  "COMPLETED",
  "CANCELLED",
  "NO_SHOW",
];

/** Statuses that are terminal — no further transitions are possible. */
export const JOB_TERMINAL_STATUSES = new Set<string>([
  "COMPLETED",
  "CANCELLED",
  "NO_SHOW",
]);

/** Statuses considered "active" / in-flight work for dashboards and boards. */
export const JOB_ACTIVE_STATUSES = new Set<string>(
  JOB_STATUSES.filter((s) => !JOB_TERMINAL_STATUSES.has(s)),
);

/** Statuses a technician may be assigned to (mirrors ASSIGNABLE_STATUSES on the backend). */
export const JOB_ASSIGNABLE_STATUSES = new Set<string>([
  "NEW",
  "SCHEDULED",
  "CONFIRMED",
  "DISPATCHED",
]);

/** Forward transition graph — mirrors VALID_TRANSITIONS on the backend (excludes cancel/no-show). */
export const JOB_FORWARD_TRANSITIONS: Record<string, JobStatus[]> = {
  NEW: ["SCHEDULED"],
  SCHEDULED: ["CONFIRMED", "DISPATCHED"],
  CONFIRMED: ["DISPATCHED"],
  DISPATCHED: ["EN_ROUTE", "IN_PROGRESS"],
  EN_ROUTE: ["ARRIVED", "IN_PROGRESS"],
  ARRIVED: ["IN_PROGRESS"],
  IN_PROGRESS: ["COMPLETED"],
  COMPLETED: [],
  CANCELLED: [],
  NO_SHOW: [],
};

/** Statuses from which a job may still be cancelled. */
export const JOB_CANCELLABLE = new Set<string>([
  "NEW",
  "SCHEDULED",
  "CONFIRMED",
  "DISPATCHED",
  "EN_ROUTE",
  "ARRIVED",
  "IN_PROGRESS",
]);

export const JOB_STATUS_LABELS: Record<string, string> = {
  NEW: "New",
  SCHEDULED: "Scheduled",
  CONFIRMED: "Confirmed",
  DISPATCHED: "Dispatched",
  EN_ROUTE: "En route",
  ARRIVED: "Arrived",
  IN_PROGRESS: "In progress",
  COMPLETED: "Completed",
  CANCELLED: "Cancelled",
  NO_SHOW: "No show",
};

export function jobStatusLabel(status: string): string {
  return JOB_STATUS_LABELS[status.toUpperCase()] || status.replace(/_/g, " ");
}

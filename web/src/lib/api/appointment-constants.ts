/**
 * Appointment lifecycle constants (Phase 11).
 * Mirrors callbot_platform.crm.appointments.constants — UPPERCASE canonical values.
 */

export type AppointmentStatus =
  | "TENTATIVE"
  | "SCHEDULED"
  | "CONFIRMED"
  | "IN_PROGRESS"
  | "COMPLETED"
  | "CANCELLED"
  | "NO_SHOW";

export const APPOINTMENT_STATUSES: AppointmentStatus[] = [
  "TENTATIVE",
  "SCHEDULED",
  "CONFIRMED",
  "IN_PROGRESS",
  "COMPLETED",
  "CANCELLED",
  "NO_SHOW",
];

export const APPOINTMENT_TERMINAL = new Set<string>([
  "COMPLETED",
  "CANCELLED",
  "NO_SHOW",
]);

export const APPOINTMENT_FORWARD: Record<string, AppointmentStatus[]> = {
  TENTATIVE: ["SCHEDULED", "CONFIRMED"],
  SCHEDULED: ["CONFIRMED", "IN_PROGRESS"],
  CONFIRMED: ["IN_PROGRESS"],
  IN_PROGRESS: ["COMPLETED"],
  COMPLETED: [],
  CANCELLED: [],
  NO_SHOW: [],
};

export const APPOINTMENT_CANCELLABLE = new Set<string>([
  "TENTATIVE",
  "SCHEDULED",
  "CONFIRMED",
  "IN_PROGRESS",
]);

export const APPOINTMENT_STATUS_LABELS: Record<string, string> = {
  TENTATIVE: "Tentative",
  SCHEDULED: "Scheduled",
  CONFIRMED: "Confirmed",
  IN_PROGRESS: "In progress",
  COMPLETED: "Completed",
  CANCELLED: "Cancelled",
  NO_SHOW: "No show",
};

export function appointmentStatusLabel(status: string): string {
  const key = status.toUpperCase().replace(/-/g, "_");
  return APPOINTMENT_STATUS_LABELS[key] || status.replace(/_/g, " ");
}

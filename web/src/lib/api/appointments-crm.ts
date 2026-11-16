/** Typed helpers for Appointment CRM APIs (Phase 11, `/api/admin/crm`). */

import { api } from "./client";
export type { AppointmentStatus } from "./appointment-constants";
export {
  APPOINTMENT_CANCELLABLE,
  APPOINTMENT_FORWARD,
  APPOINTMENT_STATUSES,
  APPOINTMENT_STATUS_LABELS,
  APPOINTMENT_TERMINAL,
  appointmentStatusLabel,
} from "./appointment-constants";

export type AppointmentRow = {
  id: string;
  appointment_number: string;
  confirmation_code?: string | null;
  status: string;
  priority?: string | null;
  is_emergency?: boolean;
  service_type: string;
  starts_at?: string | null;
  ends_at?: string | null;
  duration_minutes?: number | null;
  timezone?: string | null;
  notes?: string | null;
  customer_id: string;
  customer?: { id: string; name?: string | null; display_name?: string | null } | null;
  location_id?: string | null;
  location?: { id: string; address_line_1?: string | null; city?: string | null } | null;
  service_id?: string | null;
  service?: { id: string; name?: string | null; duration_minutes?: number | null } | null;
  job_id?: string | null;
  assigned_technician_id?: string | null;
  assigned_technician?: { id: string; display_name: string } | null;
  archived_at?: string | null;
  cancelled_at?: string | null;
  completed_at?: string | null;
  created_at?: string | null;
};

export type AppointmentHistoryRow = {
  id: string;
  from_status?: string | null;
  to_status: string;
  changed_by?: string | null;
  reason?: string | null;
  created_at?: string | null;
};

export type AvailabilitySlot = {
  starts_at: string;
  ends_at: string;
  local_start?: string | null;
  local_end?: string | null;
  technician_id?: string | null;
  technician_name?: string | null;
};

export type AvailabilityResult = {
  timezone: string;
  duration_minutes: number;
  is_emergency?: boolean;
  slots: AvailabilitySlot[];
};

export async function listCrmAppointments(params: {
  q?: string;
  status?: string;
  customer_id?: string;
  technician_id?: string;
  service_id?: string;
  starts_from?: string;
  starts_to?: string;
  limit?: number;
  cursor?: string;
  include_archived?: boolean;
}): Promise<{
  appointments: AppointmentRow[];
  next_cursor?: string | null;
  limit: number;
}> {
  const sp = new URLSearchParams();
  if (params.q) sp.set("q", params.q);
  if (params.status) sp.set("status", params.status);
  if (params.customer_id) sp.set("customer_id", params.customer_id);
  if (params.technician_id) sp.set("technician_id", params.technician_id);
  if (params.service_id) sp.set("service_id", params.service_id);
  if (params.starts_from) sp.set("starts_from", params.starts_from);
  if (params.starts_to) sp.set("starts_to", params.starts_to);
  if (params.limit) sp.set("limit", String(params.limit));
  if (params.cursor) sp.set("cursor", params.cursor);
  if (params.include_archived) sp.set("include_archived", "true");
  const qs = sp.toString();
  return api(`/api/admin/crm/appointments${qs ? `?${qs}` : ""}`);
}

export async function getCrmAppointment(id: string): Promise<AppointmentRow> {
  const res = await api<{ appointment: AppointmentRow }>(
    `/api/admin/crm/appointments/${id}`,
  );
  return res.appointment;
}

export async function createCrmAppointment(body: {
  customer_id: string;
  starts_at: string;
  ends_at?: string;
  duration_minutes?: number;
  service_id?: string;
  location_id?: string;
  technician_id?: string | null;
  job_id?: string;
  priority?: string;
  is_emergency?: boolean;
  notes?: string;
  status?: string;
  idempotency_key?: string;
}): Promise<AppointmentRow> {
  const res = await api<{ appointment: AppointmentRow }>(
    "/api/admin/crm/appointments",
    { method: "POST", body: JSON.stringify(body) },
  );
  return res.appointment;
}

export async function getCrmAppointmentHistory(
  id: string,
): Promise<{ history: AppointmentHistoryRow[] }> {
  return api(`/api/admin/crm/appointments/${id}/history`);
}

export async function transitionCrmAppointment(
  id: string,
  body: { to_status: string; reason?: string },
): Promise<AppointmentRow> {
  const res = await api<{ appointment: AppointmentRow }>(
    `/api/admin/crm/appointments/${id}/transition`,
    { method: "POST", body: JSON.stringify(body) },
  );
  return res.appointment;
}

export async function cancelCrmAppointment(
  id: string,
  body?: { reason?: string },
): Promise<AppointmentRow> {
  const res = await api<{ appointment: AppointmentRow }>(
    `/api/admin/crm/appointments/${id}/cancel`,
    { method: "POST", body: JSON.stringify(body || {}) },
  );
  return res.appointment;
}

export async function rescheduleCrmAppointment(
  id: string,
  body: { starts_at: string; ends_at?: string; duration_minutes?: number },
): Promise<AppointmentRow> {
  const res = await api<{ appointment: AppointmentRow }>(
    `/api/admin/crm/appointments/${id}/reschedule`,
    { method: "POST", body: JSON.stringify(body) },
  );
  return res.appointment;
}

export async function assignCrmAppointment(
  id: string,
  body: { technician_id: string | null },
): Promise<AppointmentRow> {
  const res = await api<{ appointment: AppointmentRow }>(
    `/api/admin/crm/appointments/${id}/assign`,
    { method: "POST", body: JSON.stringify(body) },
  );
  return res.appointment;
}

export async function queryAvailability(body: {
  from_date: string;
  to_date: string;
  service_id?: string;
  duration_minutes?: number;
  technician_id?: string;
  is_emergency?: boolean;
  location_id?: string;
  limit?: number;
}): Promise<AvailabilityResult> {
  return api("/api/admin/crm/appointments/availability", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getBusinessHours(): Promise<Record<string, unknown>> {
  return api("/api/admin/crm/business-hours");
}

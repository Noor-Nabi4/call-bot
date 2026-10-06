import type { Appointment, Call, CustomerOption } from "@/types";
import { api } from "./client";

export type TeamUser = {
  id: string;
  email: string;
  name: string;
  role: string;
  is_active: boolean;
  status?: string;
  roles?: Array<{
    id: string;
    name: string;
    is_system: boolean;
    is_active: boolean;
  }>;
};

export function listAppointments() {
  return api<{ appointments: Appointment[] }>("/api/admin/appointments");
}

export function listCalls(opts?: { status?: string; limit?: number }) {
  const params = new URLSearchParams();
  if (opts?.status) params.set("status", opts.status);
  if (opts?.limit != null) params.set("limit", String(opts.limit));
  const qs = params.toString();
  return api<{ calls: Call[] }>(`/api/admin/calls${qs ? `?${qs}` : ""}`);
}

export function reviewCallQuality(
  callId: string,
  body: {
    quality_score?: number | null;
    disposition_code?: string | null;
    quality_notes?: string | null;
  },
) {
  return api<{ call: Call }>(`/api/admin/calls/${callId}/quality`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export type SupervisorSnapshot = {
  active_calls: Call[];
  recent_calls: Call[];
  attention: Call[];
  summary: {
    calls_active: number;
    handoffs_open: number;
    calls_today: number;
    handoffs_today: number;
    avg_call_duration_seconds: number;
  };
};

export function getSupervisorSnapshot(opts?: { recent_limit?: number }) {
  const params = new URLSearchParams();
  if (opts?.recent_limit != null) {
    params.set("recent_limit", String(opts.recent_limit));
  }
  const qs = params.toString();
  return api<{ snapshot: SupervisorSnapshot }>(
    `/api/admin/supervisor${qs ? `?${qs}` : ""}`,
  );
}

export type QueueItem = {
  id: string;
  call_id: string;
  status: string;
  reason: string;
  priority: number;
  notes?: string | null;
  claimed_by?: string | null;
  claimed_at?: string | null;
  completed_at?: string | null;
  created_at?: string | null;
  caller_number?: string | null;
  called_number?: string | null;
  call_status?: string | null;
};

export function listQueue(opts?: { status?: string; limit?: number }) {
  const params = new URLSearchParams();
  if (opts?.status) params.set("status", opts.status);
  if (opts?.limit != null) params.set("limit", String(opts.limit));
  const qs = params.toString();
  return api<{ items: QueueItem[] }>(`/api/admin/queue${qs ? `?${qs}` : ""}`);
}

export function claimQueueItem(itemId: string) {
  return api<{ item: QueueItem }>(`/api/admin/queue/${itemId}/claim`, {
    method: "POST",
  });
}

export function completeQueueItem(
  itemId: string,
  body?: { notes?: string | null; cancel?: boolean },
) {
  return api<{ item: QueueItem }>(`/api/admin/queue/${itemId}/complete`, {
    method: "POST",
    body: JSON.stringify(body || {}),
  });
}

/** Picker-friendly customer list (id + name). Prefers CRM customers API. */
export function listCustomers() {
  return api<{ customers: Array<{ id: string; name: string }> }>(
    "/api/admin/crm/customers?limit=200",
  ).then((d) => ({
    customers: (d.customers || []).map(
      (c): CustomerOption => ({
        id: c.id,
        name: c.name,
      }),
    ),
  }));
}

export function listTeamUsers() {
  return api<{ users: TeamUser[] }>("/api/admin/users");
}

export function inviteTeamUser(body: {
  name: string;
  email: string;
  password: string;
  role: string;
  phone?: string;
}) {
  return api<{ user: TeamUser }>("/api/admin/users", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateTeamUser(
  userId: string,
  body: {
    name?: string;
    role?: string;
    is_active?: boolean;
    password?: string;
  },
) {
  return api<{ user: TeamUser }>(`/api/admin/users/${userId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export type OrgRole = {
  id: string;
  name: string;
  description?: string | null;
  is_system: boolean;
  is_active: boolean;
  permissions?: Array<{
    key: string;
    scope: string;
    resource: string;
    action: string;
  }>;
};

export type PlatformPermission = {
  id: string;
  key: string;
  resource: string;
  action: string;
  description: string;
};

export function listOrgRoles() {
  return api<{ roles: OrgRole[] }>("/api/admin/organization/roles");
}

export function getOrgRole(roleId: string) {
  return api<{ role: OrgRole }>(`/api/admin/organization/roles/${roleId}`);
}

export function createOrgRole(body: {
  name: string;
  description?: string;
  permissions?: Array<{ key: string; scope: string }>;
}) {
  return api<{ role: OrgRole }>("/api/admin/organization/roles", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateOrgRole(
  roleId: string,
  body: {
    name?: string;
    description?: string | null;
    is_active?: boolean;
    permissions?: Array<{ key: string; scope: string }>;
  },
) {
  return api<{ role: OrgRole }>(`/api/admin/organization/roles/${roleId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function listPlatformPermissions() {
  return api<{ permissions: PlatformPermission[] }>(
    "/api/admin/organization/permissions",
  );
}

export function listMemberRoles(memberId: string) {
  return api<{
    member_id: string;
    roles: Array<{ id: string; name: string; is_system: boolean; is_active: boolean }>;
  }>(`/api/admin/organization/members/${memberId}/roles`);
}

export function assignMemberRole(memberId: string, roleId: string) {
  return api<{
    member_id: string;
    roles: Array<{ id: string; name: string; is_system: boolean; is_active: boolean }>;
  }>(`/api/admin/organization/members/${memberId}/roles`, {
    method: "POST",
    body: JSON.stringify({ role_id: roleId }),
  });
}

export function removeMemberRole(memberId: string, roleId: string) {
  return api<{
    member_id: string;
    roles: Array<{ id: string; name: string; is_system: boolean; is_active: boolean }>;
  }>(`/api/admin/organization/members/${memberId}/roles/${roleId}`, {
    method: "DELETE",
  });
}

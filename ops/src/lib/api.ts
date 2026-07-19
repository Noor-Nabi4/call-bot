/** Browser client for platform ops APIs (cookie session). */

const API_BASE =
  process.env.NEXT_PUBLIC_PLATFORM_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

export type OpsUser = {
  id: string;
  tenant_id: string;
  tenant_slug: string;
  tenant_name: string;
  email: string;
  name: string;
  role: string;
  technician_id: string | null;
};

export type Job = {
  id: string;
  reference_code: string;
  status: string;
  service_type: string;
  customer_id: string;
  customer?: {
    id: string;
    name: string;
    email?: string | null;
    address?: string | null;
  } | null;
  assigned_technician_id?: string | null;
  assigned_technician?: { id: string; display_name: string } | null;
  scheduled_starts_at?: string | null;
  scheduled_ends_at?: string | null;
  checklist: { id: string; label: string; done: boolean }[];
  completion_notes?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  notes?: {
    id: string;
    body: string;
    author_name?: string | null;
    created_at?: string | null;
  }[];
};

export type Technician = {
  id: string;
  display_name: string;
  phone?: string | null;
  is_active: boolean;
};

async function api<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      const detail = body?.detail;
      if (typeof detail === "string") message = detail;
      else if (detail?.message) message = detail.message;
    } catch {
      /* ignore */
    }
    throw new Error(message || `Request failed (${res.status})`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export function login(body: {
  email: string;
  password: string;
  tenant_slug: string;
}) {
  return api<{ user: OpsUser }>("/auth/login", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function logout() {
  return api<{ ok: boolean }>("/auth/logout", { method: "POST" });
}

export function me() {
  return api<{ user: OpsUser }>("/auth/me");
}

export function listJobs(params?: { status?: string; technician_id?: string }) {
  const q = new URLSearchParams();
  if (params?.status) q.set("status", params.status);
  if (params?.technician_id) q.set("technician_id", params.technician_id);
  const qs = q.toString();
  return api<{ jobs: Job[] }>(`/api/jobs${qs ? `?${qs}` : ""}`);
}

export function getJob(id: string) {
  return api<{ job: Job }>(`/api/jobs/${id}`);
}

export function createJob(body: {
  customer_id: string;
  service_type: string;
  status?: string;
  scheduled_starts_at?: string | null;
  scheduled_ends_at?: string | null;
}) {
  return api<{ job: Job }>("/api/jobs", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function listTechnicians() {
  return api<{ technicians: Technician[] }>("/api/technicians");
}

export function createTechnician(body: {
  email: string;
  password: string;
  name: string;
  phone?: string;
}) {
  return api<{ technician: Technician }>("/api/technicians", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function assignJob(jobId: string, technician_id: string) {
  return api<{ job: Job }>(`/api/jobs/${jobId}/assign`, {
    method: "POST",
    body: JSON.stringify({ technician_id }),
  });
}

export function transitionJob(
  jobId: string,
  status: string,
  completion_notes?: string,
) {
  return api<{ job: Job }>(`/api/jobs/${jobId}/transition`, {
    method: "POST",
    body: JSON.stringify({ status, completion_notes }),
  });
}

export function updateChecklist(
  jobId: string,
  checklist: Job["checklist"],
) {
  return api<{ job: Job }>(`/api/jobs/${jobId}/checklist`, {
    method: "PUT",
    body: JSON.stringify({ checklist }),
  });
}

export function addNote(jobId: string, body: string) {
  return api<{ job: Job }>(`/api/jobs/${jobId}/notes`, {
    method: "POST",
    body: JSON.stringify({ body }),
  });
}

export function pingLocation(lat: number, lng: number) {
  return api<{ technician: Technician }>("/api/tech/location", {
    method: "POST",
    body: JSON.stringify({ lat, lng }),
  });
}

export function formatWhen(iso?: string | null) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export const STATUS_ORDER = [
  "new",
  "scheduled",
  "dispatched",
  "in_progress",
  "completed",
  "canceled",
] as const;

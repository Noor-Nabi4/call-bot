/** Typed helpers for the Job CRM admin APIs (Phase 10, `/api/admin/crm/jobs`). */

import { api, apiMultipart } from "./client";
export type { JobStatus } from "./job-constants";
export {
  JOB_ACTIVE_STATUSES,
  JOB_ASSIGNABLE_STATUSES,
  JOB_CANCELLABLE,
  JOB_FORWARD_TRANSITIONS,
  JOB_STATUS_LABELS,
  JOB_STATUSES,
  JOB_TERMINAL_STATUSES,
  jobStatusLabel,
} from "./job-constants";

export type JobCustomerRef = {
  id: string;
  name?: string | null;
  display_name?: string | null;
  status?: string | null;
};

export type JobTechnicianRef = {
  id: string;
  display_name: string;
};

export type JobStatusHistoryRow = {
  id: string;
  from_status?: string | null;
  to_status: string;
  changed_by?: string | null;
  reason?: string | null;
  metadata?: Record<string, unknown>;
  created_at?: string | null;
};

export type JobNoteRow = {
  id: string;
  body: string;
  author_user_id?: string | null;
  author_name?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type JobAttachmentRow = {
  id: string;
  filename: string;
  content_type?: string | null;
  size_bytes?: number | null;
  uploaded_by?: string | null;
  created_at?: string | null;
};

export type JobChecklistItem = {
  id: string;
  label: string;
  done: boolean;
};

export type JobRow = {
  id: string;
  job_number: string;
  reference_code: string;
  customer_id: string;
  customer?: JobCustomerRef | null;
  location_id?: string | null;
  service_id?: string | null;
  appointment_id?: string | null;
  lead_id?: string | null;
  call_id?: string | null;
  assigned_technician_id?: string | null;
  assigned_technician?: JobTechnicianRef | null;
  status: string;
  priority: string;
  service_type: string;
  description?: string | null;
  scheduled_starts_at?: string | null;
  scheduled_ends_at?: string | null;
  checklist?: JobChecklistItem[];
  completion_notes?: string | null;
  idempotency_key?: string | null;
  archived_at?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  status_history?: JobStatusHistoryRow[];
  notes?: JobNoteRow[];
  attachments?: JobAttachmentRow[];
};

export type JobListResponse = {
  jobs: JobRow[];
  next_cursor?: string | null;
  limit: number;
};

export type JobCreateInput = {
  customer_id: string;
  service_type: string;
  location_id?: string;
  service_id?: string;
  description?: string;
  priority?: string;
  status?: string;
  scheduled_starts_at?: string | null;
  scheduled_ends_at?: string | null;
  idempotency_key?: string;
};

function qs(params: Record<string, string | number | boolean | undefined>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === "" || v === false) continue;
    sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export async function listCrmJobs(params: {
  q?: string;
  status?: string;
  customer_id?: string;
  technician_id?: string;
  include_archived?: boolean;
  limit?: number;
  cursor?: string;
} = {}): Promise<JobListResponse> {
  return api<JobListResponse>(`/api/admin/crm/jobs${qs(params)}`);
}

export async function getCrmJob(id: string): Promise<JobRow> {
  const res = await api<{ job: JobRow }>(`/api/admin/crm/jobs/${id}`);
  return res.job;
}

export async function createCrmJob(
  body: JobCreateInput,
  opts?: { idempotencyKey?: string }
): Promise<JobRow> {
  const headers: Record<string, string> = {};
  if (opts?.idempotencyKey) {
    headers["Idempotency-Key"] = opts.idempotencyKey;
  }
  const res = await api<{ job: JobRow }>("/api/admin/crm/jobs", {
    method: "POST",
    body: JSON.stringify(body),
    headers,
  });
  return res.job;
}

export async function updateCrmJob(
  id: string,
  body: Record<string, unknown>
): Promise<JobRow> {
  const res = await api<{ job: JobRow }>(`/api/admin/crm/jobs/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  return res.job;
}

export async function archiveCrmJob(id: string): Promise<JobRow> {
  const res = await api<{ job: JobRow }>(`/api/admin/crm/jobs/${id}`, {
    method: "DELETE",
  });
  return res.job;
}

export async function restoreCrmJob(id: string): Promise<JobRow> {
  const res = await api<{ job: JobRow }>(`/api/admin/crm/jobs/${id}/restore`, {
    method: "POST",
  });
  return res.job;
}

export async function assignCrmJob(
  id: string,
  technician_id: string | null
): Promise<JobRow> {
  const res = await api<{ job: JobRow }>(`/api/admin/crm/jobs/${id}/assign`, {
    method: "POST",
    body: JSON.stringify({ technician_id }),
  });
  return res.job;
}

export async function transitionCrmJob(
  id: string,
  body: { to_status: string; reason?: string; completion_notes?: string }
): Promise<JobRow> {
  const res = await api<{ job: JobRow }>(
    `/api/admin/crm/jobs/${id}/transition`,
    {
      method: "POST",
      body: JSON.stringify(body),
    }
  );
  return res.job;
}

export async function getCrmJobHistory(
  id: string
): Promise<{ history: JobStatusHistoryRow[] }> {
  return api<{ history: JobStatusHistoryRow[] }>(
    `/api/admin/crm/jobs/${id}/history`
  );
}

export async function listCrmJobNotes(
  id: string
): Promise<{ notes: JobNoteRow[] }> {
  return api<{ notes: JobNoteRow[] }>(`/api/admin/crm/jobs/${id}/notes`);
}

export async function createCrmJobNote(
  id: string,
  body: string
): Promise<JobNoteRow> {
  const res = await api<{ note: JobNoteRow }>(
    `/api/admin/crm/jobs/${id}/notes`,
    {
      method: "POST",
      body: JSON.stringify({ body }),
    }
  );
  return res.note;
}

export async function updateCrmJobNote(
  jobId: string,
  noteId: string,
  body: string
): Promise<JobNoteRow> {
  const res = await api<{ note: JobNoteRow }>(
    `/api/admin/crm/jobs/${jobId}/notes/${noteId}`,
    {
      method: "PATCH",
      body: JSON.stringify({ body }),
    }
  );
  return res.note;
}

export async function archiveCrmJobNote(
  jobId: string,
  noteId: string
): Promise<JobNoteRow> {
  const res = await api<{ note: JobNoteRow }>(
    `/api/admin/crm/jobs/${jobId}/notes/${noteId}`,
    { method: "DELETE" }
  );
  return res.note;
}

export async function listCrmJobAttachments(
  id: string
): Promise<{ attachments: JobAttachmentRow[] }> {
  return api<{ attachments: JobAttachmentRow[] }>(
    `/api/admin/crm/jobs/${id}/attachments`
  );
}

export async function uploadCrmJobAttachment(
  id: string,
  file: File
): Promise<JobAttachmentRow> {
  const form = new FormData();
  form.append("file", file);
  const res = await apiMultipart<{ attachment: JobAttachmentRow }>(
    `/api/admin/crm/jobs/${id}/attachments`,
    form
  );
  return res.attachment;
}

export async function archiveCrmJobAttachment(
  jobId: string,
  attachmentId: string
): Promise<JobAttachmentRow> {
  const res = await api<{ attachment: JobAttachmentRow }>(
    `/api/admin/crm/jobs/${jobId}/attachments/${attachmentId}`,
    { method: "DELETE" }
  );
  return res.attachment;
}

import { notifyAttentionChanged } from "@/lib/attention-bus";
import type { Job } from "@/types";
import { api } from "./client";

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
  }).then((res) => {
    notifyAttentionChanged();
    return res;
  });
}

export function assignJob(jobId: string, technician_id: string) {
  return api<{ job: Job }>(`/api/jobs/${jobId}/assign`, {
    method: "POST",
    body: JSON.stringify({ technician_id }),
  }).then((res) => {
    notifyAttentionChanged();
    return res;
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
  }).then((res) => {
    notifyAttentionChanged();
    return res;
  });
}

export function updateChecklist(jobId: string, checklist: Job["checklist"]) {
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

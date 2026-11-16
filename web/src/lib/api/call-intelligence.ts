import { api } from "./client";

export type CallRecording = {
  id: string;
  call_id: string | null;
  status: string;
  lifecycle_status: string;
  mime_type: string;
  size_bytes: number;
  duration_ms: number | null;
  download_url?: string;
  ttl_seconds?: number;
  expires_at: string | null;
  recorded_at: string | null;
};

export type TranscriptSegment = {
  id: string;
  speaker: string;
  start_ms: number;
  end_ms: number;
  text: string;
  confidence: number | null;
  sequence: number;
};

export type CallTranscript = {
  id: string;
  call_id: string;
  status: string;
  language: string | null;
  full_text: string | null;
  segments?: TranscriptSegment[];
  last_error: string | null;
  completed_at: string | null;
};

export type CallIntelligence = {
  id: string;
  call_id: string;
  intent: string | null;
  problem: string | null;
  outcome: string | null;
  sentiment: string | null;
  appointment_status: string | null;
  follow_up: string | null;
  classification: string | null;
  classification_confidence: number | null;
  classification_source: string | null;
  important_notes: string[];
  analysis_status: string;
  last_error: string | null;
  analysis_version: number;
};

export type CallClassification = {
  call_id: string;
  classification: string | null;
  confidence: number | null;
  source: string | null;
  analysis_status: string;
};

export function getCallRecording(callId: string) {
  return api<{ recording: CallRecording }>(
    `/api/admin/crm/calls/${callId}/recording`,
  );
}

export function getCallTranscript(callId: string) {
  return api<{ transcript: CallTranscript }>(
    `/api/admin/crm/calls/${callId}/transcript`,
  );
}

export function getCallIntelligence(callId: string) {
  return api<{ intelligence: CallIntelligence }>(
    `/api/admin/crm/calls/${callId}/intelligence`,
  );
}

export function getCallClassification(callId: string) {
  return api<{ classification: CallClassification }>(
    `/api/admin/crm/calls/${callId}/classification`,
  );
}

export function reanalyzeCall(callId: string) {
  return api<{ reanalyze: { enqueued: boolean; job_id?: string } }>(
    `/api/admin/crm/calls/${callId}/reanalyze`,
    { method: "POST", body: JSON.stringify({}) },
  );
}

export function searchCallIntelligence(params: {
  q?: string;
  classification?: string;
  sentiment?: string;
  limit?: number;
} = {}) {
  const qs = new URLSearchParams();
  if (params.q) qs.set("q", params.q);
  if (params.classification) qs.set("classification", params.classification);
  if (params.sentiment) qs.set("sentiment", params.sentiment);
  if (params.limit) qs.set("limit", String(params.limit));
  const q = qs.toString();
  return api<{
    items: Array<{
      call_id: string;
      snippet: string;
      classification: string | null;
      sentiment: string | null;
      intent: string | null;
    }>;
    total: number;
  }>(`/api/admin/crm/call-intelligence/search${q ? `?${q}` : ""}`);
}

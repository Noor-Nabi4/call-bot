import { api } from "./client";

export type CommunicationTemplate = {
  id: string;
  channel: string;
  template_key: string;
  name: string;
  description: string | null;
  status: string;
  active_version: number;
  version?: number;
  subject_template?: string | null;
  body_template?: string;
  updated_at: string | null;
  versions?: Array<{
    id: string;
    version: number;
    status: string;
    subject_template: string | null;
    body_template: string;
  }>;
};

export function listCommunicationTemplates(params?: {
  channel?: string;
  status?: string;
}) {
  const qs = new URLSearchParams();
  if (params?.channel) qs.set("channel", params.channel);
  if (params?.status) qs.set("status", params.status);
  const q = qs.toString();
  return api<{ items: CommunicationTemplate[] }>(
    `/api/admin/crm/communication-templates${q ? `?${q}` : ""}`,
  );
}

export function getCommunicationTemplate(id: string) {
  return api<{ template: CommunicationTemplate }>(
    `/api/admin/crm/communication-templates/${id}`,
  );
}

export function updateCommunicationTemplate(
  id: string,
  body: {
    name?: string;
    description?: string | null;
    subject_template?: string | null;
    body_template?: string;
    publish?: boolean;
  },
) {
  return api<{ template: CommunicationTemplate }>(
    `/api/admin/crm/communication-templates/${id}`,
    { method: "PATCH", body: JSON.stringify(body) },
  );
}

export function validateCommunicationTemplate(
  id: string,
  body: { subject_template?: string | null; body_template?: string },
) {
  return api<{ valid: boolean; errors: string[]; allowed_variables: string[] }>(
    `/api/admin/crm/communication-templates/${id}/validate`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

export function previewCommunicationTemplate(
  id: string,
  body: { subject_template?: string | null; body_template?: string },
) {
  return api<{
    channel: string;
    template_key: string;
    version: number;
    rendered: string;
    rendered_subject: string | null;
  }>(`/api/admin/crm/communication-templates/${id}/preview`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function publishCommunicationTemplate(id: string) {
  return api<{ template: CommunicationTemplate }>(
    `/api/admin/crm/communication-templates/${id}/publish`,
    { method: "POST", body: JSON.stringify({}) },
  );
}

export function archiveCommunicationTemplate(id: string) {
  return api<{ template: CommunicationTemplate }>(
    `/api/admin/crm/communication-templates/${id}/archive`,
    { method: "POST", body: JSON.stringify({}) },
  );
}

export function getTemplateVariables(templateKey?: string) {
  const qs = templateKey
    ? `?template_key=${encodeURIComponent(templateKey)}`
    : "";
  return api<{
    template_key?: string;
    variables?: string[];
    by_template?: Record<string, string[]>;
    sms_keys?: string[];
    email_keys?: string[];
  }>(`/api/admin/crm/communication-templates/variables${qs}`);
}

import { api } from "./client";

export type AutomationWorkflow = {
  id: string;
  name: string;
  description: string | null;
  status: string;
  trigger_event: string;
  version?: number;
  version_status?: string;
  definition?: {
    conditions?: Record<string, unknown> | null;
    actions?: Array<{ type: string; config: Record<string, unknown> }>;
  };
};

export type AutomationExecution = {
  id: string;
  workflow_id: string;
  event_id: string;
  status: string;
  correlation_id: string;
  started_at: string | null;
  completed_at: string | null;
  error_code: string | null;
  error_message: string | null;
  actions: Array<{
    id: string;
    action_key: string;
    status: string;
    error_code: string | null;
    error_message: string | null;
  }>;
};

export const AUTOMATION_EVENTS = [
  "CALL_COMPLETED",
  "LEAD_CREATED",
  "JOB_CREATED",
  "APPOINTMENT_CREATED",
  "APPOINTMENT_REMINDER",
  "TECHNICIAN_DISPATCHED",
  "TECHNICIAN_ARRIVED",
  "JOB_COMPLETED",
  "ESTIMATE_SENT",
  "ESTIMATE_APPROVED",
  "INVOICE_CREATED",
  "PAYMENT_COMPLETED",
  "ORDER_CREATED",
  "ORDER_SHIPPED",
] as const;

export const AUTOMATION_ACTIONS = [
  "SEND_SMS",
  "SEND_EMAIL",
  "CREATE_TASK",
  "CREATE_JOB",
  "CREATE_APPOINTMENT",
  "SEND_PAYMENT_LINK",
  "REQUEST_REVIEW",
  "WEBHOOK",
] as const;

export async function listAutomations(): Promise<{ workflows: AutomationWorkflow[] }> {
  return api("/api/admin/crm/automations");
}

export async function getAutomation(id: string): Promise<{ workflow: AutomationWorkflow }> {
  return api(`/api/admin/crm/automations/${id}`);
}

export async function createAutomation(body: {
  name: string;
  trigger_event: string;
  description?: string;
  definition?: AutomationWorkflow["definition"];
}): Promise<{ workflow: AutomationWorkflow }> {
  return api("/api/admin/crm/automations", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateAutomation(
  id: string,
  body: Record<string, unknown>
): Promise<{ workflow: AutomationWorkflow }> {
  return api(`/api/admin/crm/automations/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function publishAutomation(id: string): Promise<{ workflow: AutomationWorkflow }> {
  return api(`/api/admin/crm/automations/${id}/publish`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function activateAutomation(id: string): Promise<{ workflow: AutomationWorkflow }> {
  return api(`/api/admin/crm/automations/${id}/activate`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function disableAutomation(id: string): Promise<{ workflow: AutomationWorkflow }> {
  return api(`/api/admin/crm/automations/${id}/disable`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function listAutomationExecutions(
  id: string
): Promise<{ executions: AutomationExecution[] }> {
  return api(`/api/admin/crm/automations/${id}/executions`);
}

import { api, apiMultipart } from "./client";

export type EquipmentRow = {
  id: string;
  customer_id: string;
  location_id: string | null;
  manufacturer: string;
  model: string;
  serial_number: string | null;
  installation_date: string | null;
  warranty_start_date: string | null;
  warranty_end_date: string | null;
  warranty_provider: string | null;
  warranty_notes: string | null;
  status: string;
  notes: string | null;
  warranty_status: string;
  under_warranty: boolean;
  days_remaining: number | null;
  created_at: string | null;
  updated_at: string | null;
  attachments?: EquipmentAttachmentRow[];
};

export type EquipmentHistoryItem = {
  type: string;
  date: string;
  summary?: string;
  job_id?: string;
  job_number?: string;
  note_id?: string;
  attachment_id?: string;
};

export type EquipmentAttachmentRow = {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  kind: string;
  download_url?: string | null;
  created_at?: string | null;
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

export async function listEquipment(params: {
  q?: string;
  customer_id?: string;
  location_id?: string;
  status?: string;
  serial_number?: string;
  warranty_status?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<{ equipment: EquipmentRow[]; limit: number; offset: number }> {
  return api(`/api/admin/crm/equipment${qs(params)}`);
}

export async function getEquipment(id: string): Promise<EquipmentRow> {
  const res = await api<{ equipment: EquipmentRow }>(`/api/admin/crm/equipment/${id}`);
  return res.equipment;
}

export async function createEquipment(body: {
  customer_id: string;
  manufacturer: string;
  model: string;
  location_id?: string;
  serial_number?: string;
  installation_date?: string;
  warranty_start_date?: string;
  warranty_end_date?: string;
  warranty_provider?: string;
  warranty_notes?: string;
  status?: string;
  notes?: string;
}): Promise<EquipmentRow> {
  const res = await api<{ equipment: EquipmentRow }>("/api/admin/crm/equipment", {
    method: "POST",
    body: JSON.stringify(body),
  });
  return res.equipment;
}

export async function updateEquipment(
  id: string,
  body: Record<string, unknown>
): Promise<EquipmentRow> {
  const res = await api<{ equipment: EquipmentRow }>(`/api/admin/crm/equipment/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  return res.equipment;
}

export async function deleteEquipment(id: string): Promise<{ id?: string; deleted?: boolean }> {
  return api(`/api/admin/crm/equipment/${id}`, { method: "DELETE" });
}

export async function getEquipmentHistory(
  id: string,
  params?: { limit?: number; offset?: number }
): Promise<{
  history: EquipmentHistoryItem[];
  limit: number;
  offset: number;
  total: number;
}> {
  return api(`/api/admin/crm/equipment/${id}/history${qs(params ?? {})}`);
}

export async function uploadEquipmentAttachment(
  equipmentId: string,
  file: File,
  kind = "PHOTO"
): Promise<EquipmentAttachmentRow> {
  const form = new FormData();
  form.append("file", file);
  form.append("kind", kind);
  const res = await apiMultipart<{ attachment: EquipmentAttachmentRow }>(
    `/api/admin/crm/equipment/${equipmentId}/attachments`,
    form
  );
  return res.attachment;
}

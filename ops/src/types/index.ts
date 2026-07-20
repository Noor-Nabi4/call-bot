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

export type HandoffSettings = {
  enabled: boolean;
  mode: string;
  escalation_phone_e164: string | null;
  sip_outbound_trunk_id: string | null;
};

export type AgentSettings = {
  assistant_name?: string | null;
  business_description?: string | null;
  greeting?: string | null;
  tone?: string | null;
  response_style?: string | null;
  language?: string | null;
  supported_languages?: string[] | null;
  service_areas?: string[] | null;
  business_hours_summary?: string | null;
  booking_rules?: string | null;
  pricing_disclosure_policy?: string | null;
  handoff_rules_text?: string | null;
  restricted_topics?: string[] | null;
  custom_instructions?: string | null;
  profile_version?: number | null;
  updated_at?: string | null;
  voice?: string | null;
  tenant_id?: string;
};

export type CustomerOption = {
  id: string;
  name: string;
};

export type Appointment = {
  id: string;
  confirmation_code: string;
  status: string;
  service_type: string;
  starts_at?: string | null;
  ends_at?: string | null;
  customer_id: string;
};

export type Call = {
  id: string;
  status: string;
  caller_number?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
};

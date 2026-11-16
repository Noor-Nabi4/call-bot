import type { InventoryNumber, PhoneNumber, TestCallSession } from "@/types";
import { api } from "./client";

export function listPhoneNumbers() {
  return api<{ items: PhoneNumber[] }>("/api/admin/phone-numbers");
}

export function assignPhoneProfile(
  phoneNumberId: string,
  agentProfileId: string | null,
) {
  return api<{ phone_number: PhoneNumber }>(
    `/api/admin/phone-numbers/${phoneNumberId}`,
    {
      method: "PATCH",
      body: JSON.stringify({ agent_profile_id: agentProfileId }),
    },
  );
}

export function connectPhoneNumber(body: {
  phone_number: string;
  twilio_account_sid?: string;
}) {
  return api<Record<string, unknown>>("/api/admin/phone-numbers/connect", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function ensureTwilioSubaccount() {
  return api<Record<string, unknown>>("/api/admin/twilio/subaccount", {
    method: "POST",
  });
}

export function searchInventory(params: {
  country?: string;
  area_code?: string;
  limit?: number;
}) {
  const q = new URLSearchParams();
  if (params.country) q.set("country", params.country);
  if (params.area_code) q.set("area_code", params.area_code);
  if (params.limit) q.set("limit", String(params.limit));
  const suffix = q.toString() ? `?${q}` : "";
  return api<{ items: InventoryNumber[] }>(`/api/admin/inventory${suffix}`);
}

export function purchasePhoneNumber(phoneNumber: string, idempotencyKey: string) {
  return api<Record<string, unknown>>("/api/admin/phone-numbers/purchase", {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify({ phone_number: phoneNumber, confirm: true }),
  });
}

export function confirmPhoneTrunk(
  phoneNumberId: string,
  twilioTrunkSid?: string,
) {
  return api<Record<string, unknown>>(
    `/api/admin/phone-numbers/${phoneNumberId}/confirm-trunk`,
    {
      method: "POST",
      body: JSON.stringify({ twilio_trunk_sid: twilioTrunkSid || null }),
    },
  );
}

export type PhoneVerificationStart = {
  phone_number_id: string;
  e164: string;
  verification_status: string;
  connection_status: string;
  verification_token?: string;
  expires_at?: string;
  instructions: string;
};

export function startPhoneVerification(phoneNumberId: string) {
  return api<PhoneVerificationStart>(
    `/api/admin/phone-numbers/${phoneNumberId}/verification/start`,
    { method: "POST" },
  );
}

export function releasePhoneNumber(phoneNumberId: string) {
  return api<Record<string, unknown>>(
    `/api/admin/phone-numbers/${phoneNumberId}/release`,
    {
      method: "POST",
      body: JSON.stringify({}),
    },
  );
}

export function createTestCall(agentProfileId?: string | null) {
  return api<TestCallSession>("/api/admin/test-call", {
    method: "POST",
    body: JSON.stringify({
      agent_profile_id: agentProfileId || null,
    }),
  });
}

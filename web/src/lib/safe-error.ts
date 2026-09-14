import { errors } from "@/lib/ops-copy";

const SENSITIVE =
  /\b(STRIPE|LIVEKIT|OPENAI[_-]?REALTIME|ACCOUNT[_ ]?SID|SIP[_ ]?(REFER|TRUNK)|WEBHOOK[_ ]?SECRET|HMAC|API[_ ]?KEY|METADATA[_ ]?HMAC|STACK[_ ]?TRACE|process\.env|REDIS|POSTGRES|EMBEDDING|VECTOR[_ ]?ID|SECRET|STACK)\b/i;

/**
 * Map backend failures to safe customer-facing messages.
 * Never render raw provider or infrastructure errors in the UI.
 */
export function safeUserError(
  error: unknown,
  fallback: string = errors.generic,
): string {
  const raw =
    error instanceof Error
      ? error.message
      : typeof error === "string"
        ? error
        : "";

  if (!raw.trim()) return fallback;
  if (SENSITIVE.test(raw)) return fallback;
  if (/^request failed/i.test(raw)) return fallback;

  // Auth-friendly short messages
  if (/invalid|unauthorized|forbidden|credentials|password|email/i.test(raw)) {
    if (raw.length <= 120 && !/[{\\[]/.test(raw)) return raw;
  }

  if (raw.length <= 120 && !/[{\\[\]=]|http:\/\/|https:\/\//i.test(raw)) {
    return raw;
  }

  return fallback;
}

/** Mask internal IDs for display (show last 4 characters). */
export function maskSecret(value: string | null | undefined): string {
  if (!value) return "";
  const trimmed = value.trim();
  if (trimmed.length <= 4) return "••••";
  return `••••${trimmed.slice(-4)}`;
}

import { telephony, voice } from "@/lib/copy";

const SENSITIVE =
  /\b(LIVEKIT|OPENAI[_-]?REALTIME|ACCOUNT[_ ]?SID|SIP[_ ]?(REFER|TRUNK)|WEBHOOK[_ ]?SECRET|HMAC|API[_ ]?KEY|METADATA[_ ]?HMAC|STACK[_ ]?TRACE|process\.env|REDIS|POSTGRES|MISSING REQUIRED ENVIRONMENT|AGENT[_ ]?NAME|TENANT[_ ]?ID)\b/i;

/**
 * Map backend / provider failures to safe customer-facing messages.
 * Detailed errors belong in server logs, not the UI.
 */
export function safeUserError(
  error: unknown,
  fallback: string = telephony.genericError,
): string {
  const raw =
    error instanceof Error
      ? error.message
      : typeof error === "string"
        ? error
        : "";

  if (!raw.trim()) return fallback;

  if (SENSITIVE.test(raw)) return fallback;

  // Token / session start failures
  if (/token|connect|session|microphone|permission/i.test(raw)) {
    return voice.startFailed;
  }

  // Keep short, non-technical messages that do not leak internals
  if (raw.length <= 120 && !/[{\\[\]=]|http:\/\/|https:\/\//i.test(raw)) {
    return raw;
  }

  return fallback;
}

export function safeConnectionError(error: unknown): string {
  return safeUserError(error, voice.interruptedError);
}

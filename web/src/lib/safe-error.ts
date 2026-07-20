/** Safe user-facing error messages for marketing forms. */

const SENSITIVE =
  /\b(STRIPE|LIVEKIT|OPENAI|WEBHOOK|HMAC|API[_ ]?KEY|SECRET|STACK)\b/i;

export function safeUserError(error: unknown, fallback: string): string {
  const raw =
    error instanceof Error
      ? error.message
      : typeof error === "string"
        ? error
        : "";
  if (!raw.trim()) return fallback;
  if (SENSITIVE.test(raw)) return fallback;
  if (raw.length <= 140 && !/[{\\[]/.test(raw)) return raw;
  return fallback;
}

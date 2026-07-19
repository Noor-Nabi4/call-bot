/** Cross-page signal so the notifications bell refreshes after mutations. */

export const ATTENTION_REFRESH_EVENT = "ops:attention-refresh";

export function notifyAttentionChanged(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(ATTENTION_REFRESH_EVENT));
}

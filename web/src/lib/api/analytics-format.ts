/** Pure analytics formatters (no API client — safe for node:test). */

export function formatDurationSeconds(
  seconds: number | null | undefined,
): string {
  if (seconds == null || Number.isNaN(seconds)) return "—";
  const s = Math.round(seconds);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  if (m < 60) return rem ? `${m}m ${rem}s` : `${m}m`;
  const h = Math.floor(m / 60);
  const rm = m % 60;
  return rm ? `${h}h ${rm}m` : `${h}h`;
}

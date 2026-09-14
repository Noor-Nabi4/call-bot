/** Schedule urgency derived from real scheduled_starts_at values. */

export function deriveUrgency(
  iso?: string | null,
): "overdue" | "today" | "upcoming" | "none" {
  if (!iso) return "none";
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return "none";
  const now = new Date();
  const startOfToday = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate(),
  );
  const endOfToday = new Date(startOfToday);
  endOfToday.setDate(endOfToday.getDate() + 1);
  if (when < startOfToday) return "overdue";
  if (when < endOfToday) return "today";
  return "upcoming";
}

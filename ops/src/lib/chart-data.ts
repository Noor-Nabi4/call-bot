/** Pure helpers to bucket real API records into chart series. No mock fallbacks. */

export type DayBucket = {
  key: string;
  label: string;
  date: Date;
};

export function dayKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function buildDayBuckets(days: number, now = new Date()): DayBucket[] {
  const buckets: DayBucket[] = [];
  const start = new Date(now);
  start.setHours(0, 0, 0, 0);
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(start);
    d.setDate(start.getDate() - i);
    buckets.push({
      key: dayKey(d),
      label:
        days <= 7
          ? d.toLocaleDateString(undefined, { weekday: "short" })
          : d.toLocaleDateString(undefined, { month: "short", day: "numeric" }),
      date: d,
    });
  }
  return buckets;
}

export function rangeStart(days: number, now = new Date()): Date {
  const d = new Date(now);
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() - (days - 1));
  return d;
}

export function inRange(iso: string | null | undefined, start: Date, end: Date): boolean {
  if (!iso) return false;
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return false;
  return t >= start.getTime() && t <= end.getTime();
}

export function countByDay(
  timestamps: Array<string | null | undefined>,
  buckets: DayBucket[],
): number[] {
  const map = new Map(buckets.map((b) => [b.key, 0]));
  for (const iso of timestamps) {
    if (!iso) continue;
    const key = dayKey(new Date(iso));
    if (map.has(key)) map.set(key, (map.get(key) || 0) + 1);
  }
  return buckets.map((b) => map.get(b.key) || 0);
}

export function isHandledCall(call: {
  status?: string | null;
  ended_at?: string | null;
}): boolean {
  if (call.ended_at) return true;
  const s = (call.status || "").toLowerCase();
  return ["completed", "ended", "answered", "success"].includes(s);
}

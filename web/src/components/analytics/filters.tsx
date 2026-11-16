"use client";

import { cn } from "@/lib/cn";
import type { AnalyticsPreset } from "@/lib/api/analytics";
import { Input, Select } from "@/components/ui";

const PRESETS: { id: AnalyticsPreset; label: string }[] = [
  { id: "today", label: "Today" },
  { id: "yesterday", label: "Yesterday" },
  { id: "last_7_days", label: "Last 7 days" },
  { id: "last_30_days", label: "Last 30 days" },
  { id: "this_month", label: "This month" },
  { id: "last_month", label: "Last month" },
  { id: "custom", label: "Custom" },
];

export type AnalyticsFilterState = {
  preset: AnalyticsPreset;
  from_date: string;
  to_date: string;
};

export function AnalyticsFilters({
  value,
  onChange,
  timezone,
  className,
}: {
  value: AnalyticsFilterState;
  onChange: (next: AnalyticsFilterState) => void;
  timezone?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-end gap-3 rounded-xl border border-border bg-surface px-3 py-3",
        className,
      )}
    >
      <label className="grid gap-1 text-xs font-medium text-text-secondary">
        Date range
        <Select
          className="min-w-[10rem]"
          value={value.preset}
          onChange={(e) =>
            onChange({
              ...value,
              preset: e.target.value as AnalyticsPreset,
            })
          }
          aria-label="Analytics date range preset"
        >
          {PRESETS.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label}
            </option>
          ))}
        </Select>
      </label>
      {value.preset === "custom" ? (
        <>
          <label className="grid gap-1 text-xs font-medium text-text-secondary">
            From
            <Input
              type="date"
              value={value.from_date}
              onChange={(e) =>
                onChange({ ...value, from_date: e.target.value })
              }
            />
          </label>
          <label className="grid gap-1 text-xs font-medium text-text-secondary">
            To
            <Input
              type="date"
              value={value.to_date}
              onChange={(e) => onChange({ ...value, to_date: e.target.value })}
            />
          </label>
        </>
      ) : null}
      {timezone ? (
        <p className="ml-auto text-[11px] text-text-muted">
          Tenant timezone: {timezone}
        </p>
      ) : null}
    </div>
  );
}

"use client";

import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";

export type AnalyticsKpi = {
  id: string;
  label: string;
  value: string;
  hint?: string;
  unavailable?: string | null;
  icon: LucideIcon;
};

export function AnalyticsKpiCard({
  item,
  loading,
}: {
  item: AnalyticsKpi;
  loading?: boolean;
}) {
  const Icon = item.icon;
  const unavailable = Boolean(item.unavailable);
  return (
    <div
      className={cn(
        "flex h-full flex-col gap-3 rounded-[12px] border border-border bg-surface px-4 py-3.5",
        unavailable && "opacity-90",
      )}
    >
      <span className="inline-flex size-9 items-center justify-center rounded-lg border border-border bg-surface-muted/60 text-text-secondary">
        <Icon className="size-5" strokeWidth={1.8} aria-hidden />
      </span>
      <div className="min-w-0">
        <p className="text-[11px] font-medium tracking-wide text-text-muted uppercase">
          {item.label}
        </p>
        {loading ? (
          <div className="mt-2 h-7 w-20 animate-pulse rounded bg-surface-muted" />
        ) : unavailable ? (
          <p className="mt-1 text-sm font-medium text-text-secondary">
            Not available
          </p>
        ) : (
          <p className="mt-1 font-heading text-2xl font-semibold tabular-nums tracking-tight text-text-primary">
            {item.value}
          </p>
        )}
        <p className="mt-1 text-xs text-text-muted">
          {unavailable ? item.unavailable : item.hint}
        </p>
      </div>
    </div>
  );
}

export function AnalyticsKpiGrid({
  items,
  loading,
  className,
}: {
  items: AnalyticsKpi[];
  loading?: boolean;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6",
        className,
      )}
      role="list"
      aria-label="Analytics KPIs"
    >
      {items.map((item) => (
        <div key={item.id} role="listitem">
          <AnalyticsKpiCard item={item} loading={loading} />
        </div>
      ))}
    </div>
  );
}

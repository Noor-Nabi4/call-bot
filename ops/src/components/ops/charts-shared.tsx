"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export type DateRangeDays = 7 | 30;

export function DateRangeSelector({
  value,
  onChange,
  className,
}: {
  value: DateRangeDays;
  onChange: (days: DateRangeDays) => void;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "inline-flex rounded-[10px] border border-border bg-surface-muted p-0.5",
        className,
      )}
      role="group"
      aria-label="Chart date range"
    >
      {([7, 30] as const).map((days) => (
        <button
          key={days}
          type="button"
          onClick={() => onChange(days)}
          className={cn(
            "rounded-md px-2.5 py-1 text-xs font-medium transition-colors duration-150",
            value === days
              ? "bg-surface text-text-primary shadow-sm"
              : "text-text-secondary hover:text-text-primary",
          )}
        >
          {days}d
        </button>
      ))}
    </div>
  );
}

export function DashboardChartCard({
  title,
  description,
  action,
  children,
  className,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("glass-panel overflow-hidden", className)}>
      <header className="flex flex-wrap items-start justify-between gap-2 border-b border-border px-3.5 py-2.5">
        <div className="min-w-0">
          <h2 className="font-heading text-sm font-semibold text-text-primary">
            {title}
          </h2>
          {description ? (
            <p className="mt-0.5 text-xs text-text-muted">{description}</p>
          ) : null}
        </div>
        {action}
      </header>
      <div className="p-3.5">{children}</div>
    </section>
  );
}

export function ChartSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn("flex h-48 items-end gap-2", className)}
      aria-busy="true"
      aria-label="Loading chart"
    >
      {Array.from({ length: 8 }).map((_, i) => (
        <div
          key={i}
          className="skeleton flex-1"
          style={{ height: `${30 + ((i * 17) % 60)}%` }}
        />
      ))}
    </div>
  );
}

export function ChartEmptyState({
  message = "No activity data is available for this period.",
  className,
}: {
  message?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex h-48 items-center justify-center rounded-[10px] border border-dashed border-border px-4 text-center text-sm text-text-muted",
        className,
      )}
      role="status"
    >
      {message}
    </div>
  );
}

export const CHART_COLORS = {
  primary: "#0F766E",
  secondary: "#14b8a0",
  tertiary: "#5c6d74",
  grid: "rgba(12, 26, 30, 0.08)",
  text: "#5c6d74",
} as const;

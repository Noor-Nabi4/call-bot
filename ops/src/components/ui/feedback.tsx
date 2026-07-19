"use client";

import { cn } from "@/lib/cn";
import type { ReactNode } from "react";

export function MetricSummary({
  items,
  className,
}: {
  items: {
    label: string;
    value: string | number;
    hint?: string;
  }[];
  className?: string;
}) {
  if (items.length === 0) return null;
  return (
    <div
      className={cn(
        "mb-4 grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-3 lg:grid-cols-5",
        className,
      )}
      role="list"
      aria-label="Summary metrics"
    >
      {items.map((item) => (
        <div
          key={item.label}
          className="bg-surface px-3 py-2.5"
          role="listitem"
        >
          <p className="text-[11px] font-medium tracking-wide text-text-muted uppercase">
            {item.label}
          </p>
          <p className="mt-0.5 font-mono text-xl font-semibold tabular-nums text-text-primary">
            {item.value}
          </p>
          {item.hint ? (
            <p className="mt-0.5 text-xs text-text-secondary">{item.hint}</p>
          ) : null}
        </div>
      ))}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-lg border border-dashed border-border bg-surface px-6 py-12 text-center",
        className,
      )}
      role="status"
    >
      {icon ? (
        <div className="mb-3 text-text-muted" aria-hidden>
          {icon}
        </div>
      ) : null}
      <h3 className="text-sm font-semibold text-text-primary">{title}</h3>
      {description ? (
        <p className="mt-1 max-w-sm text-sm text-text-secondary">{description}</p>
      ) : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
  className,
}: {
  title?: string;
  message?: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border border-danger/30 bg-danger-soft px-4 py-3 text-sm",
        className,
      )}
      role="alert"
    >
      <p className="font-semibold text-danger">{title}</p>
      {message ? <p className="mt-1 text-danger/90">{message}</p> : null}
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 text-sm font-medium text-danger underline-offset-2 hover:underline"
        >
          Try again
        </button>
      ) : null}
    </div>
  );
}

export function LoadingSkeleton({
  rows = 4,
  className,
}: {
  rows?: number;
  className?: string;
}) {
  return (
    <div className={cn("space-y-2", className)} aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton h-10 w-full" />
      ))}
    </div>
  );
}

export function TechnicianAvatar({
  name,
  size = "md",
  className,
}: {
  name: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() || "")
    .join("");
  const sizes = {
    sm: "size-6 text-[10px]",
    md: "size-8 text-xs",
    lg: "size-10 text-sm",
  };
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full bg-brand-soft font-semibold text-brand",
        sizes[size],
        className,
      )}
      aria-hidden
    >
      {initials || "?"}
    </span>
  );
}

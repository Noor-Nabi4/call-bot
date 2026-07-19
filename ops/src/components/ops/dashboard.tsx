"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export function SummaryStrip({
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
        "grid grid-cols-2 gap-3 sm:grid-cols-4",
        className,
      )}
      role="list"
      aria-label="Summary"
    >
      {items.map((item) => (
        <div
          key={item.label}
          className="glass-panel px-4 py-3.5 transition hover:border-brand/40"
          role="listitem"
        >
          <p className="text-[11px] font-medium tracking-wide text-text-muted uppercase">
            {item.label}
          </p>
          <p className="mt-1.5 font-heading text-2xl font-semibold tabular-nums text-text-primary">
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

export function AttentionList({
  items,
  className,
}: {
  items: {
    id: string;
    title: string;
    count: number;
    explanation: string;
    href: string;
  }[];
  className?: string;
}) {
  if (items.length === 0) {
    return (
      <div
        className={cn(
          "rounded-2xl border border-border/80 bg-surface/40 px-4 py-5 text-sm text-text-secondary",
          className,
        )}
      >
        Nothing needs attention right now.
      </div>
    );
  }

  return (
    <ul className={cn("grid gap-2", className)}>
      {items.map((item) => (
        <li key={item.id}>
          <Link
            href={item.href}
            className="glass-panel flex items-start justify-between gap-3 px-3.5 py-3 transition duration-150 hover:border-brand/40"
          >
            <div className="min-w-0">
              <p className="text-sm font-semibold text-text-primary">
                {item.title}
              </p>
              <p className="mt-0.5 text-xs text-text-muted">{item.explanation}</p>
            </div>
            <span className="shrink-0 font-heading text-lg font-semibold tabular-nums text-cyan">
              {item.count}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

export function ActivityFeed({
  items,
  className,
  empty,
}: {
  items: {
    id: string;
    title: string;
    detail?: string;
    time?: string | null;
  }[];
  className?: string;
  empty?: ReactNode;
}) {
  if (items.length === 0) {
    return (
      <div
        className={cn(
          "rounded-xl border border-dashed border-border px-4 py-6 text-center text-sm text-text-muted",
          className,
        )}
      >
        {empty ?? "No recent activity."}
      </div>
    );
  }

  return (
    <ol
      className={cn(
        "space-y-0 divide-y divide-border overflow-hidden rounded-2xl border border-border glass-panel p-0",
        className,
      )}
    >
      {items.map((item) => (
        <li
          key={item.id}
          className="flex items-start justify-between gap-3 px-3.5 py-2.5"
        >
          <div className="min-w-0">
            <p className="text-sm font-medium text-text-primary">{item.title}</p>
            {item.detail ? (
              <p className="mt-0.5 text-xs text-text-muted">{item.detail}</p>
            ) : null}
          </div>
          {item.time ? (
            <time className="shrink-0 font-mono text-[11px] text-text-muted">
              {item.time}
            </time>
          ) : null}
        </li>
      ))}
    </ol>
  );
}

export function Panel({
  title,
  action,
  children,
  className,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("glass-panel overflow-hidden", className)}>
      <header className="flex items-center justify-between gap-2 border-b border-border px-3.5 py-2.5">
        <h2 className="font-heading text-sm font-semibold text-text-primary">
          {title}
        </h2>
        {action}
      </header>
      <div className="p-3.5">{children}</div>
    </section>
  );
}

"use client";

import { cn } from "@/lib/cn";
import type { ReactNode } from "react";

export function Timeline({
  items,
  className,
}: {
  items: {
    id: string;
    title: string;
    detail?: string;
    time?: string | null;
    tone?: "default" | "success" | "warn" | "danger";
  }[];
  className?: string;
}) {
  if (items.length === 0) {
    return (
      <p className="text-sm text-text-muted">No timeline events.</p>
    );
  }

  const tones = {
    default: "bg-border-strong",
    success: "bg-brand",
    warn: "bg-warn",
    danger: "bg-danger",
  };

  return (
    <ol className={cn("relative space-y-4 border-l border-border pl-4", className)}>
      {items.map((item) => (
        <li key={item.id} className="relative">
          <span
            className={cn(
              "absolute top-1.5 -left-[1.3rem] size-2 rounded-full",
              tones[item.tone || "default"],
            )}
            aria-hidden
          />
          <p className="text-sm font-medium text-text-primary">{item.title}</p>
          {item.detail ? (
            <p className="mt-0.5 text-sm text-text-secondary">{item.detail}</p>
          ) : null}
          {item.time ? (
            <p className="mt-0.5 font-mono text-[11px] text-text-muted">
              {item.time}
            </p>
          ) : null}
        </li>
      ))}
    </ol>
  );
}

export function PermissionGuard({
  allowed,
  fallback,
  children,
}: {
  allowed: boolean;
  fallback?: ReactNode;
  children: ReactNode;
}) {
  if (!allowed) {
    return (
      <>
        {fallback ?? (
          <div className="rounded-lg border border-border bg-surface p-6 text-sm text-text-secondary">
            You do not have permission to view this section.
          </div>
        )}
      </>
    );
  }
  return <>{children}</>;
}

export function Surface({
  children,
  className,
  as: Tag = "section",
}: {
  children: ReactNode;
  className?: string;
  as?: "section" | "div" | "article";
}) {
  return (
    <Tag
      className={cn(
        "rounded-lg border border-border bg-surface",
        className,
      )}
    >
      {children}
    </Tag>
  );
}

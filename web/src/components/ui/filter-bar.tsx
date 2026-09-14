"use client";

import { Search, X } from "lucide-react";
import { cn } from "@/lib/cn";
import type { InputHTMLAttributes } from "react";

export function SearchInput({
  className,
  onClear,
  value,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & {
  onClear?: () => void;
}) {
  return (
    <div className={cn("relative", className)}>
      <Search
        className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-text-muted"
        aria-hidden
      />
      <input
        type="search"
        value={value}
        className="h-9 w-full rounded-md border border-border bg-surface pr-8 pl-9 text-sm text-text-primary placeholder:text-text-muted transition-[border-color] duration-150 focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand-soft"
        {...props}
      />
      {value && onClear ? (
        <button
          type="button"
          onClick={onClear}
          className="absolute top-1/2 right-2 -translate-y-1/2 rounded p-0.5 text-text-muted hover:text-text-primary"
          aria-label="Clear search"
        >
          <X className="size-3.5" />
        </button>
      ) : null}
    </div>
  );
}

export function FilterBar({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "mb-4 flex flex-wrap items-center gap-2 rounded-lg border border-border bg-surface p-2.5",
        className,
      )}
      role="toolbar"
      aria-label="Filters"
    >
      {children}
    </div>
  );
}

export function SavedViewSelector({
  views,
  value,
  onChange,
}: {
  views: { id: string; label: string }[];
  value: string;
  onChange: (id: string) => void;
}) {
  return (
    <div
      className="inline-flex rounded-md border border-border bg-surface-muted p-0.5"
      role="group"
      aria-label="Saved views"
    >
      {views.map((view) => (
        <button
          key={view.id}
          type="button"
          onClick={() => onChange(view.id)}
          className={cn(
            "rounded px-2.5 py-1 text-xs font-medium transition-colors duration-150",
            value === view.id
              ? "bg-surface text-text-primary shadow-sm"
              : "text-text-secondary hover:text-text-primary",
          )}
        >
          {view.label}
        </button>
      ))}
    </div>
  );
}

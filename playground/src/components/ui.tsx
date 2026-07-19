"use client";

import { cn } from "@/lib/cn";
import type { ButtonHTMLAttributes } from "react";

export function Button({
  className,
  variant = "primary",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
}) {
  const variants = {
    primary:
      "bg-brand text-background hover:bg-brand-bright disabled:opacity-50",
    secondary:
      "border border-border bg-surface-strong text-text-primary hover:bg-brand-soft disabled:opacity-50",
    ghost: "text-text-secondary hover:bg-brand-soft hover:text-text-primary",
    danger:
      "border border-danger/40 bg-danger-soft text-danger hover:bg-danger hover:text-background",
  };
  return (
    <button
      type="button"
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-full px-5 py-2.5 text-sm font-semibold transition-[background-color,transform,opacity] duration-200 ease-out disabled:cursor-not-allowed",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}

export function Field({
  label,
  children,
  className,
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <label className={cn("grid gap-1.5 text-sm text-text-secondary", className)}>
      {label}
      {children}
    </label>
  );
}

export function TextInput({
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-11 w-full rounded-xl border border-border bg-surface-strong px-3 text-text-primary placeholder:text-text-muted focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand-soft",
        className,
      )}
      {...props}
    />
  );
}

export function EmptyHint({ children }: { children: React.ReactNode }) {
  return <p className="text-sm text-text-muted">{children}</p>;
}

export function ErrorBanner({ message }: { message: string }) {
  return (
    <p
      className="rounded-xl border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger"
      role="alert"
    >
      {message}
    </p>
  );
}

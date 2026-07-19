"use client";

import { cn } from "@/lib/cn";
import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "ink";
type Size = "sm" | "md" | "lg";

const variants: Record<Variant, string> = {
  primary:
    "bg-brand text-white hover:bg-brand-hover disabled:opacity-50 border border-transparent",
  secondary:
    "bg-surface text-text-primary border border-border hover:bg-surface-muted disabled:opacity-50",
  ghost:
    "bg-transparent text-text-secondary border border-transparent hover:bg-surface-muted hover:text-text-primary disabled:opacity-50",
  danger:
    "bg-danger-soft text-danger border border-transparent hover:bg-danger hover:text-white disabled:opacity-50",
  ink: "bg-text-primary text-white border border-transparent hover:opacity-90 disabled:opacity-50",
};

const sizes: Record<Size, string> = {
  sm: "h-8 px-2.5 text-xs gap-1.5",
  md: "h-9 px-3 text-sm gap-2",
  lg: "h-11 px-4 text-sm gap-2",
};

export function Button({
  className,
  variant = "primary",
  size = "md",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
}) {
  return (
    <button
      type="button"
      className={cn(
        "inline-flex items-center justify-center rounded-[10px] font-medium transition-[background-color,opacity,transform] duration-150 ease-out disabled:cursor-not-allowed",
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    />
  );
}

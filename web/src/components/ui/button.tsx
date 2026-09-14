"use client";

import { cn } from "@/lib/cn";
import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "ink";
type Size = "sm" | "md" | "lg";

const variants: Record<Variant, string> = {
  primary:
    "bg-teal text-white shadow-sm hover:bg-teal-bright hover:shadow-md disabled:opacity-50 border border-transparent",
  secondary:
    "bg-surface text-text-primary border border-border hover:border-teal/40 hover:bg-teal-soft disabled:opacity-50",
  ghost:
    "bg-transparent text-text-secondary border border-transparent hover:bg-teal-soft/60 hover:text-teal disabled:opacity-50",
  danger:
    "bg-danger-soft text-danger border border-transparent hover:bg-danger hover:text-white disabled:opacity-50",
  ink: "bg-hero text-white border border-transparent hover:opacity-90 disabled:opacity-50",
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
        "inline-flex items-center justify-center rounded-[var(--radius-md)] font-semibold tracking-[-0.01em] transition-[background-color,border-color,box-shadow,opacity,transform] duration-200 hover:-translate-y-px disabled:cursor-not-allowed disabled:hover:translate-y-0",
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    />
  );
}

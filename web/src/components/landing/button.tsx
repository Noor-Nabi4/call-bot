import Link from "next/link";
import type { ReactNode } from "react";

type ButtonVariant = "primary" | "secondary" | "ghost" | "inverse" | "outline-light";
type ButtonSize = "md" | "lg";

const variants: Record<ButtonVariant, string> = {
  primary:
    "bg-teal text-white shadow-sm hover:bg-teal-bright hover:shadow-md focus-visible:outline-teal",
  secondary:
    "bg-surface text-ink border border-line hover:border-teal/40 hover:bg-teal-soft focus-visible:outline-teal",
  ghost:
    "bg-transparent text-ink-soft hover:text-teal hover:bg-teal-soft/60 focus-visible:outline-teal",
  inverse:
    "bg-teal-bright text-hero hover:bg-white focus-visible:outline-white",
  "outline-light":
    "bg-transparent text-white border border-white/25 hover:border-teal-bright/70 hover:bg-white/5 focus-visible:outline-white",
};

const sizes: Record<ButtonSize, string> = {
  md: "px-5 py-2.5 text-sm",
  lg: "px-6 py-3.5 text-sm sm:text-base",
};

export type ButtonProps = {
  href: string;
  children: ReactNode;
  variant?: ButtonVariant;
  size?: ButtonSize;
  className?: string;
  external?: boolean;
};

function isInternalHref(href: string): boolean {
  return href.startsWith("/") && !href.startsWith("//");
}

export function Button({
  href,
  children,
  variant = "primary",
  size = "md",
  className = "",
  external = false,
}: ButtonProps) {
  const classes = `inline-flex items-center justify-center gap-2 rounded-[var(--radius-md)] font-semibold tracking-[-0.01em] transition-[transform,background-color,border-color,box-shadow,color] duration-200 hover:-translate-y-px focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ${variants[variant]} ${sizes[size]} ${className}`;

  if (!external && isInternalHref(href)) {
    return (
      <Link href={href} className={classes}>
        {children}
      </Link>
    );
  }

  return (
    <a
      href={href}
      className={classes}
      {...(external
        ? { target: "_blank", rel: "noopener noreferrer" }
        : {})}
    >
      {children}
    </a>
  );
}

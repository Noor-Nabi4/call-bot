import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

type VisualFrameProps = {
  children: ReactNode;
  className?: string;
  /** Accessible name for meaningful product visuals. Empty/undefined = decorative. */
  label?: string;
  tone?: "dark" | "light";
  /** Optional product-window chrome title. */
  chrome?: string;
  status?: string;
};

export function VisualFrame({
  children,
  className = "",
  label,
  tone = "dark",
  chrome,
  status,
}: VisualFrameProps) {
  const dark = tone === "dark";

  return (
    <div
      className={cn(
        "product-visual-frame relative overflow-hidden rounded-[var(--radius-xl)] border",
        dark
          ? "border-white/10 bg-[#0B1220] text-white shadow-[0_24px_60px_-28px_rgba(15,23,42,0.85)]"
          : "border-line bg-surface text-ink shadow-[0_22px_50px_-28px_rgba(15,23,42,0.28)]",
        className,
      )}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      <div
        className="pointer-events-none absolute inset-0"
        aria-hidden="true"
      >
        <div
          className={cn(
            "absolute inset-0 opacity-80",
            dark
              ? "bg-[radial-gradient(90%_70%_at_80%_0%,rgba(20,184,160,0.18),transparent_55%),radial-gradient(70%_60%_at_0%_100%,rgba(14,165,233,0.12),transparent_50%)]"
              : "bg-[radial-gradient(90%_70%_at_80%_0%,rgba(20,184,160,0.10),transparent_55%),radial-gradient(70%_60%_at_0%_100%,rgba(14,165,233,0.08),transparent_50%)]",
          )}
        />
        <div
          className={cn(
            "absolute inset-0 opacity-[0.35]",
            dark ? "mix-blend-soft-light" : "opacity-20",
          )}
          style={{
            backgroundImage:
              "linear-gradient(rgba(148,163,184,0.08) 1px, transparent 1px), linear-gradient(90deg, rgba(148,163,184,0.08) 1px, transparent 1px)",
            backgroundSize: "28px 28px",
            maskImage:
              "radial-gradient(ellipse 80% 70% at 50% 40%, black, transparent)",
          }}
        />
      </div>

      {chrome ? (
        <div
          className={cn(
            "relative flex items-center justify-between gap-3 border-b px-4 py-3",
            dark ? "border-white/10" : "border-line",
          )}
        >
          <div className="flex min-w-0 items-center gap-3">
            <span className="flex items-center gap-1.5" aria-hidden="true">
              <span
                className={cn(
                  "h-2.5 w-2.5 rounded-full",
                  dark ? "bg-white/20" : "bg-slate-300",
                )}
              />
              <span
                className={cn(
                  "h-2.5 w-2.5 rounded-full",
                  dark ? "bg-white/20" : "bg-slate-300",
                )}
              />
              <span
                className={cn(
                  "h-2.5 w-2.5 rounded-full",
                  dark ? "bg-white/20" : "bg-slate-300",
                )}
              />
            </span>
            <p
              className={cn(
                "m-0 truncate text-xs font-medium tracking-[-0.01em]",
                dark ? "text-hero-muted" : "text-muted",
              )}
            >
              {chrome}
            </p>
          </div>
          {status ? (
            <span
              className={cn(
                "inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold",
                dark
                  ? "bg-teal/15 text-teal-bright"
                  : "bg-teal-soft text-teal-deep",
              )}
            >
              <span
                className="flow-status-dot h-1.5 w-1.5 rounded-full bg-current"
                aria-hidden="true"
              />
              {status}
            </span>
          ) : null}
        </div>
      ) : null}

      <div className="relative">{children}</div>
    </div>
  );
}

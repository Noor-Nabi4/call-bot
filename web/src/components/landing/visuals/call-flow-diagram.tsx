import type { BranchStep, FlowStep } from "@/lib/marketing/visuals";
import { cn } from "@/lib/cn";

type CallFlowDiagramProps = {
  steps: readonly FlowStep[];
  branches?: readonly BranchStep[];
  compact?: boolean;
  tone?: "dark" | "light";
};

function toneClasses(tone: FlowStep["tone"], dark: boolean, focal: boolean) {
  if (tone === "accent" || focal) {
    return dark
      ? "border-teal/45 bg-teal/15 text-white shadow-[0_0_0_1px_rgba(20,184,160,0.12)]"
      : "border-teal/35 bg-teal-soft text-teal-deep shadow-[0_0_0_1px_rgba(15,118,110,0.08)]";
  }
  if (tone === "success") {
    return dark
      ? "border-emerald-400/35 bg-emerald-400/[0.12] text-emerald-100"
      : "border-emerald-600/20 bg-emerald-50 text-emerald-800";
  }
  if (tone === "muted") {
    return dark
      ? "border-white/10 bg-white/[0.03] text-hero-muted"
      : "border-line bg-bg text-muted";
  }
  return dark
    ? "border-white/10 bg-white/[0.045] text-white"
    : "border-line bg-bg text-ink";
}

function Connector({ dark }: { dark: boolean }) {
  return (
    <div className="flow-connector flex flex-col items-center py-1" aria-hidden="true">
      <span
        className={cn(
          "block w-px flex-1 min-h-3",
          dark ? "bg-gradient-to-b from-white/25 to-teal/40" : "bg-gradient-to-b from-line-strong to-teal/40",
        )}
      />
      <svg
        width="10"
        height="8"
        viewBox="0 0 10 8"
        className={dark ? "text-teal-bright" : "text-teal"}
      >
        <path
          d="M1 1.5L5 6.5L9 1.5"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
}

export function CallFlowDiagram({
  steps,
  branches,
  compact = false,
  tone = "dark",
}: CallFlowDiagramProps) {
  const dark = tone === "dark";
  const accentIndex = Math.max(
    0,
    steps.findIndex((step) => step.tone === "accent"),
  );

  return (
    <div className={cn("flow-diagram", compact ? "space-y-1.5" : "space-y-2")}>
      {steps.map((step, index) => {
        const focal = index === accentIndex || step.tone === "accent";
        return (
          <div
            key={`${step.label}-${index}`}
            className="flow-node-wrap flex flex-col items-stretch"
            style={{ ["--flow-delay" as string]: `${index * 70}ms` }}
          >
            <div
              className={cn(
                "flow-node relative rounded-[14px] border px-3.5 transition-[transform,box-shadow] duration-300",
                compact ? "py-2.5" : "py-3",
                toneClasses(step.tone, dark, focal),
                focal && "flow-node-focal",
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span
                      className={cn(
                        "inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-[10px] font-semibold tracking-[0.08em]",
                        focal
                          ? dark
                            ? "bg-teal/25 text-teal-bright"
                            : "bg-teal/15 text-teal-deep"
                          : dark
                            ? "bg-white/8 text-hero-muted"
                            : "bg-bg text-muted",
                      )}
                    >
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    {focal ? (
                      <span
                        className={cn(
                          "text-[10px] font-semibold tracking-[0.12em] uppercase",
                          dark ? "text-teal-bright" : "text-teal",
                        )}
                      >
                        AI active
                      </span>
                    ) : null}
                    {step.tone === "success" ? (
                      <span
                        className={cn(
                          "text-[10px] font-semibold tracking-[0.12em] uppercase",
                          dark ? "text-emerald-300" : "text-emerald-700",
                        )}
                      >
                        Done
                      </span>
                    ) : null}
                  </div>
                  <p
                    className={cn(
                      "mt-1.5 m-0 font-semibold tracking-[-0.02em]",
                      focal ? "text-[15px] sm:text-base" : "text-sm",
                    )}
                  >
                    {step.label}
                  </p>
                  {step.detail ? (
                    <p
                      className={cn(
                        "mt-0.5 m-0 text-xs leading-snug",
                        dark ? "text-hero-muted" : "text-muted",
                      )}
                    >
                      {step.detail}
                    </p>
                  ) : null}
                </div>
                {focal ? (
                  <span
                    className={cn(
                      "flow-pulse mt-1 h-2 w-2 shrink-0 rounded-full",
                      dark ? "bg-teal-bright" : "bg-teal",
                    )}
                    aria-hidden="true"
                  />
                ) : null}
              </div>
            </div>
            {index < steps.length - 1 ||
            (branches && index === steps.length - 1) ? (
              <Connector dark={dark} />
            ) : null}
          </div>
        );
      })}

      {branches && branches.length > 0 ? (
        <div
          className={cn(
            "grid gap-2 rounded-[14px] border p-3 sm:grid-cols-2",
            dark ? "border-white/10 bg-white/[0.03]" : "border-line bg-bg",
          )}
        >
          {branches.map((branch) => (
            <div
              key={branch.label}
              className={cn(
                "rounded-[10px] border px-3 py-2 text-xs font-medium",
                dark
                  ? "border-white/10 bg-white/[0.04] text-hero-muted"
                  : "border-line bg-surface text-muted",
              )}
            >
              <span
                className={dark ? "text-teal-bright" : "text-teal"}
                aria-hidden="true"
              >
                →{" "}
              </span>
              {branch.label}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

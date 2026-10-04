import { CallFlowDiagram } from "@/components/landing/visuals/call-flow-diagram";
import { HumanBusinessVisual } from "@/components/landing/visuals/human-business-visual";
import { HumanProductVisual } from "@/components/landing/visuals/human-product-visual";
import { Marketing3DVisual } from "@/components/landing/visuals/marketing-3d-visual";
import { VisualFrame } from "@/components/landing/visuals/visual-frame";
import { Waveform } from "@/components/landing/visuals/waveform";
import { cn } from "@/lib/cn";
import type { StoryMedia } from "@/lib/marketing/human-assets";
import type { HumanBusinessVisualConfig } from "@/lib/marketing/human-business-visuals";
import type { ThreeDAsset } from "@/lib/marketing/three-d-assets";
import type { FlowStep } from "@/lib/marketing/visuals";

export type SectionFlowVariant = "flow" | "spotlight" | "stack" | "handoff";

type SectionFlowVisualProps = {
  title: string;
  alt: string;
  steps: readonly FlowStep[];
  tone?: "dark" | "light";
  variant?: SectionFlowVariant;
  /** @deprecated Prefer `media` for human + 3D storytelling. */
  image?: ThreeDAsset;
  media?: StoryMedia;
  /** Optional campaign visual for human-product story bands. */
  businessVisual?: HumanBusinessVisualConfig | null;
};

function deriveStatus(steps: readonly FlowStep[]): string {
  if (steps.some((step) => step.tone === "success")) return "Outcome ready";
  if (steps.some((step) => step.tone === "accent")) return "AI Agent active";
  return "Live workflow";
}

function deriveMeta(steps: readonly FlowStep[]): string {
  const success = steps.find((step) => step.tone === "success");
  if (success?.detail) return success.detail;
  if (success) return success.label;
  return "Incoming call · 00:42";
}

function SatelliteCard({
  label,
  value,
  dark,
  className,
}: {
  label: string;
  value: string;
  dark: boolean;
  className?: string;
}) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "rounded-[12px] border px-3 py-2 shadow-[var(--shadow-sm)] backdrop-blur",
        dark
          ? "border-white/10 bg-[#102033]/92 text-white"
          : "border-line bg-surface/95 text-ink",
        className,
      )}
    >
      <p
        className={cn(
          "m-0 text-[10px] font-semibold tracking-[0.1em] uppercase",
          dark ? "text-hero-muted" : "text-muted",
        )}
      >
        {label}
      </p>
      <p className="mt-0.5 m-0 text-xs font-semibold tracking-[-0.01em]">
        {value}
      </p>
    </div>
  );
}

function SpotlightLayout({
  steps,
  dark,
}: {
  steps: readonly FlowStep[];
  dark: boolean;
}) {
  const accent =
    steps.find((step) => step.tone === "accent") || steps[1] || steps[0];
  const others = steps.filter((step) => step !== accent).slice(0, 4);

  return (
    <div className="relative">
      <div
        className={cn(
          "rounded-[18px] border p-4 sm:p-5",
          dark
            ? "border-teal/35 bg-teal/10 shadow-[0_0_0_1px_rgba(20,184,160,0.08)]"
            : "border-teal/25 bg-teal-soft",
        )}
      >
        <div className="flex items-center justify-between gap-3">
          <p
            className={cn(
              "m-0 text-[11px] font-semibold tracking-[0.12em] uppercase",
              dark ? "text-teal-bright" : "text-teal-deep",
            )}
          >
            AI Agent
          </p>
          <span
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-semibold",
              dark ? "bg-teal/20 text-teal-bright" : "bg-white text-teal",
            )}
          >
            <span className="flow-pulse h-1.5 w-1.5 rounded-full bg-current" />
            Active
          </span>
        </div>
        <p
          className={cn(
            "mt-2 m-0 text-lg font-semibold tracking-[-0.03em]",
            dark ? "text-white" : "text-ink",
          )}
        >
          {accent?.label}
        </p>
        {accent?.detail ? (
          <p
            className={cn(
              "mt-1 m-0 text-sm",
              dark ? "text-hero-muted" : "text-muted",
            )}
          >
            {accent.detail}
          </p>
        ) : null}
        <Waveform className="mt-4 opacity-90" bars={22} />
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2">
        {others.map((step) => (
          <div
            key={step.label}
            className={cn(
              "rounded-[12px] border px-3 py-2.5",
              dark
                ? "border-white/10 bg-white/[0.04]"
                : "border-line bg-bg",
            )}
          >
            <p
              className={cn(
                "m-0 text-[10px] font-semibold tracking-[0.1em] uppercase",
                dark ? "text-hero-muted" : "text-muted",
              )}
            >
              {step.tone === "success" ? "Result" : "Step"}
            </p>
            <p
              className={cn(
                "mt-1 m-0 text-xs font-semibold",
                dark ? "text-white" : "text-ink",
              )}
            >
              {step.label}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function StackLayout({
  steps,
  dark,
}: {
  steps: readonly FlowStep[];
  dark: boolean;
}) {
  return (
    <div className="relative space-y-2.5">
      {steps.map((step, index) => (
        <div
          key={step.label}
          className={cn(
            "flow-node-wrap rounded-[14px] border px-3.5 py-3",
            step.tone === "accent"
              ? dark
                ? "border-teal/40 bg-teal/15"
                : "border-teal/30 bg-teal-soft"
              : dark
                ? "border-white/10 bg-white/[0.04]"
                : "border-line bg-bg",
          )}
          style={{
            ["--flow-delay" as string]: `${index * 70}ms`,
          }}
        >
          <div className="flex items-center justify-between gap-2">
            <p
              className={cn(
                "m-0 text-sm font-semibold tracking-[-0.02em]",
                dark ? "text-white" : "text-ink",
              )}
            >
              {step.label}
            </p>
            <span
              className={cn(
                "text-[10px] font-semibold tracking-[0.1em] uppercase",
                dark ? "text-hero-muted" : "text-muted",
              )}
            >
              {String(index + 1).padStart(2, "0")}
            </span>
          </div>
          {step.detail ? (
            <p
              className={cn(
                "mt-1 m-0 text-xs",
                dark ? "text-hero-muted" : "text-muted",
              )}
            >
              {step.detail}
            </p>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function HandoffLayout({
  steps,
  dark,
}: {
  steps: readonly FlowStep[];
  dark: boolean;
}) {
  const ai =
    steps.find((step) => step.tone === "accent") || steps[0];
  const human =
    steps.find((step) => step.tone === "muted") ||
    steps[steps.length - 1];
  const middle = steps.filter((step) => step !== ai && step !== human);

  return (
    <div className="grid gap-3">
      <div
        className={cn(
          "rounded-[16px] border p-4",
          dark ? "border-teal/35 bg-teal/10" : "border-teal/25 bg-teal-soft",
        )}
      >
        <p
          className={cn(
            "m-0 text-[11px] font-semibold tracking-[0.12em] uppercase",
            dark ? "text-teal-bright" : "text-teal-deep",
          )}
        >
          AI handles routine
        </p>
        <p
          className={cn(
            "mt-1 m-0 text-base font-semibold",
            dark ? "text-white" : "text-ink",
          )}
        >
          {ai?.label}
        </p>
        {ai?.detail ? (
          <p
            className={cn(
              "mt-1 m-0 text-xs",
              dark ? "text-hero-muted" : "text-muted",
            )}
          >
            {ai.detail}
          </p>
        ) : null}
      </div>

      {middle.length > 0 ? (
        <div className="grid grid-cols-2 gap-2">
          {middle.slice(0, 2).map((step) => (
            <div
              key={step.label}
              className={cn(
                "rounded-[12px] border px-3 py-2.5 text-xs font-semibold",
                dark
                  ? "border-white/10 bg-white/[0.04] text-white"
                  : "border-line bg-bg text-ink",
              )}
            >
              {step.label}
            </div>
          ))}
        </div>
      ) : null}

      <div
        className={cn(
          "rounded-[16px] border p-4",
          dark ? "border-white/12 bg-white/[0.04]" : "border-line bg-bg",
        )}
      >
        <p
          className={cn(
            "m-0 text-[11px] font-semibold tracking-[0.12em] uppercase",
            dark ? "text-hero-muted" : "text-muted",
          )}
        >
          Human when it matters
        </p>
        <p
          className={cn(
            "mt-1 m-0 text-base font-semibold",
            dark ? "text-white" : "text-ink",
          )}
        >
          {human?.label}
        </p>
        {human?.detail ? (
          <p
            className={cn(
              "mt-1 m-0 text-xs",
              dark ? "text-hero-muted" : "text-muted",
            )}
          >
            {human.detail}
          </p>
        ) : null}
        <p
          className={cn(
            "mt-3 m-0 inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold",
            dark ? "bg-white/8 text-hero-muted" : "bg-surface text-muted",
          )}
        >
          Context preserved
        </p>
      </div>
    </div>
  );
}

function CompactStepStrip({
  steps,
  dark,
}: {
  steps: readonly FlowStep[];
  dark: boolean;
}) {
  return (
    <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
      {steps.slice(0, 4).map((step, index) => (
        <div
          key={step.label}
          className={cn(
            "rounded-[12px] border px-2.5 py-2",
            step.tone === "accent"
              ? dark
                ? "border-teal/35 bg-teal/12"
                : "border-teal/25 bg-teal-soft"
              : dark
                ? "border-white/10 bg-white/[0.04]"
                : "border-line bg-bg",
          )}
        >
          <p
            className={cn(
              "m-0 text-[10px] font-semibold tracking-[0.1em] uppercase",
              dark ? "text-hero-muted" : "text-muted",
            )}
          >
            {String(index + 1).padStart(2, "0")}
          </p>
          <p
            className={cn(
              "mt-1 m-0 text-xs font-semibold leading-snug",
              dark ? "text-white" : "text-ink",
            )}
          >
            {step.label}
          </p>
        </div>
      ))}
    </div>
  );
}

function MediaBand({
  media,
  image,
  variant,
  dark,
  businessVisual,
}: {
  media?: StoryMedia;
  image?: ThreeDAsset;
  variant: SectionFlowVariant;
  dark: boolean;
  businessVisual?: HumanBusinessVisualConfig | null;
}) {
  const composition = media?.composition;
  const human = media?.human;
  const threeD = media?.threeD || image;
  const large =
    variant === "spotlight" ||
    composition === "human-product" ||
    composition === "human-handoff";

  if (composition === "human-product" && businessVisual) {
    return (
      <div
        className={cn(
          "border-b p-3 sm:p-4",
          dark ? "border-white/10" : "border-line",
        )}
      >
        <HumanBusinessVisual
          config={businessVisual}
          variant="spotlight"
          decorative
          className={cn(
            "human-business-surface w-full",
            large
              ? "aspect-[16/10] sm:aspect-[16/9]"
              : "h-40 sm:h-48",
          )}
          sizes="(max-width: 768px) 100vw, 520px"
        />
      </div>
    );
  }

  if (
    (composition === "human-product" ||
      composition === "human-3d" ||
      composition === "human-handoff") &&
    human
  ) {
    return (
      <div
        className={cn(
          "border-b p-3 sm:p-4",
          dark ? "border-white/10" : "border-line",
        )}
      >
        <HumanProductVisual
          human={human}
          threeD={
            composition === "human-product" || composition === "human-3d"
              ? threeD
              : composition === "human-handoff"
                ? threeD
                : undefined
          }
          variant={
            composition === "human-handoff"
              ? "handoff"
              : composition === "human-3d"
                ? "overlay"
                : "overlay"
          }
          decorative
          className={cn(
            "human-product-surface w-full",
            large
              ? "aspect-[16/10] sm:aspect-[16/9]"
              : "h-40 sm:h-48",
          )}
          sizes="(max-width: 768px) 100vw, 520px"
        />
      </div>
    );
  }

  if (threeD) {
    return (
      <div
        className={cn(
          "border-b p-3 sm:p-4",
          dark ? "border-white/10" : "border-line",
        )}
      >
        <Marketing3DVisual
          asset={threeD}
          float={variant === "spotlight"}
          decorative
          className={cn(
            "marketing-3d-surface w-full",
            large
              ? "aspect-[16/10] sm:aspect-[16/9]"
              : "h-40 sm:h-48",
          )}
          sizes="(max-width: 768px) 100vw, 520px"
        />
      </div>
    );
  }

  return null;
}

/** Compact product-flow visual for alternating storytelling sections. */
export function SectionFlowVisual({
  title,
  alt,
  steps,
  tone = "dark",
  variant = "flow",
  image,
  media,
  businessVisual,
}: SectionFlowVisualProps) {
  const dark = tone === "dark";
  const status = deriveStatus(steps);
  const meta = deriveMeta(steps);
  const hasMediaBand = Boolean(
    media?.human || media?.threeD || image || businessVisual,
  );
  const humanLed =
    media?.composition === "human-product" ||
    media?.composition === "human-3d" ||
    media?.composition === "human-handoff";

  return (
    <div className="relative">
      <VisualFrame
        label={alt}
        tone={tone}
        chrome={title}
        status={status}
        className="min-h-[20rem] sm:min-h-[24rem]"
      >
        <MediaBand
          media={media}
          image={image}
          variant={variant}
          dark={dark}
          businessVisual={businessVisual}
        />

        <div className="p-4 sm:p-6">
          <div className="mb-3 flex items-center justify-between gap-3 sm:mb-4">
            <p
              className={cn(
                "m-0 text-xs",
                dark ? "text-hero-muted" : "text-muted",
              )}
            >
              {meta}
            </p>
            <span
              className={cn(
                "rounded-full px-2.5 py-1 text-[11px] font-semibold",
                dark
                  ? "bg-white/8 text-hero-muted"
                  : "bg-bg text-muted",
              )}
            >
              Live
            </span>
          </div>

          {variant === "spotlight" ? (
            hasMediaBand || humanLed ? (
              <CompactStepStrip steps={steps} dark={dark} />
            ) : (
              <SpotlightLayout steps={steps} dark={dark} />
            )
          ) : null}
          {variant === "stack" ? (
            hasMediaBand || humanLed ? (
              <CompactStepStrip steps={steps} dark={dark} />
            ) : (
              <StackLayout steps={steps} dark={dark} />
            )
          ) : null}
          {variant === "handoff" ? (
            <HandoffLayout steps={steps} dark={dark} />
          ) : null}
          {variant === "flow" ? (
            <CallFlowDiagram steps={steps} compact tone={tone} />
          ) : null}
        </div>
      </VisualFrame>

      {variant === "spotlight" || variant === "flow" ? (
        <>
          <SatelliteCard
            label="Status"
            value={status}
            dark={dark}
            className="animate-float absolute -left-1 top-16 z-[2] hidden w-[8.5rem] lg:-left-3 lg:block"
          />
          <SatelliteCard
            label="Next step"
            value={steps[steps.length - 1]?.label || "Complete"}
            dark={dark}
            className="animate-float-slow absolute -right-1 bottom-14 z-[2] hidden w-[9rem] lg:-right-3 lg:block"
          />
        </>
      ) : null}
    </div>
  );
}

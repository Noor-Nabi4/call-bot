import type { ReactNode } from "react";
import { Button } from "@/components/landing/button";
import { Reveal } from "@/components/landing/reveal";
import { cn } from "@/lib/cn";

export type AlternatingFeatureSectionProps = {
  eyebrow: string;
  title: string;
  description: string;
  bullets: readonly string[];
  visual: ReactNode;
  reverse?: boolean;
  badge?: string;
  cta?: { href: string; label: string };
  tone?: "bg" | "surface" | "elevated";
  id?: string;
};

const toneClass: Record<
  NonNullable<AlternatingFeatureSectionProps["tone"]>,
  string
> = {
  bg: "bg-bg",
  surface: "bg-surface",
  elevated: "bg-surface",
};

export function AlternatingFeatureSection({
  eyebrow,
  title,
  description,
  bullets,
  visual,
  reverse = false,
  badge,
  cta,
  tone = "bg",
  id,
}: AlternatingFeatureSectionProps) {
  const headingId = id ? `${id}-heading` : undefined;

  return (
    <section
      id={id}
      className={cn(
        "section-pad-story relative border-t border-line",
        toneClass[tone],
      )}
      aria-labelledby={headingId}
    >
      {tone === "elevated" ? (
        <div
          className="pointer-events-none absolute inset-0 bg-gradient-to-br from-teal-soft/45 via-transparent to-blue-soft/25"
          aria-hidden="true"
        />
      ) : null}
      {tone === "surface" ? (
        <div
          className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-teal/20 to-transparent"
          aria-hidden="true"
        />
      ) : null}

      <div className="relative z-[1] content-width">
        <div
          className={cn(
            "grid items-center gap-10 lg:grid-cols-2 lg:gap-12 xl:gap-16",
            reverse && "lg:[&>*:first-child]:order-2",
          )}
        >
          <Reveal variant={reverse ? "right" : "left"}>
            <div className="w-full max-w-none lg:max-w-[34rem] xl:max-w-none">
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <p className="m-0 inline-flex rounded-[var(--radius-sm)] bg-teal-soft px-2.5 py-1 text-[11px] font-semibold tracking-[0.14em] text-teal-deep uppercase">
                  {eyebrow}
                </p>
                {badge ? (
                  <span className="inline-flex rounded-full border border-line bg-bg/80 px-2.5 py-1 text-[11px] font-semibold text-muted backdrop-blur">
                    {badge}
                  </span>
                ) : null}
              </div>
              <h2
                id={headingId}
                className="font-display m-0 text-[clamp(1.8rem,3.5vw,2.65rem)] font-semibold leading-[1.08] tracking-[-0.04em] text-ink"
              >
                {title}
              </h2>
              <p className="mt-4 m-0 max-w-[38rem] text-base leading-relaxed text-muted sm:text-lg">
                {description}
              </p>
              <ul className="story-feature-list mt-7 m-0 flex list-none flex-col gap-2.5 p-0">
                {bullets.map((bullet) => (
                  <li
                    key={bullet}
                    className="story-feature-item flex items-start gap-3 rounded-[14px] border border-transparent px-2.5 py-2 text-[15px] leading-snug text-ink-soft transition-[background-color,border-color,transform] duration-200 hover:border-line hover:bg-surface/80"
                  >
                    <span
                      className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-teal-soft text-teal"
                      aria-hidden="true"
                    >
                      <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                        <path
                          d="M2.5 6.2l2.2 2.2 4.8-4.8"
                          stroke="currentColor"
                          strokeWidth="1.6"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    </span>
                    <span className="font-medium tracking-[-0.01em]">{bullet}</span>
                  </li>
                ))}
              </ul>
              {cta ? (
                <div className="mt-8">
                  <Button href={cta.href} variant="secondary">
                    {cta.label}
                  </Button>
                </div>
              ) : null}
            </div>
          </Reveal>

          <Reveal variant={reverse ? "left" : "right"}>
            <div className="story-visual-slot relative mx-auto w-full max-w-xl overflow-x-clip px-1 sm:px-2 lg:max-w-none lg:px-0">
              {visual}
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

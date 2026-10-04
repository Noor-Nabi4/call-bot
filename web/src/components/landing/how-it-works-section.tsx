"use client";

import { useState } from "react";
import { Reveal } from "@/components/landing/reveal";

export type HowItWorksStep = {
  title: string;
  body: string;
  previewLabel?: string;
  previewLines?: readonly string[];
};

type HowItWorksSectionProps = {
  title: string;
  supporting: string;
  steps: readonly HowItWorksStep[];
};

function StepPreview({
  label,
  lines,
}: {
  label: string;
  lines: readonly string[];
}) {
  return (
    <div
      className="step-preview-enter relative hidden h-full min-h-[16rem] w-full max-w-[13.5rem] shrink-0 overflow-hidden rounded-[16px] border border-white/80 bg-gradient-to-b from-[#0c2228] to-[#12353a] shadow-[-2px_4px_15px_rgba(0,0,0,0.2)] sm:block"
      aria-hidden="true"
    >
      <div className="absolute inset-0 opacity-40">
        <div className="absolute -right-6 top-8 h-32 w-32 rounded-full bg-teal/40 blur-2xl" />
        <div className="absolute -left-4 bottom-10 h-24 w-24 rounded-full bg-blue/30 blur-2xl" />
      </div>
      <div className="relative flex h-full flex-col p-4">
        <p className="m-0 text-[10px] font-semibold tracking-[0.14em] text-teal-bright uppercase">
          {label}
        </p>
        <div className="mt-4 flex flex-1 flex-col gap-2">
          {lines.map((line) => (
            <div
              key={line}
              className="rounded-[10px] border border-white/10 bg-white/5 px-3 py-2.5"
            >
              <p className="m-0 text-xs leading-snug text-white/85">{line}</p>
            </div>
          ))}
        </div>
        <div className="mt-auto h-1.5 overflow-hidden rounded-full bg-white/10">
          <div className="h-full w-2/3 rounded-full bg-gradient-to-r from-teal-bright to-blue" />
        </div>
      </div>
    </div>
  );
}

export function HowItWorksSection({
  title,
  supporting,
  steps,
}: HowItWorksSectionProps) {
  const [active, setActive] = useState(0);

  return (
    <section
      id="how-it-works"
      className="section-pad border-t border-line bg-bg"
      aria-labelledby="how-heading"
    >
      <div className="content-width">
        <Reveal>
          <div className="max-w-2xl">
            <p className="m-0 mb-3 inline-flex rounded-[var(--radius-sm)] bg-teal-soft px-2.5 py-1 text-[11px] font-semibold tracking-[0.12em] text-teal-deep uppercase">
              Getting started
            </p>
            <h2
              id="how-heading"
              className="font-display m-0 text-[clamp(1.85rem,3.8vw,2.85rem)] font-semibold leading-[1.08] tracking-[-0.04em] text-ink"
            >
              {title}
            </h2>
            <p className="mt-4 m-0 text-base leading-relaxed text-muted sm:text-lg">
              {supporting}
            </p>
          </div>
        </Reveal>

        <Reveal variant="scale" className="mt-10">
          <div
            className="rounded-[24px] border border-line bg-surface p-2 shadow-[var(--shadow-sm)]"
            role="tablist"
            aria-label="How Call & Flow works"
          >
            <div className="flex flex-col gap-2 lg:flex-row lg:items-stretch">
              {steps.map((step, index) => {
                const isOpen = active === index;
                const number = String(index + 1).padStart(2, "0");

                return (
                  <button
                    key={step.title}
                    type="button"
                    role="tab"
                    aria-selected={isOpen}
                    aria-controls={`how-panel-${index}`}
                    id={`how-tab-${index}`}
                    onClick={() => setActive(index)}
                    onMouseEnter={() => {
                      if (
                        typeof window !== "undefined" &&
                        window.matchMedia("(hover: hover)").matches
                      ) {
                        setActive(index);
                      }
                    }}
                    className={`how-step-card group flex min-h-[12rem] flex-col rounded-[20px] border-2 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal ${
                      isOpen
                        ? "border-white bg-[#f4f6f8] shadow-[0_8px_20px_rgba(0,0,0,0.1)] lg:flex-[1.65]"
                        : "border-transparent bg-[#f4f6f8]/80 hover:bg-[#f4f6f8] lg:flex-1"
                    }`}
                  >
                    <div
                      id={`how-panel-${index}`}
                      role="tabpanel"
                      aria-labelledby={`how-tab-${index}`}
                      className={`flex h-full gap-4 p-5 sm:p-6 ${
                        isOpen ? "flex-row" : "flex-col"
                      }`}
                    >
                      <div className="flex min-w-0 flex-1 flex-col justify-between gap-8">
                        <p className="m-0 text-lg tracking-[-0.03em] text-[#AEAEAE]">
                          {number}
                        </p>
                        <div>
                          <h3 className="m-0 text-[1.35rem] font-medium tracking-[-0.04em] text-ink-soft sm:text-[1.5rem]">
                            {step.title}
                          </h3>
                          <p
                            className={`mt-2 m-0 text-sm leading-relaxed text-muted transition-opacity duration-300 sm:text-[15px] ${
                              isOpen ? "line-clamp-none" : "line-clamp-3"
                            }`}
                          >
                            {step.body}
                          </p>
                        </div>
                      </div>

                      {isOpen ? (
                        <StepPreview
                          label={step.previewLabel || "Live preview"}
                          lines={
                            step.previewLines || [
                              "Agent ready",
                              "Number connected",
                              "Calls answered",
                            ]
                          }
                        />
                      ) : null}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

"use client";

import { useId, useState } from "react";
import { Reveal } from "@/components/landing/reveal";

export type FeatureShowcaseItem = {
  tab: string;
  badge: string;
  title: string;
  body: string;
  previewLabel: string;
  previewLines: readonly string[];
};

type FeatureShowcaseProps = {
  title: string;
  supporting: string;
  items: readonly FeatureShowcaseItem[];
};

function ShowcasePreview({
  label,
  lines,
}: {
  label: string;
  lines: readonly string[];
}) {
  return (
    <div
      className="relative flex min-h-[18rem] flex-1 flex-col overflow-hidden rounded-[20px] bg-[#f4f6f8] p-4 sm:min-h-[22rem] sm:p-5"
      aria-hidden="true"
    >
      <div className="absolute inset-0 opacity-70">
        <div className="absolute -left-10 top-8 h-40 w-40 rounded-full bg-teal/15 blur-3xl" />
        <div className="absolute -right-8 bottom-6 h-36 w-36 rounded-full bg-blue/15 blur-3xl" />
      </div>

      <div className="relative flex flex-1 flex-col gap-3">
        <div className="overflow-hidden rounded-[12px] border border-line bg-surface shadow-[0_8px_28px_rgba(12,26,30,0.1)]">
          <div className="flex items-center gap-2 border-b border-line px-3 py-2.5">
            <span className="h-2 w-2 rounded-full bg-line-strong" />
            <span className="h-2 w-2 rounded-full bg-line-strong" />
            <span className="h-2 w-2 rounded-full bg-line-strong" />
            <span className="ml-2 text-[11px] font-medium text-muted">
              {label}
            </span>
          </div>
          <div className="space-y-2.5 p-3 sm:p-4">
            {lines.map((line, index) => (
              <div
                key={line}
                className="flex items-center justify-between gap-3 rounded-[10px] border border-line bg-bg px-3 py-2.5"
                style={{ animationDelay: `${index * 60}ms` }}
              >
                <span className="text-sm font-medium tracking-[-0.02em] text-ink-soft">
                  {line}
                </span>
                <span className="h-2 w-2 shrink-0 rounded-full bg-teal-bright" />
              </div>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-[12px] border border-line bg-surface/90 p-3 shadow-[var(--shadow-sm)]">
            <p className="m-0 text-[10px] tracking-[0.1em] text-muted uppercase">
              Status
            </p>
            <p className="mt-1 m-0 text-sm font-semibold text-ink">Active</p>
          </div>
          <div className="rounded-[12px] border border-line bg-surface/90 p-3 shadow-[var(--shadow-sm)]">
            <p className="m-0 text-[10px] tracking-[0.1em] text-muted uppercase">
              Outcome
            </p>
            <p className="mt-1 m-0 text-sm font-semibold text-teal">Ready</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export function FeatureShowcase({
  title,
  supporting,
  items,
}: FeatureShowcaseProps) {
  const tabsId = useId();
  const [active, setActive] = useState(0);
  const current = items[active] ?? items[0];

  if (!current) return null;

  return (
    <section
      id="platform"
      className="section-pad border-t border-line bg-bg"
      aria-labelledby="platform-heading"
    >
      <div className="content-width">
        <Reveal>
          <div className="mx-auto max-w-2xl text-center">
            <p className="m-0 mb-3 inline-flex rounded-[var(--radius-sm)] bg-teal-soft px-2.5 py-1 text-[11px] font-semibold tracking-[0.12em] text-teal-deep uppercase">
              Platform
            </p>
            <h2
              id="platform-heading"
              className="font-display m-0 text-[clamp(1.9rem,4vw,2.85rem)] font-semibold leading-[1.1] tracking-[-0.045em] text-ink"
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
            id={tabsId}
            role="tablist"
            aria-label="Platform capabilities"
            className="mx-auto flex max-w-5xl flex-wrap items-center justify-center gap-1.5 rounded-full border border-line bg-surface p-1.5 shadow-[var(--shadow-sm)] sm:gap-2 sm:p-2"
          >
            {items.map((item, index) => {
              const selected = index === active;
              return (
                <button
                  key={item.tab}
                  type="button"
                  role="tab"
                  aria-selected={selected}
                  aria-controls={`platform-panel-${index}`}
                  id={`platform-tab-${index}`}
                  onClick={() => setActive(index)}
                  className={`rounded-full px-3.5 py-2 text-sm tracking-[-0.02em] transition-[background-color,color,box-shadow,transform] duration-300 sm:px-4 ${
                    selected
                      ? "bg-ink font-medium text-white shadow-[var(--shadow-sm)]"
                      : "bg-transparent font-normal text-ink-soft hover:bg-bg hover:text-ink"
                  }`}
                >
                  {item.tab}
                </button>
              );
            })}
          </div>
        </Reveal>

        <Reveal className="mt-6" variant="up">
          <div
            id={`platform-panel-${active}`}
            role="tabpanel"
            aria-labelledby={`platform-tab-${active}`}
            className="overflow-hidden rounded-[24px] border border-line bg-surface p-2 shadow-[var(--shadow-md)] sm:p-2.5"
          >
            <div
              key={current.tab}
              className="showcase-panel-enter grid items-stretch gap-2 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)] lg:gap-4 lg:p-1.5 lg:pr-6"
            >
              <ShowcasePreview
                label={current.previewLabel}
                lines={current.previewLines}
              />
              <div className="flex flex-col justify-center gap-5 px-4 py-6 sm:px-6 lg:py-8">
                <p className="m-0 inline-flex w-fit rounded-full bg-teal-soft px-3 py-1.5 text-[11px] font-semibold tracking-[0.08em] text-teal-deep uppercase">
                  {current.badge}
                </p>
                <h3 className="font-display m-0 text-[clamp(1.55rem,3vw,2.15rem)] font-medium leading-[1.15] tracking-[-0.04em] text-ink">
                  {current.title}
                </h3>
                <p className="m-0 max-w-md text-base leading-relaxed text-muted">
                  {current.body}
                </p>
              </div>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

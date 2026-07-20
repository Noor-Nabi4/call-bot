"use client";

import { useId, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/landing/button";

export type PricingPlanOption = {
  key: string;
  name: string;
  tagline: string;
  price: string;
  features: readonly string[];
  cta: string;
  href: string;
  popular?: boolean;
};

type PricingSectionProps = {
  title: string;
  supporting: string;
  compareHref: string;
  compareLabel: string;
  plans: PricingPlanOption[];
  emptyNote: string;
};

function CheckIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
      <circle cx="9" cy="9" r="8" stroke="rgba(255,255,255,0.35)" strokeWidth="1.25" />
      <path
        d="M5.5 9.2l2.2 2.2 4.8-4.8"
        stroke="rgba(255,255,255,0.9)"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ArrowIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <path
        d="M3 7h8M8 3.5L11.5 7 8 10.5"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function PricingSection({
  title,
  supporting,
  compareHref,
  compareLabel,
  plans,
  emptyNote,
}: PricingSectionProps) {
  const listId = useId();
  const defaultKey =
    plans.find((plan) => plan.popular)?.key ?? plans[0]?.key ?? "";
  const [selectedKey, setSelectedKey] = useState(defaultKey);
  const selected =
    plans.find((plan) => plan.key === selectedKey) ?? plans[0] ?? null;

  if (plans.length === 0) {
    return (
      <section
        id="pricing"
        className="section-pad relative overflow-hidden border-t border-line"
        aria-labelledby="pricing-heading"
      >
        <div className="pricing-atmosphere" aria-hidden="true" />
        <div className="relative z-[1] content-width">
          <h2
            id="pricing-heading"
            className="font-display m-0 text-[clamp(2rem,4vw,2.75rem)] font-semibold tracking-[-0.04em] text-ink"
          >
            {title}
          </h2>
          <p className="mt-4 m-0 max-w-xl text-base text-muted">{emptyNote}</p>
          <div className="mt-6">
            <Button href={compareHref} variant="primary">
              {compareLabel}
            </Button>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section
      id="pricing"
      className="section-pad relative overflow-hidden border-t border-line"
      aria-labelledby="pricing-heading"
    >
      <div className="pricing-atmosphere" aria-hidden="true" />

      <div className="relative z-[1] content-width">
        <div className="grid items-start gap-10 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)] lg:gap-14">
          <div className="flex flex-col gap-10">
            <div>
              <p className="m-0 mb-3 inline-flex rounded-[var(--radius-sm)] bg-teal-soft px-2.5 py-1 text-[11px] font-semibold tracking-[0.12em] text-teal-deep uppercase">
                Pricing
              </p>
              <h2
                id="pricing-heading"
                className="pricing-title-gradient font-display m-0 text-[clamp(2.15rem,4.5vw,3rem)] font-semibold leading-[1.1] tracking-[-0.045em]"
              >
                {title}
              </h2>
              <p className="mt-4 m-0 max-w-md text-base leading-relaxed text-muted">
                {supporting}
              </p>
            </div>

            <div
              id={listId}
              role="listbox"
              aria-label="Choose a plan"
              className="rounded-[24px] bg-surface p-2 shadow-[var(--shadow-md)]"
            >
              {plans.map((plan) => {
                const active = plan.key === selected?.key;
                return (
                  <button
                    key={plan.key}
                    type="button"
                    role="option"
                    aria-selected={active}
                    onClick={() => setSelectedKey(plan.key)}
                    className={`flex w-full items-center justify-between gap-4 rounded-[16px] px-5 py-4 text-left transition-[background-color,box-shadow,opacity,transform] duration-200 ${
                      active
                        ? "bg-bg shadow-[5px_8px_18px_rgba(12,26,30,0.12)]"
                        : "bg-transparent opacity-60 hover:opacity-90"
                    }`}
                  >
                    <span className="min-w-0">
                      <span className="block text-lg font-semibold tracking-[-0.03em] text-ink-soft">
                        {plan.name}
                      </span>
                      <span className="mt-0.5 block text-sm tracking-[-0.02em] text-muted">
                        {plan.tagline}
                      </span>
                    </span>
                    <span
                      className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border transition-colors ${
                        active
                          ? "border-teal bg-teal text-white"
                          : "border-line text-transparent"
                      }`}
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
                  </button>
                );
              })}
            </div>

            <Link
              href={compareHref}
              className="text-sm font-semibold text-teal transition-colors hover:text-teal-deep"
            >
              {compareLabel} →
            </Link>
          </div>

          {selected ? (
            <article
              className="pricing-detail-card flex flex-col gap-10 rounded-[24px] p-7 text-white sm:p-8"
              aria-live="polite"
            >
              <div className="flex flex-col gap-6">
                <div className="flex items-center gap-3">
                  <span className="flex h-10 w-10 items-center justify-center rounded-full bg-white/10">
                    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
                      <path
                        d="M4 13V5M9 13V3M14 13V7"
                        stroke="rgba(255,255,255,0.9)"
                        strokeWidth="1.6"
                        strokeLinecap="round"
                      />
                    </svg>
                  </span>
                  <h3 className="font-display m-0 text-[1.7rem] font-medium tracking-[-0.04em]">
                    {selected.name}
                  </h3>
                </div>

                <div>
                  <p className="m-0 flex items-baseline gap-2">
                    <span className="font-display text-[2.5rem] font-semibold tracking-[-0.05em]">
                      {selected.price}
                    </span>
                    {selected.price !== "Custom" ? (
                      <span className="text-lg text-white/80">/ mo</span>
                    ) : null}
                  </p>
                  <p className="mt-3 m-0 max-w-sm text-base leading-relaxed text-white/80">
                    {selected.tagline}
                  </p>
                </div>

                <Link
                  href={selected.href}
                  className="inline-flex w-fit items-center gap-3 rounded-[12px] bg-[#eef4f1] py-2 pl-4 pr-2 text-sm font-medium tracking-[-0.02em] text-hero shadow-[0_5px_15px_rgba(0,0,0,0.18)] transition-[transform,background-color] duration-200 hover:-translate-y-px hover:bg-white"
                >
                  {selected.cta}
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-hero text-white">
                    <ArrowIcon />
                  </span>
                </Link>
              </div>

              <ul className="m-0 grid list-none gap-2.5 p-0">
                {selected.features.slice(0, 6).map((feature) => (
                  <li
                    key={feature}
                    className="flex items-start gap-2.5 text-[15px] leading-snug text-white/80"
                  >
                    <span className="mt-0.5 shrink-0">
                      <CheckIcon />
                    </span>
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>
            </article>
          ) : null}
        </div>
      </div>
    </section>
  );
}

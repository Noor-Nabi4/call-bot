"use client";

import { AnimatedBackground } from "@/components/landing/animated-background";
import { Button } from "@/components/landing/button";
import { track } from "@/lib/analytics";
import { hero } from "@/lib/copy";

function ProductPreview() {
  return (
    <div className="relative mx-auto w-full max-w-lg lg:max-w-none">
      <div
        className="relative overflow-hidden rounded-[var(--radius-xl)] border border-white/10 bg-[#0F172A]/90 shadow-[var(--shadow-lg)] backdrop-blur-sm"
        aria-hidden="true"
      >
        <div className="flex items-center gap-2 border-b border-white/10 px-4 py-3">
          <span className="h-2.5 w-2.5 rounded-full bg-white/20" />
          <span className="h-2.5 w-2.5 rounded-full bg-white/20" />
          <span className="h-2.5 w-2.5 rounded-full bg-white/20" />
          <span className="ml-2 text-xs font-medium tracking-[-0.01em] text-hero-muted">
            Live call · AI receptionist
          </span>
        </div>
        <div className="grid gap-4 p-5 sm:p-6">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="m-0 text-xs tracking-[0.1em] text-teal-bright uppercase">
                Active call
              </p>
              <p className="mt-1 m-0 text-lg font-semibold tracking-[-0.02em] text-white">
                Inbound · Main line
              </p>
            </div>
            <div className="rounded-full bg-teal/20 px-3 py-1 text-xs font-semibold text-teal-bright">
              00:42
            </div>
          </div>
          <div className="rounded-[var(--radius-md)] border border-white/10 bg-white/5 p-4">
            <p className="m-0 text-xs text-hero-muted">Caller intent</p>
            <p className="mt-1 m-0 text-sm font-medium text-white">
              Book appointment · Service request
            </p>
            <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10">
              <div className="h-full w-[68%] rounded-full bg-gradient-to-r from-teal to-blue" />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {["Knowledge", "Booking", "Handoff"].map((label) => (
              <div
                key={label}
                className="rounded-[var(--radius-sm)] border border-white/10 bg-white/[0.04] px-2 py-3 text-center"
              >
                <p className="m-0 text-[11px] font-medium text-hero-muted">
                  {label}
                </p>
                <p className="mt-1 m-0 text-sm font-semibold text-white">Ready</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="animate-float absolute -left-3 top-16 hidden w-44 rounded-[var(--radius-lg)] border border-white/10 bg-[#10262c]/95 p-3 shadow-[var(--shadow-md)] backdrop-blur sm:block lg:-left-8">
        <p className="m-0 text-[11px] tracking-[0.08em] text-hero-muted uppercase">
          Template
        </p>
        <p className="mt-1 m-0 text-sm font-semibold text-white">
          Service business · ready
        </p>
      </div>

      <div className="animate-float-slow absolute -right-2 bottom-20 hidden w-48 rounded-[var(--radius-lg)] border border-white/10 bg-[#10262c]/95 p-3 shadow-[var(--shadow-md)] backdrop-blur sm:block lg:-right-6">
        <p className="m-0 text-[11px] tracking-[0.08em] text-hero-muted uppercase">
          Handoff
        </p>
        <p className="mt-1 m-0 text-sm font-semibold text-white">
          Context ready for humans
        </p>
      </div>
    </div>
  );
}

export function Hero() {
  return (
    <section
      className="relative isolate overflow-hidden bg-hero text-white"
      aria-labelledby="hero-heading"
    >
      <AnimatedBackground />

      <div className="relative z-[1] content-width px-6 pb-16 pt-28 sm:px-10 sm:pb-20 sm:pt-32 lg:px-12 lg:pb-24">
        <div className="grid items-center gap-12 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)] lg:gap-12">
          <div className="max-w-xl">
            <p className="animate-fade m-0 inline-flex rounded-full border border-white/15 bg-white/5 px-3 py-1 text-[11px] font-semibold tracking-[0.12em] text-teal-bright uppercase">
              {hero.eyebrow}
            </p>
            <h1
              id="hero-heading"
              className="animate-rise font-display mt-5 m-0 text-[clamp(2.4rem,6.2vw,4.1rem)] font-semibold leading-[1.02] tracking-[-0.045em]"
            >
              {hero.headline}
            </h1>
            <p className="animate-rise-delay mt-5 m-0 max-w-md text-base leading-relaxed text-hero-muted sm:text-lg">
              {hero.supporting}
            </p>
            <div className="animate-rise-delay-2 mt-8 flex flex-wrap items-center gap-3">
              <Button
                href="/signup"
                variant="inverse"
                size="lg"
                onClick={() => track("cta_start_trial", { source: "hero" })}
              >
                {hero.primaryCta}
              </Button>
              <Button
                href="#demo"
                variant="outline-light"
                size="lg"
                onClick={() => track("cta_try_voice_demo", { source: "hero" })}
              >
                {hero.secondaryCta}
              </Button>
            </div>
            <ul className="animate-rise-delay-3 mt-8 m-0 flex list-none flex-wrap gap-x-5 gap-y-2 p-0">
              {hero.trustItems.map((item) => (
                <li
                  key={item}
                  className="flex items-center gap-2 text-sm text-hero-muted"
                >
                  <span
                    className="h-1.5 w-1.5 rounded-full bg-teal-bright"
                    aria-hidden="true"
                  />
                  {item}
                </li>
              ))}
            </ul>
          </div>
          <div className="animate-rise-delay-2">
            <ProductPreview />
          </div>
        </div>
      </div>
    </section>
  );
}

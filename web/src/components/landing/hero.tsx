"use client";

import { AnimatedBackground } from "@/components/landing/animated-background";
import { Button } from "@/components/landing/button";
import { HeroVisual } from "@/components/landing/visuals";
import { track } from "@/lib/analytics";
import { hero } from "@/lib/copy";

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
            <HeroVisual />
          </div>
        </div>
      </div>
    </section>
  );
}

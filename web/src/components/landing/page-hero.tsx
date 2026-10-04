import type { ReactNode } from "react";
import { AnimatedBackground } from "@/components/landing/animated-background";
import { Breadcrumbs, type Crumb } from "@/components/landing/breadcrumbs";
import { Button } from "@/components/landing/button";

type PageHeroProps = {
  eyebrow: string;
  title: string;
  supporting: string;
  breadcrumbs?: readonly Crumb[];
  primaryCta?: { href: string; label: string };
  secondaryCta?: { href: string; label: string };
  children?: ReactNode;
  /** Optional product visual shown beside copy on large screens. */
  visual?: ReactNode;
  titleId?: string;
};

export function PageHero({
  eyebrow,
  title,
  supporting,
  breadcrumbs,
  primaryCta = { href: "/signup", label: "Start Free Trial" },
  secondaryCta = { href: "/#demo", label: "Try Voice Demo" },
  children,
  visual,
  titleId = "page-hero-heading",
}: PageHeroProps) {
  return (
    <section
      className="relative isolate overflow-hidden bg-hero text-white"
      aria-labelledby={titleId}
    >
      <AnimatedBackground />
      <div className="relative z-[1] content-width px-6 pb-14 pt-28 sm:px-10 sm:pb-16 sm:pt-32 lg:px-12">
        {breadcrumbs ? <Breadcrumbs items={breadcrumbs} /> : null}
        <div
          className={
            visual
              ? "grid items-center gap-10 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)] lg:gap-12"
              : undefined
          }
        >
          <div className="max-w-3xl">
            <p className="m-0 inline-flex rounded-full border border-white/15 bg-white/5 px-3 py-1 text-[11px] font-semibold tracking-[0.12em] text-teal-bright uppercase">
              {eyebrow}
            </p>
            <h1
              id={titleId}
              className="font-display mt-5 m-0 text-[clamp(2.1rem,5vw,3.5rem)] font-semibold leading-[1.05] tracking-[-0.045em]"
            >
              {title}
            </h1>
            <p className="mt-5 m-0 max-w-2xl text-base leading-relaxed text-hero-muted sm:text-lg">
              {supporting}
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Button href={primaryCta.href} variant="inverse" size="lg">
                {primaryCta.label}
              </Button>
              <Button href={secondaryCta.href} variant="outline-light" size="lg">
                {secondaryCta.label}
              </Button>
            </div>
            {children}
          </div>
          {visual ? (
            <div className="min-w-0 lg:justify-self-end lg:w-full">
              {visual}
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}

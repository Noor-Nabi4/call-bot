import { Button } from "@/components/landing/button";
import { Reveal } from "@/components/landing/reveal";

type CtaBandProps = {
  title?: string;
  body?: string;
  primaryHref?: string;
  primaryLabel?: string;
  secondaryHref?: string;
  secondaryLabel?: string;
};

export function CtaBand({
  title = "Ready to answer every call?",
  body = "Start a free trial, configure your first voice agent, and put Call & Flow on a number your customers already dial.",
  primaryHref = "/signup",
  primaryLabel = "Start Free Trial",
  secondaryHref = "/pricing",
  secondaryLabel = "See pricing",
}: CtaBandProps) {
  return (
    <section
      className="relative overflow-hidden bg-hero px-6 py-20 text-white sm:px-10 lg:px-12"
      aria-labelledby="marketing-cta-heading"
    >
      <div
        className="pointer-events-none absolute inset-0"
        aria-hidden="true"
        style={{
          background:
            "radial-gradient(70% 60% at 50% 0%, rgba(20,184,160,0.28), transparent 60%)",
        }}
      />
      <Reveal
        variant="scale"
        className="relative z-[1] mx-auto flex max-w-3xl flex-col items-start gap-6 sm:items-center sm:text-center"
      >
        <h2
          id="marketing-cta-heading"
          className="font-display m-0 text-[clamp(2rem,4.5vw,3.1rem)] font-semibold leading-[1.05] tracking-[-0.04em]"
        >
          {title}
        </h2>
        <p className="m-0 max-w-xl text-base leading-relaxed text-hero-muted sm:text-lg">
          {body}
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-3 sm:justify-center">
          <Button href={primaryHref} variant="inverse" size="lg">
            {primaryLabel}
          </Button>
          <Button href={secondaryHref} variant="outline-light" size="lg">
            {secondaryLabel}
          </Button>
        </div>
      </Reveal>
    </section>
  );
}

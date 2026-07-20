import {
  answer,
  book,
  capabilities,
  close,
  footer,
  handoff,
  hero,
  howItWorks,
  industries,
  platform,
  site,
} from "@/lib/copy";
import { buildFaqJsonLd } from "@/lib/metadata";
import { faqItems } from "@/lib/seo";

const PLAYGROUND =
  process.env.NEXT_PUBLIC_PLAYGROUND_URL?.replace(/\/$/, "") ||
  "http://localhost:3000";
const OPS =
  process.env.NEXT_PUBLIC_OPS_URL?.replace(/\/$/, "") ||
  "http://localhost:3001";

function resolveFooterHref(
  kind: "playground" | "ops" | "login" | "pricing",
): string {
  if (kind === "playground") return PLAYGROUND;
  if (kind === "ops") return OPS;
  if (kind === "pricing") return "/pricing";
  return `${OPS}/login`;
}

function HeroVisual() {
  return (
    <div className="hero-stage" aria-hidden="true">
      <div className="hero-glow" />
      <div className="hero-grid" />
      <div
        className="ring"
        style={{ width: "min(48vw, 380px)", height: "min(48vw, 380px)" }}
      />
      <div
        className="ring ring-2"
        style={{ width: "min(48vw, 380px)", height: "min(48vw, 380px)" }}
      />
      <div
        className="ring ring-3"
        style={{ width: "min(48vw, 380px)", height: "min(48vw, 380px)" }}
      />
      <svg
        className="wave-layer"
        viewBox="0 0 1440 320"
        preserveAspectRatio="none"
        fill="none"
        role="presentation"
      >
        <path
          d="M0 220 C 180 160, 280 280, 460 210 C 640 140, 760 260, 940 200 C 1120 140, 1280 240, 1440 180 L 1440 320 L 0 320 Z"
          fill="rgba(113, 240, 202, 0.12)"
        />
        <path
          d="M0 250 C 200 190, 320 300, 520 240 C 720 180, 860 290, 1060 230 C 1260 170, 1360 250, 1440 210 L 1440 320 L 0 320 Z"
          fill="rgba(15, 122, 100, 0.28)"
        />
        <path
          d="M0 40 C 120 90, 200 20, 340 70 C 480 120, 560 30, 700 80 C 840 130, 980 40, 1120 90 C 1260 140, 1360 60, 1440 100"
          stroke="rgba(185, 225, 210, 0.35)"
          strokeWidth="2"
        />
        <path
          d="M0 90 C 140 40, 240 120, 380 70 C 520 20, 640 110, 780 60 C 920 10, 1040 100, 1180 55 C 1320 10, 1380 70, 1440 40"
          stroke="rgba(113, 240, 202, 0.55)"
          strokeWidth="2.5"
        />
      </svg>
    </div>
  );
}

export default function LandingPage() {
  const faqJsonLd = buildFaqJsonLd(faqItems);

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }}
      />

      <main id="main-content">
        <section
          className="relative isolate min-h-[100svh] overflow-hidden"
          aria-labelledby="hero-heading"
        >
          <HeroVisual />

          <div className="relative z-[1] mx-auto flex min-h-[100svh] w-full max-w-6xl flex-col px-6 pb-16 pt-8 sm:px-10 lg:px-12">
            <header className="animate-fade flex items-center justify-between gap-4">
              <p className="font-display text-2xl font-semibold tracking-[-0.03em] text-[#f3f8f5] sm:text-3xl">
                <a href="/" className="text-inherit no-underline">
                  {hero.brand}
                </a>
              </p>
              <nav aria-label="Primary">
                <ul className="m-0 flex list-none items-center gap-4 p-0 sm:gap-5">
                  <li className="hidden sm:block">
                    <a
                      href="#how-it-works"
                      className="text-sm font-medium text-[#afc2ba] transition-colors hover:text-[#f3f8f5]"
                    >
                      How it works
                    </a>
                  </li>
                  <li className="hidden md:block">
                    <a
                      href="#platform"
                      className="text-sm font-medium text-[#afc2ba] transition-colors hover:text-[#f3f8f5]"
                    >
                      Platform
                    </a>
                  </li>
                  <li>
                    <a
                      href="/pricing"
                      className="text-sm font-medium text-[#afc2ba] transition-colors hover:text-[#f3f8f5]"
                    >
                      Pricing
                    </a>
                  </li>
                  <li>
                    <a
                      href="/signup"
                      className="text-sm font-medium text-[#afc2ba] transition-colors hover:text-[#f3f8f5]"
                    >
                      Sign up
                    </a>
                  </li>
                  <li>
                    <a
                      href={`${OPS}/login`}
                      className="text-sm font-medium text-[#afc2ba] transition-colors hover:text-[#f3f8f5]"
                    >
                      Sign in
                    </a>
                  </li>
                </ul>
              </nav>
            </header>

            <div className="flex flex-1 flex-col justify-end gap-8 pb-4 pt-24 sm:max-w-xl sm:justify-center sm:pb-10 lg:max-w-2xl">
              <h1
                id="hero-heading"
                className="animate-rise font-display m-0 text-[clamp(2.6rem,8vw,4.75rem)] font-semibold leading-[0.98] tracking-[-0.035em] text-[#f3f8f5]"
              >
                {hero.headline}
              </h1>
              <p className="animate-rise-delay m-0 max-w-md text-base leading-relaxed text-[#afc2ba] sm:text-lg">
                {hero.supporting}
              </p>
              <div className="animate-rise-delay-2 flex flex-wrap items-center gap-3">
                <a
                  href="/signup"
                  className="inline-flex items-center justify-center rounded-md bg-[#45d6ac] px-5 py-3 text-sm font-semibold text-[#07120f] transition-[transform,background-color] duration-200 hover:translate-y-[-1px] hover:bg-[#71f0ca]"
                >
                  Get started
                </a>
                <a
                  href={PLAYGROUND}
                  className="inline-flex items-center justify-center rounded-md border border-[rgba(185,225,210,0.28)] bg-transparent px-5 py-3 text-sm font-semibold text-[#f3f8f5] transition-colors duration-200 hover:border-[#45d6ac]/70 hover:bg-[rgba(69,214,172,0.08)]"
                >
                  {hero.primaryCta}
                </a>
              </div>
            </div>
          </div>
        </section>

        <section
          className="section-band px-6 py-24 sm:px-10 lg:px-12"
          aria-labelledby="answer-heading"
        >
          <div className="mx-auto grid max-w-6xl gap-10 lg:grid-cols-[1.1fr_0.9fr] lg:items-end">
            <h2
              id="answer-heading"
              className="font-display m-0 text-[clamp(2rem,4vw,3rem)] font-semibold leading-[1.05] tracking-[-0.03em] text-ink"
            >
              {answer.title}
            </h2>
            <p className="m-0 max-w-md text-base leading-relaxed text-muted sm:text-lg">
              {answer.body}
            </p>
          </div>
        </section>

        <section
          className="border-t border-line bg-paper px-6 py-24 sm:px-10 lg:px-12"
          aria-labelledby="book-heading"
        >
          <div className="mx-auto grid max-w-6xl gap-10 lg:grid-cols-[0.9fr_1.1fr] lg:items-end">
            <p className="m-0 order-2 max-w-md text-base leading-relaxed text-muted sm:text-lg lg:order-1">
              {book.body}
            </p>
            <h2
              id="book-heading"
              className="font-display order-1 m-0 text-[clamp(2rem,4vw,3rem)] font-semibold leading-[1.05] tracking-[-0.03em] text-ink lg:order-2 lg:text-right"
            >
              {book.title}
            </h2>
          </div>
        </section>

        <section
          id="how-it-works"
          className="border-t border-line bg-fog px-6 py-24 sm:px-10 lg:px-12"
          aria-labelledby="how-heading"
        >
          <div className="mx-auto max-w-6xl">
            <h2
              id="how-heading"
              className="font-display m-0 text-[clamp(2rem,4vw,3rem)] font-semibold leading-[1.05] tracking-[-0.03em] text-ink"
            >
              {howItWorks.title}
            </h2>
            <p className="mt-4 max-w-2xl text-base leading-relaxed text-muted sm:text-lg">
              {howItWorks.supporting}
            </p>
            <ol className="mt-12 m-0 grid list-none gap-10 p-0 sm:grid-cols-2">
              {howItWorks.steps.map((step, index) => (
                <li key={step.title} className="min-w-0">
                  <p className="m-0 font-mono text-xs tracking-[0.14em] text-teal uppercase">
                    Step {index + 1}
                  </p>
                  <h3 className="mt-2 m-0 text-xl font-semibold tracking-[-0.02em] text-ink">
                    {step.title}
                  </h3>
                  <p className="mt-2 m-0 text-base leading-relaxed text-muted">
                    {step.body}
                  </p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section
          className="border-t border-line bg-paper px-6 py-24 sm:px-10 lg:px-12"
          aria-labelledby="capabilities-heading"
        >
          <div className="mx-auto max-w-6xl">
            <h2
              id="capabilities-heading"
              className="font-display m-0 text-[clamp(2rem,4vw,3rem)] font-semibold leading-[1.05] tracking-[-0.03em] text-ink"
            >
              {capabilities.title}
            </h2>
            <p className="mt-4 max-w-2xl text-base leading-relaxed text-muted sm:text-lg">
              {capabilities.supporting}
            </p>
            <ul className="mt-12 m-0 grid list-none gap-x-10 gap-y-10 p-0 sm:grid-cols-2 lg:grid-cols-3">
              {capabilities.items.map((item) => (
                <li key={item.title}>
                  <h3 className="m-0 text-lg font-semibold tracking-[-0.02em] text-ink">
                    {item.title}
                  </h3>
                  <p className="mt-2 m-0 text-base leading-relaxed text-muted">
                    {item.body}
                  </p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section
          id="platform"
          className="border-t border-line bg-fog px-6 py-24 sm:px-10 lg:px-12"
          aria-labelledby="platform-heading"
        >
          <div className="mx-auto max-w-6xl">
            <h2
              id="platform-heading"
              className="font-display m-0 text-[clamp(2rem,4vw,3rem)] font-semibold leading-[1.05] tracking-[-0.03em] text-ink"
            >
              {platform.title}
            </h2>
            <p className="mt-4 max-w-2xl text-base leading-relaxed text-muted sm:text-lg">
              {platform.supporting}
            </p>
            <ul className="mt-12 m-0 grid list-none gap-10 p-0 lg:grid-cols-3">
              {platform.items.map((item) => (
                <li key={item.title} className="border-t border-line pt-6">
                  <h3 className="m-0 text-xl font-semibold tracking-[-0.02em] text-ink">
                    {item.title}
                  </h3>
                  <p className="mt-2 m-0 text-base leading-relaxed text-muted">
                    {item.body}
                  </p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section
          className="border-t border-line bg-paper px-6 py-24 sm:px-10 lg:px-12"
          aria-labelledby="industries-heading"
        >
          <div className="mx-auto max-w-6xl">
            <h2
              id="industries-heading"
              className="font-display m-0 text-[clamp(2rem,4vw,3rem)] font-semibold leading-[1.05] tracking-[-0.03em] text-ink"
            >
              {industries.title}
            </h2>
            <p className="mt-4 max-w-2xl text-base leading-relaxed text-muted sm:text-lg">
              {industries.supporting}
            </p>
            <ul className="mt-12 m-0 grid list-none gap-8 p-0 sm:grid-cols-2">
              {industries.items.map((item) => (
                <li key={item.name} className="border-t border-line pt-6">
                  <h3 className="m-0 text-xl font-semibold tracking-[-0.02em] text-ink">
                    {item.name}
                  </h3>
                  <p className="mt-2 m-0 text-base leading-relaxed text-muted">
                    {item.body}
                  </p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section
          className="border-t border-line bg-fog px-6 py-24 sm:px-10 lg:px-12"
          aria-labelledby="handoff-heading"
        >
          <div className="mx-auto grid max-w-6xl gap-10 lg:grid-cols-[1.1fr_0.9fr] lg:items-end">
            <h2
              id="handoff-heading"
              className="font-display m-0 text-[clamp(2rem,4vw,3rem)] font-semibold leading-[1.05] tracking-[-0.03em] text-ink"
            >
              {handoff.title}
            </h2>
            <p className="m-0 max-w-md text-base leading-relaxed text-muted sm:text-lg">
              {handoff.body}
            </p>
          </div>
        </section>

        <section
          id="faq"
          className="border-t border-line bg-paper px-6 py-24 sm:px-10 lg:px-12"
          aria-labelledby="faq-heading"
        >
          <div className="mx-auto max-w-3xl">
            <h2
              id="faq-heading"
              className="font-display m-0 text-[clamp(2rem,4vw,2.75rem)] font-semibold leading-[1.05] tracking-[-0.03em] text-ink"
            >
              Frequently asked questions
            </h2>
            <p className="mt-4 max-w-2xl text-base leading-relaxed text-muted">
              Marketplace agents, multi-tenant ops, booking, handoff, and public
              APIs.
            </p>
            <div className="mt-10 space-y-6">
              {faqItems.map((item) => (
                <article
                  key={item.question}
                  className="border-t border-line pt-6 first:border-t-0 first:pt-0"
                >
                  <h3 className="m-0 text-lg font-semibold tracking-[-0.02em] text-ink">
                    {item.question}
                  </h3>
                  <p className="mt-2 m-0 text-base leading-relaxed text-muted">
                    {item.answer}
                  </p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section
          className="relative overflow-hidden bg-ink px-6 py-28 text-[#f3f8f5] sm:px-10 lg:px-12"
          aria-labelledby="close-heading"
        >
          <div
            className="pointer-events-none absolute inset-0 opacity-70"
            aria-hidden="true"
            style={{
              background:
                "radial-gradient(70% 60% at 50% 0%, rgba(26,168,132,0.28), transparent 60%)",
            }}
          />
          <div className="relative z-[1] mx-auto flex max-w-3xl flex-col items-start gap-6 sm:items-center sm:text-center">
            <h2
              id="close-heading"
              className="font-display m-0 text-[clamp(2rem,4.5vw,3.25rem)] font-semibold leading-[1.05] tracking-[-0.03em]"
            >
              {close.title}
            </h2>
            <p className="m-0 max-w-xl text-base leading-relaxed text-[#afc2ba] sm:text-lg">
              {close.body}
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-3 sm:justify-center">
              <a
                href="/pricing"
                className="inline-flex items-center justify-center rounded-md bg-[#45d6ac] px-5 py-3 text-sm font-semibold text-[#07120f] transition-[transform,background-color] duration-200 hover:translate-y-[-1px] hover:bg-[#71f0ca]"
              >
                {close.primaryCta}
              </a>
              <a
                href={`${OPS}/login`}
                className="inline-flex items-center justify-center rounded-md border border-[rgba(185,225,210,0.28)] px-5 py-3 text-sm font-semibold text-[#f3f8f5] transition-colors hover:border-[#45d6ac]/70"
              >
                {close.secondaryCta}
              </a>
            </div>
          </div>
        </section>

        <footer className="border-t border-line bg-paper px-6 py-10 sm:px-10">
          <div className="mx-auto flex max-w-6xl flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-display m-0 text-lg font-semibold tracking-[-0.02em] text-ink">
                {site.brand}
              </p>
              <p className="mt-1 m-0 text-sm text-muted">{footer.note}</p>
            </div>
            <nav aria-label="Footer">
              <ul className="m-0 flex list-none flex-wrap gap-x-5 gap-y-2 p-0">
                {footer.links.map((link) => (
                  <li key={link.label}>
                    <a
                      href={resolveFooterHref(link.hrefEnv)}
                      className="text-sm font-medium text-ink-soft transition-colors hover:text-teal"
                    >
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            </nav>
          </div>
        </footer>
      </main>
    </>
  );
}

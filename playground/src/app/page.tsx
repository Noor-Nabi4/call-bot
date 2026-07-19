import Link from "next/link";
import { Playground } from "@/components/playground";
import { PageShell } from "@/components/shell";
import { home } from "@/lib/copy";

export default function HomePage() {
  return (
    <PageShell active="voice">
      <header className="mx-auto max-w-2xl animate-[rise_420ms_ease-out] text-center">
        <h1 className="m-0 font-display text-[clamp(2.2rem,6.5vw,3.5rem)] font-semibold leading-[0.98] tracking-[-0.03em] text-text-primary">
          {home.heading}
        </h1>
        <p className="mx-auto mt-4 max-w-lg text-base leading-relaxed text-text-secondary sm:text-lg">
          {home.supporting}
        </p>
        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
          <a
            href="#voice-assistant"
            className="inline-flex items-center justify-center rounded-full bg-brand px-5 py-2.5 text-sm font-semibold text-background transition-opacity hover:opacity-90"
          >
            {home.primaryAction}
          </a>
          <Link
            href="/telephony"
            className="inline-flex items-center justify-center rounded-full border border-border bg-surface-strong px-5 py-2.5 text-sm font-semibold text-text-primary transition-colors hover:border-brand/40"
          >
            {home.secondaryAction}
          </Link>
        </div>
        <p className="mx-auto mt-4 max-w-md text-sm text-text-muted">
          {home.trust}
        </p>
      </header>

      <div id="voice-assistant" className="flex flex-1 justify-center scroll-mt-8">
        <Playground />
      </div>

      <footer className="text-center text-sm text-text-muted">
        <p className="m-0">{home.privacy}</p>
      </footer>
    </PageShell>
  );
}

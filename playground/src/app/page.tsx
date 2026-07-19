import { Playground } from "@/components/playground";

export default function HomePage() {
  return (
    <main className="relative isolate grid min-h-screen grid-rows-[auto_1fr_auto] gap-6 overflow-hidden p-[clamp(1.5rem,4vw,3.5rem)] sm:gap-8">
      <div
        className="atmosphere absolute inset-0 -z-10 bg-[radial-gradient(circle_at_12%_18%,rgba(15,118,110,0.16),transparent_42%),radial-gradient(circle_at_88%_8%,rgba(16,35,58,0.1),transparent_36%),linear-gradient(160deg,#f7fafb_0%,#edf3f6_48%,#e7eef2_100%)]"
        aria-hidden
      />
      <header className="max-w-xl animate-rise">
        <p className="mb-3 font-display text-[clamp(2.4rem,6vw,4.2rem)] font-[650] leading-[0.95] tracking-[-0.04em]">
          Call Bot
        </p>
        <h1 className="m-0 text-[clamp(1.1rem,2vw,1.35rem)] font-semibold tracking-[0.08em] text-live-deep uppercase">
          Voice playground
        </h1>
        <p className="mt-4 max-w-lg text-lg leading-relaxed text-ink-soft">
          Talk to your LiveKit OpenAI Realtime agent from the browser. Keep the
          Python worker running, then start a call here.
        </p>
      </header>
      <Playground />
      <footer className="text-[0.95rem] text-ink-soft">
        <p className="m-0">
          Worker: <code>cd voice-agent && uv run src/agent.py dev</code>
          {" · "}
          <a href="/telephony" className="underline-offset-2 hover:underline">
            Telephony wizard
          </a>
        </p>
      </footer>
    </main>
  );
}

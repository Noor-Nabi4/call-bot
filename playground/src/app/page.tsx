import { Playground } from "@/components/playground";
import { PageShell } from "@/components/shell";

export default function HomePage() {
  return (
    <PageShell active="voice">
      <header className="mx-auto max-w-xl animate-[rise_420ms_ease-out] text-center">
        <h1 className="m-0 font-display text-[clamp(2.4rem,7vw,3.75rem)] font-semibold leading-[0.95] tracking-[-0.03em] text-text-primary">
          Talk to your agent
        </h1>
        <p className="mx-auto mt-4 max-w-md text-base leading-relaxed text-text-secondary sm:text-lg">
          A realtime voice session powered by LiveKit and OpenAI. Keep the
          Python worker running, then start a call below.
        </p>
      </header>

      <div className="flex flex-1 justify-center">
        <Playground />
      </div>

      <footer className="text-center text-sm text-text-muted">
        <p className="m-0">
          Worker:{" "}
          <code className="text-text-secondary">
            cd voice-agent && uv run src/agent.py dev
          </code>
        </p>
      </footer>
    </PageShell>
  );
}

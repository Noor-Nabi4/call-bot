import { Playground } from "@/components/playground";

export default function HomePage() {
  return (
    <main className="shell">
      <div className="atmosphere" aria-hidden />
      <header className="hero">
        <p className="brand">Call Bot</p>
        <h1>Voice playground</h1>
        <p className="lede">
          Talk to your LiveKit OpenAI Realtime agent from the browser. Keep the
          Python worker running, then start a call here.
        </p>
      </header>
      <Playground />
      <footer className="foot">
        <p>
          Worker: <code>cd voice-agent && uv run src/agent.py dev</code>
        </p>
      </footer>
    </main>
  );
}

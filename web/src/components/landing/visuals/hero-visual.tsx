import { VisualFrame } from "@/components/landing/visuals/visual-frame";
import { Waveform } from "@/components/landing/visuals/waveform";
import { heroCallFlow } from "@/lib/marketing/visuals";

const flowSummary = [
  "Incoming call",
  "AI voice agent",
  "Knowledge / CRM",
  "Book · Qualify · Support",
  "Human handoff",
] as const;

export function HeroVisual() {
  return (
    <div className="relative mx-auto w-full max-w-lg lg:max-w-none">
      <VisualFrame
        label="Product preview of an AI voice agent answering an inbound call, using knowledge and booking, then preparing human handoff"
        className="p-0"
      >
        <div className="flex items-center gap-2 border-b border-white/10 px-4 py-3">
          <span className="h-2.5 w-2.5 rounded-full bg-white/20" aria-hidden="true" />
          <span className="h-2.5 w-2.5 rounded-full bg-white/20" aria-hidden="true" />
          <span className="h-2.5 w-2.5 rounded-full bg-white/20" aria-hidden="true" />
          <span className="ml-2 text-xs font-medium tracking-[-0.01em] text-hero-muted">
            {heroCallFlow.title}
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
              {heroCallFlow.status}
            </div>
          </div>

          <div className="rounded-[var(--radius-md)] border border-white/10 bg-white/5 p-4">
            <p className="m-0 text-xs text-hero-muted">Caller intent</p>
            <p className="mt-1 m-0 text-sm font-medium text-white">
              {heroCallFlow.intent}
            </p>
            <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10">
              <div className="h-full w-[68%] rounded-full bg-gradient-to-r from-teal to-blue" />
            </div>
            <Waveform className="mt-3" bars={24} />
          </div>

          <ol className="m-0 grid list-none gap-2 p-0">
            {flowSummary.map((step, index) => (
              <li
                key={step}
                className="flex items-center gap-3 rounded-[12px] border border-white/10 bg-white/[0.04] px-3 py-2.5"
              >
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-teal/20 text-[11px] font-semibold text-teal-bright">
                  {index + 1}
                </span>
                <span className="text-sm font-medium text-white/90">{step}</span>
                {index < flowSummary.length - 1 ? (
                  <span className="ml-auto text-hero-muted" aria-hidden="true">
                    ↓
                  </span>
                ) : null}
              </li>
            ))}
          </ol>

          <div className="grid grid-cols-3 gap-2">
            {heroCallFlow.chips.map((label) => (
              <div
                key={label}
                className="rounded-[var(--radius-sm)] border border-white/10 bg-white/[0.04] px-2 py-3 text-center"
              >
                <p className="m-0 text-[11px] font-medium text-hero-muted">{label}</p>
                <p className="mt-1 m-0 text-sm font-semibold text-white">Ready</p>
              </div>
            ))}
          </div>
        </div>
      </VisualFrame>

      <div className="animate-float absolute -left-3 top-16 hidden w-44 rounded-[var(--radius-lg)] border border-white/10 bg-[#10262c]/95 p-3 shadow-[var(--shadow-md)] backdrop-blur sm:block lg:-left-8">
        <p className="m-0 text-[11px] tracking-[0.08em] text-hero-muted uppercase">
          Flow
        </p>
        <p className="mt-1 m-0 text-sm font-semibold text-white">
          Call → AI → Action
        </p>
      </div>

      <div className="animate-float-slow absolute -right-2 bottom-16 hidden w-48 rounded-[var(--radius-lg)] border border-white/10 bg-[#10262c]/95 p-3 shadow-[var(--shadow-md)] backdrop-blur sm:block lg:-right-6">
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

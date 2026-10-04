import { CallFlowDiagram } from "@/components/landing/visuals/call-flow-diagram";
import { VisualFrame } from "@/components/landing/visuals/visual-frame";
import { Waveform } from "@/components/landing/visuals/waveform";
import { industryVisuals } from "@/lib/marketing/visuals";

type IndustryVisualProps = {
  slug: string;
  industryName: string;
};

export function IndustryVisual({ slug, industryName }: IndustryVisualProps) {
  const visual = industryVisuals[slug];
  if (!visual) return null;

  return (
    <div className="relative">
      <VisualFrame
        label={visual.alt}
        chrome={`${industryName} · Live line`}
        status="AI Agent active"
      >
        <div className="p-5 sm:p-6">
          <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="m-0 text-xs font-semibold tracking-[0.12em] text-teal-bright uppercase">
                {visual.accent}
              </p>
              <p className="mt-1 m-0 text-lg font-semibold tracking-[-0.02em]">
                {visual.scenario}
              </p>
              <p className="mt-1 m-0 text-xs text-hero-muted">
                Incoming call · 00:42
              </p>
            </div>
            <div className="rounded-[12px] border border-white/10 bg-white/[0.04] px-3 py-2 text-right">
              <p className="m-0 text-[11px] tracking-[0.08em] text-hero-muted uppercase">
                {visual.metricLabel}
              </p>
              <p className="mt-0.5 m-0 text-sm font-semibold text-teal-bright">
                {visual.metric}
              </p>
            </div>
          </div>

          <div className="mb-4 hidden rounded-[14px] border border-white/10 bg-white/[0.03] px-3 py-3 sm:block">
            <div className="mb-2 flex items-center justify-between gap-2">
              <p className="m-0 text-[11px] font-semibold tracking-[0.1em] text-hero-muted uppercase">
                Call recording
              </p>
              <p className="m-0 text-[11px] font-semibold text-teal-bright">
                Live
              </p>
            </div>
            <Waveform bars={20} />
          </div>

          <CallFlowDiagram steps={visual.steps} compact />
        </div>
      </VisualFrame>
    </div>
  );
}

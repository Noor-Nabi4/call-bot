import { CallFlowDiagram } from "@/components/landing/visuals/call-flow-diagram";
import { HumanBusinessVisual } from "@/components/landing/visuals/human-business-visual";
import { VisualFrame } from "@/components/landing/visuals/visual-frame";
import { Waveform } from "@/components/landing/visuals/waveform";
import { getUseCaseBusinessVisual } from "@/lib/marketing/human-business-visuals";
import { useCaseVisuals } from "@/lib/marketing/visuals";

type UseCaseVisualProps = {
  slug: string;
  priority?: boolean;
};

export function UseCaseVisual({ slug, priority = true }: UseCaseVisualProps) {
  const visual = useCaseVisuals[slug];
  const business = getUseCaseBusinessVisual(slug);
  if (!visual || !business) return null;

  return (
    <div className="relative">
      <VisualFrame
        label={visual.alt}
        chrome={visual.title}
        status="AI Agent active"
      >
        <div className="border-b border-white/10 p-3 sm:p-4">
          <HumanBusinessVisual
            config={business}
            priority={priority}
            className="human-business-surface aspect-[16/10] sm:aspect-[16/9]"
            sizes="(max-width: 1024px) 100vw, 560px"
          />
        </div>

        <div className="p-5 sm:p-6">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <p className="m-0 text-xs font-semibold tracking-[0.12em] text-teal-bright uppercase">
                Use case
              </p>
              <p className="mt-1 m-0 text-lg font-semibold tracking-[-0.02em]">
                {visual.result}
              </p>
              <p className="mt-1 m-0 text-xs text-hero-muted">
                Incoming call · 00:42
              </p>
            </div>
            <span className="rounded-full border border-teal/30 bg-teal/15 px-3 py-1 text-xs font-semibold text-teal-bright">
              Live
            </span>
          </div>

          <div className="mb-4 hidden rounded-[14px] border border-white/10 bg-white/[0.03] px-3 py-3 sm:block">
            <Waveform bars={18} />
          </div>

          <CallFlowDiagram steps={visual.steps} compact />
        </div>
      </VisualFrame>
    </div>
  );
}

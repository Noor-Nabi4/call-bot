import { CallFlowDiagram } from "@/components/landing/visuals/call-flow-diagram";
import { VisualFrame } from "@/components/landing/visuals/visual-frame";
import { Waveform } from "@/components/landing/visuals/waveform";
import {
  receptionistFlow,
  voiceAgentFlow,
} from "@/lib/marketing/visuals";

type ProductVisualProps = {
  variant: "receptionist" | "voice-agents";
};

export function ProductVisual({ variant }: ProductVisualProps) {
  if (variant === "voice-agents") {
    return (
      <VisualFrame label={voiceAgentFlow.alt} className="p-5 sm:p-6">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <p className="m-0 text-xs font-semibold tracking-[0.12em] text-teal-bright uppercase">
              {voiceAgentFlow.title}
            </p>
            <p className="mt-1 m-0 text-lg font-semibold tracking-[-0.02em]">
              Platform call path
            </p>
          </div>
          <Waveform className="hidden w-28 sm:flex" bars={18} />
        </div>
        <CallFlowDiagram
          steps={voiceAgentFlow.steps}
          branches={voiceAgentFlow.branches}
        />
      </VisualFrame>
    );
  }

  return (
    <VisualFrame label={receptionistFlow.alt} className="p-5 sm:p-6">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <p className="m-0 text-xs font-semibold tracking-[0.12em] text-teal-bright uppercase">
            {receptionistFlow.title}
          </p>
          <p className="mt-1 m-0 text-lg font-semibold tracking-[-0.02em]">
            Front-desk automation
          </p>
        </div>
        <span className="rounded-full bg-teal/20 px-3 py-1 text-xs font-semibold text-teal-bright">
          Live
        </span>
      </div>
      <CallFlowDiagram steps={receptionistFlow.steps} />
    </VisualFrame>
  );
}

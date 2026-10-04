import Image from "next/image";
import { Marketing3DVisual } from "@/components/landing/visuals/marketing-3d-visual";
import { Waveform } from "@/components/landing/visuals/waveform";
import { cn } from "@/lib/cn";
import type {
  BusinessOverlayCard,
  HumanBusinessVisualConfig,
} from "@/lib/marketing/human-business-visuals";

type HumanBusinessVisualProps = {
  config: HumanBusinessVisualConfig;
  /** Override image from registry. */
  image?: HumanBusinessVisualConfig["image"];
  industry?: string;
  personRole?: string;
  environment?: string;
  workflow?: readonly string[];
  threeDAsset?: HumanBusinessVisualConfig["threeDAsset"];
  overlayCards?: readonly BusinessOverlayCard[];
  variant?: "hero" | "spotlight" | "compact";
  /**
   * `auto` respects bakedOverlays.
   * `html` forces CSS glass cards.
   * `none` shows photography (+ optional 3D) only.
   */
  overlayMode?: "auto" | "html" | "none";
  priority?: boolean;
  alt?: string;
  className?: string;
  sizes?: string;
  decorative?: boolean;
  showThreeD?: boolean;
};

const POSITION_CLASS: Record<BusinessOverlayCard["position"], string> = {
  "top-left": "hbv-card--top-left",
  "top-center": "hbv-card--top-center",
  "top-right": "hbv-card--top-right",
  center: "hbv-card--center",
  "bottom-left": "hbv-card--bottom-left",
  "bottom-right": "hbv-card--bottom-right",
  right: "hbv-card--right",
};

function IncomingCallCard({ card }: { card: BusinessOverlayCard }) {
  return (
    <div
      className={cn("hbv-glass hbv-call-card", POSITION_CLASS[card.position])}
      aria-hidden="true"
    >
      <div className="hbv-call-card__row">
        <span className="hbv-call-avatar" />
        <div className="min-w-0">
          <p className="hbv-kicker">{card.title}</p>
          {card.subtitle ? (
            <p className="hbv-title">{card.subtitle}</p>
          ) : null}
          {card.detail ? <p className="hbv-meta">{card.detail}</p> : null}
        </div>
        <span className="hbv-call-accept" />
      </div>
    </div>
  );
}

function AiAgentCard({ card }: { card: BusinessOverlayCard }) {
  return (
    <div
      className={cn("hbv-ai-cluster", POSITION_CLASS[card.position])}
      aria-hidden="true"
    >
      <div className="hbv-ai-orb">
        <Waveform bars={10} className="hbv-ai-orb__wave" />
      </div>
      <div className="hbv-glass hbv-ai-label">
        <p className="hbv-kicker">{card.title}</p>
        {card.subtitle ? <p className="hbv-title">{card.subtitle}</p> : null}
      </div>
    </div>
  );
}

function OutcomeCard({ card }: { card: BusinessOverlayCard }) {
  return (
    <div
      className={cn("hbv-glass hbv-outcome-card", POSITION_CLASS[card.position])}
      aria-hidden="true"
    >
      <div className="hbv-outcome-card__head">
        <span className="hbv-outcome-icon" />
        <div className="min-w-0">
          <p className="hbv-kicker">Outcome</p>
          <p className="hbv-title">{card.title}</p>
        </div>
      </div>
      {card.subtitle ? <p className="hbv-meta mt-2">{card.subtitle}</p> : null}
      {card.detail ? (
        <p className="mt-1 m-0 text-[12px] font-semibold text-[#0B1220]">
          {card.detail}
        </p>
      ) : null}
      {card.meta ? (
        <p className="hbv-outcome-status mt-2">
          <span className="hbv-check" />
          {card.meta}
        </p>
      ) : null}
    </div>
  );
}

function OverlayLayer({ cards }: { cards: readonly BusinessOverlayCard[] }) {
  return (
    <div className="hbv-overlays" aria-hidden="true">
      {cards.map((card) => {
        if (card.kind === "incoming-call" || card.kind === "status") {
          return <IncomingCallCard key={card.id} card={card} />;
        }
        if (card.kind === "ai-agent") {
          return <AiAgentCard key={card.id} card={card} />;
        }
        return <OutcomeCard key={card.id} card={card} />;
      })}
    </div>
  );
}

/**
 * Premium human-centric campaign visual:
 * REAL PERSON + BUSINESS ENVIRONMENT + AI VOICE + BUSINESS ACTION UI
 */
export function HumanBusinessVisual({
  config,
  image,
  industry,
  personRole,
  environment,
  workflow,
  threeDAsset,
  overlayCards,
  variant,
  overlayMode = "auto",
  priority = false,
  alt,
  className = "",
  sizes = "(max-width: 768px) 100vw, 640px",
  decorative = false,
  showThreeD,
}: HumanBusinessVisualProps) {
  const resolvedImage = image || config.image;
  const resolvedThreeD = threeDAsset ?? config.threeDAsset;
  const resolvedCards = overlayCards || config.overlayCards;
  const resolvedVariant = variant || config.variant;
  const resolvedRole = personRole || config.personRole;
  const resolvedEnvironment = environment || config.environment;
  const resolvedWorkflow = workflow || config.workflow;
  const showHtmlOverlays =
    overlayMode === "html" ||
    (overlayMode === "auto" && !config.bakedOverlays);
  const chipEnabled =
    showThreeD ?? (!config.bakedOverlays && resolvedVariant !== "compact");
  const showChip = chipEnabled && Boolean(resolvedThreeD);

  return (
    <div
      className={cn(
        "human-business-visual relative overflow-hidden rounded-[18px]",
        `hbv-variant-${resolvedVariant}`,
        className,
      )}
      data-industry={
        industry ||
        (config.category === "industry" ? config.slug : undefined)
      }
      data-use-case={config.category === "use-case" ? config.slug : undefined}
      data-person-role={resolvedRole}
      data-environment={resolvedEnvironment}
      data-workflow={resolvedWorkflow.join(" → ")}
    >
      <div
        className="pointer-events-none absolute inset-0 z-[1] bg-gradient-to-t from-[#0B1220]/40 via-transparent to-transparent"
        aria-hidden="true"
      />
      <div
        className="pointer-events-none absolute inset-0 z-[1] ring-1 ring-inset ring-white/10"
        aria-hidden="true"
      />

      <Image
        src={resolvedImage.src}
        alt={decorative ? "" : alt || resolvedImage.alt}
        fill
        className={cn("object-cover", config.focus)}
        priority={priority}
        loading={priority ? "eager" : "lazy"}
        sizes={sizes}
        aria-hidden={decorative || undefined}
      />

      {showHtmlOverlays ? <OverlayLayer cards={resolvedCards} /> : null}

      {showChip && resolvedThreeD ? (
        <div className="human-3d-chip hbv-3d-chip" aria-hidden="true">
          <Marketing3DVisual
            asset={resolvedThreeD}
            decorative
            className="aspect-[16/10] rounded-[14px]"
            sizes="200px"
          />
        </div>
      ) : null}
    </div>
  );
}

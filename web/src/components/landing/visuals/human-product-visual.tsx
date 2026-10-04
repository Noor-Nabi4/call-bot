import Image from "next/image";
import { Marketing3DVisual } from "@/components/landing/visuals/marketing-3d-visual";
import { cn } from "@/lib/cn";
import type {
  HumanAsset,
  StoryMediaAsset,
} from "@/lib/marketing/human-assets";

type HumanProductVisualProps = {
  human: HumanAsset;
  threeD?: StoryMediaAsset;
  /** human-lead = full scene; overlay = scene + floating 3D card */
  variant?: "scene" | "overlay" | "handoff";
  className?: string;
  priority?: boolean;
  sizes?: string;
  /** When true, treat as decorative inside a labeled VisualFrame. */
  decorative?: boolean;
};

/** Human business scene with optional supporting 3D product depth. */
export function HumanProductVisual({
  human,
  threeD,
  variant = "scene",
  className = "",
  priority = false,
  sizes = "(max-width: 768px) 100vw, 560px",
  decorative = false,
}: HumanProductVisualProps) {
  const showOverlay = Boolean(threeD) && variant !== "scene";

  return (
    <div
      className={cn(
        "human-product-visual relative overflow-hidden rounded-[18px]",
        className,
      )}
    >
      <div
        className="pointer-events-none absolute inset-0 z-[1] bg-gradient-to-t from-[#0B1220]/55 via-[#0B1220]/10 to-transparent"
        aria-hidden="true"
      />
      <div
        className="pointer-events-none absolute inset-0 z-[1] ring-1 ring-inset ring-white/10"
        aria-hidden="true"
      />

      <Image
        src={human.src}
        alt={decorative ? "" : human.alt}
        fill
        className="object-cover object-[center_20%]"
        priority={priority}
        loading={priority ? "eager" : "lazy"}
        sizes={sizes}
        aria-hidden={decorative || undefined}
      />

      {showOverlay && threeD ? (
        <div
          className={cn(
            "human-3d-chip absolute z-[2] hidden overflow-hidden rounded-[14px] border border-white/15 shadow-[0_18px_40px_-24px_rgba(0,0,0,0.65)] sm:block",
            variant === "handoff"
              ? "bottom-3 right-3 w-[42%] max-w-[11.5rem]"
              : "bottom-3 right-3 w-[46%] max-w-[12.5rem]",
          )}
          aria-hidden="true"
        >
          <Marketing3DVisual
            asset={threeD}
            decorative
            className="aspect-[16/10] rounded-[14px]"
            sizes="200px"
          />
        </div>
      ) : null}
    </div>
  );
}

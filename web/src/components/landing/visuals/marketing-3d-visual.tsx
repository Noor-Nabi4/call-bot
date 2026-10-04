import Image from "next/image";
import { cn } from "@/lib/cn";
type MarketingImageAsset = {
  src: string;
  alt: string;
  width: number;
  height: number;
};

type Marketing3DVisualProps = {
  asset: MarketingImageAsset;
  className?: string;
  priority?: boolean;
  /** Decorative ambient float — disabled under prefers-reduced-motion via CSS. */
  float?: boolean;
  sizes?: string;
  /** When true, image is decorative and hidden from assistive tech. */
  decorative?: boolean;
};

/** Premium 3D marketing still — optimized via next/image. */
export function Marketing3DVisual({
  asset,
  className = "",
  priority = false,
  float = false,
  sizes = "(max-width: 768px) 100vw, 560px",
  decorative = false,
}: Marketing3DVisualProps) {
  return (
    <div
      className={cn(
        "marketing-3d relative overflow-hidden rounded-[18px]",
        float && "marketing-3d-float",
        className,
      )}
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
        src={asset.src}
        alt={decorative ? "" : asset.alt}
        fill
        className="object-cover"
        priority={priority}
        loading={priority ? "eager" : "lazy"}
        sizes={sizes}
        aria-hidden={decorative || undefined}
      />
    </div>
  );
}

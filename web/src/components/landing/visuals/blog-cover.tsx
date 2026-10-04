import { MarketingImage } from "@/components/landing/visuals/marketing-image";
import { VisualFrame } from "@/components/landing/visuals/visual-frame";
import { Waveform } from "@/components/landing/visuals/waveform";
import { blogCovers } from "@/lib/marketing/visuals";

type BlogCoverProps = {
  slug: string;
  title: string;
  priority?: boolean;
  className?: string;
};

export function BlogCover({
  slug,
  title,
  priority = false,
  className = "",
}: BlogCoverProps) {
  const cover = blogCovers[slug];
  const alt = cover?.alt || `Featured visual for ${title}`;

  if (cover?.src) {
    return (
      <div
        className={`overflow-hidden rounded-[var(--radius-xl)] border border-line shadow-[var(--shadow-md)] ${className}`}
      >
        <MarketingImage
          src={cover.src}
          alt={alt}
          width={1600}
          height={900}
          priority={priority}
          className="aspect-[16/9] h-auto w-full object-cover"
          sizes="(max-width: 768px) 100vw, 720px"
        />
      </div>
    );
  }

  const theme = cover?.theme || "platform";

  return (
    <VisualFrame label={alt} className={`aspect-[16/9] p-6 sm:p-8 ${className}`}>
      <div className="flex h-full min-h-[12rem] flex-col justify-between">
        <div>
          <p className="m-0 text-xs font-semibold tracking-[0.12em] text-teal-bright uppercase">
            {theme === "receptionist"
              ? "AI receptionist"
              : theme === "waveform"
                ? "AI voice agents"
                : "Call & Flow"}
          </p>
          <p className="mt-3 m-0 max-w-md text-xl font-semibold tracking-[-0.03em] sm:text-2xl">
            {title}
          </p>
        </div>
        <div className="mt-8">
          {theme === "receptionist" ? (
            <div className="grid max-w-sm gap-2">
              {["Incoming call", "AI receptionist", "Book / answer / transfer"].map(
                (step, index) => (
                  <div
                    key={step}
                    className="rounded-[10px] border border-white/10 bg-white/[0.05] px-3 py-2 text-sm text-hero-muted"
                  >
                    <span className="mr-2 text-teal-bright">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    {step}
                  </div>
                ),
              )}
            </div>
          ) : (
            <Waveform className="w-full max-w-md" bars={32} />
          )}
        </div>
      </div>
    </VisualFrame>
  );
}

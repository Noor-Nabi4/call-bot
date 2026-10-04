import { VisualFrame } from "@/components/landing/visuals/visual-frame";
import { pricingVisual } from "@/lib/marketing/visuals";

export function PricingVisual() {
  return (
    <VisualFrame
      tone="light"
      label={pricingVisual.alt}
      className="p-5 sm:p-6 shadow-[var(--shadow-md)]"
    >
      <p className="m-0 text-xs font-semibold tracking-[0.12em] text-teal uppercase">
        Capacity
      </p>
      <p className="mt-2 m-0 text-lg font-semibold tracking-[-0.02em] text-ink">
        {pricingVisual.title}
      </p>
      <ul className="mt-5 m-0 flex list-none flex-col gap-4 p-0">
        {pricingVisual.meters.map((meter) => (
          <li key={meter.label}>
            <div className="mb-1.5 flex items-center justify-between gap-3 text-sm">
              <span className="text-muted">{meter.label}</span>
              <span className="font-semibold text-ink">{meter.value}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-bg">
              <div
                className="h-full rounded-full bg-gradient-to-r from-teal to-teal-bright"
                style={{ width: `${meter.value}%` }}
                aria-hidden="true"
              />
            </div>
          </li>
        ))}
      </ul>
      <p className="mt-4 m-0 text-xs leading-relaxed text-muted">
        Plans scale by included minutes, concurrency, and phone numbers — not
        vague seat counts.
      </p>
    </VisualFrame>
  );
}

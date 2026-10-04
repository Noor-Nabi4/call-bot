import { Reveal } from "@/components/landing/reveal";
import { SectionHeader } from "@/components/landing/section-header";

type ContentItem = {
  title: string;
  body: string;
};

type ContentGridProps = {
  eyebrow?: string;
  title: string;
  supporting?: string;
  items: readonly ContentItem[];
  id?: string;
  columns?: 2 | 3;
  tone?: "surface" | "bg";
};

export function ContentGrid({
  eyebrow,
  title,
  supporting,
  items,
  id,
  columns = 3,
  tone = "bg",
}: ContentGridProps) {
  const headingId = id ? `${id}-heading` : undefined;

  return (
    <section
      id={id}
      className={`section-pad border-t border-line ${
        tone === "surface" ? "bg-surface" : "bg-bg"
      }`}
      aria-labelledby={headingId}
    >
      <div className="content-width">
        <Reveal>
          <SectionHeader
            eyebrow={eyebrow}
            title={title}
            supporting={supporting}
            id={headingId}
          />
        </Reveal>
        <ul
          className={`mt-10 m-0 grid list-none gap-4 p-0 sm:grid-cols-2 ${
            columns === 3 ? "lg:grid-cols-3" : ""
          }`}
        >
          {items.map((item, index) => (
            <Reveal
              key={item.title}
              as="li"
              delay={(index % 3) as 0 | 1 | 2 | 3}
              variant="scale"
            >
              <article className="card-surface card-surface-hover h-full p-5 sm:p-6">
                <h3 className="m-0 text-lg font-semibold tracking-[-0.02em] text-ink">
                  {item.title}
                </h3>
                <p className="mt-2 m-0 text-sm leading-relaxed text-muted sm:text-base">
                  {item.body}
                </p>
              </article>
            </Reveal>
          ))}
        </ul>
      </div>
    </section>
  );
}

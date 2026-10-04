import Link from "next/link";
import { Reveal } from "@/components/landing/reveal";
import { SectionHeader } from "@/components/landing/section-header";

type RelatedLink = {
  href: string;
  label: string;
  description?: string;
};

type RelatedLinksProps = {
  title?: string;
  supporting?: string;
  links: readonly RelatedLink[];
};

export function RelatedLinks({
  title = "Related pages",
  supporting = "Keep exploring how Call & Flow fits your calls.",
  links,
}: RelatedLinksProps) {
  if (links.length === 0) return null;

  return (
    <section
      className="section-pad border-t border-line bg-surface"
      aria-labelledby="related-links-heading"
    >
      <div className="content-width">
        <Reveal>
          <SectionHeader
            eyebrow="Explore"
            title={title}
            supporting={supporting}
            id="related-links-heading"
          />
        </Reveal>
        <ul className="mt-8 m-0 grid list-none gap-3 p-0 sm:grid-cols-2 lg:grid-cols-3">
          {links.map((link) => (
            <li key={link.href}>
              <Link
                href={link.href}
                className="card-surface card-surface-hover block h-full p-5 no-underline transition-colors"
              >
                <span className="text-base font-semibold tracking-[-0.02em] text-ink">
                  {link.label}
                </span>
                {link.description ? (
                  <span className="mt-2 block text-sm leading-relaxed text-muted">
                    {link.description}
                  </span>
                ) : null}
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

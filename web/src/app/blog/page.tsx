import Link from "next/link";
import {
  CtaBand,
  JsonLd,
  MarketingShell,
  PageHero,
  RelatedLinks,
  Reveal,
} from "@/components/landing";
import { blogIndex, blogPosts } from "@/lib/marketing/blog";
import {
  buildBreadcrumbJsonLd,
  buildPageMetadata,
  buildWebPageJsonLd,
} from "@/lib/metadata";

export const metadata = buildPageMetadata({
  title: blogIndex.title,
  description: blogIndex.description,
  path: "/blog",
  keywords: [
    "AI receptionist guide",
    "AI voice agents resources",
    "business phone automation",
  ],
});

export default function BlogIndexPage() {
  return (
    <>
      <JsonLd
        data={buildWebPageJsonLd({
          path: "/blog",
          name: blogIndex.title,
          description: blogIndex.description,
        })}
      />
      <JsonLd
        data={buildBreadcrumbJsonLd([
          { name: "Home", path: "/" },
          { name: "Resources", path: "/blog" },
        ])}
      />

      <MarketingShell>
        <PageHero
          eyebrow="Resources"
          title={blogIndex.h1}
          supporting={blogIndex.supporting}
          breadcrumbs={[
            { label: "Home", href: "/" },
            { label: "Resources" },
          ]}
          secondaryCta={{ href: "/ai-voice-agents", label: "AI Voice Agents" }}
        />

        <section
          className="section-pad border-t border-line bg-surface"
          aria-labelledby="blog-list-heading"
        >
          <div className="content-width">
            <h2 id="blog-list-heading" className="sr-only">
              Articles
            </h2>
            <ul className="m-0 grid list-none gap-4 p-0">
              {blogPosts.map((post, index) => (
                <Reveal key={post.slug} as="li" delay={(index % 3) as 0 | 1 | 2 | 3}>
                  <article className="card-surface card-surface-hover p-6 sm:p-8">
                    <p className="m-0 text-xs font-semibold tracking-[0.1em] text-teal uppercase">
                      {new Date(post.publishedAt).toLocaleDateString("en-US", {
                        month: "long",
                        day: "numeric",
                        year: "numeric",
                      })}{" "}
                      · {post.readingMinutes} min read
                    </p>
                    <h3 className="mt-3 m-0 text-2xl font-semibold tracking-[-0.03em] text-ink">
                      <Link
                        href={`/blog/${post.slug}`}
                        className="text-inherit no-underline hover:text-teal"
                      >
                        {post.title}
                      </Link>
                    </h3>
                    <p className="mt-3 m-0 max-w-3xl text-base leading-relaxed text-muted">
                      {post.description}
                    </p>
                    <ul className="mt-4 m-0 flex list-none flex-wrap gap-2 p-0">
                      {post.tags.map((tag) => (
                        <li
                          key={tag}
                          className="rounded-full bg-teal-soft px-2.5 py-1 text-xs font-medium text-teal-deep"
                        >
                          {tag}
                        </li>
                      ))}
                    </ul>
                  </article>
                </Reveal>
              ))}
            </ul>
          </div>
        </section>

        <RelatedLinks
          title="Commercial pages"
          links={[
            {
              href: "/ai-receptionist",
              label: "AI Receptionist",
              description: "Product page for front-desk automation.",
            },
            {
              href: "/ai-voice-agents",
              label: "AI Voice Agents",
              description: "Platform overview for phone automation.",
            },
            {
              href: "/pricing",
              label: "Pricing",
              description: "Current plans and included minutes.",
            },
          ]}
        />

        <CtaBand />
      </MarketingShell>
    </>
  );
}

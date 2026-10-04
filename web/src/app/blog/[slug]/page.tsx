import Link from "next/link";
import { notFound } from "next/navigation";
import {
  BlogCover,
  CtaBand,
  JsonLd,
  MarketingShell,
  PageHero,
  RelatedLinks,
} from "@/components/landing";
import {
  blogPosts,
  getBlogPost,
  getBlogSlugs,
} from "@/lib/marketing/blog";
import { absoluteUrl } from "@/lib/seo";
import {
  buildBreadcrumbJsonLd,
  buildPageMetadata,
  buildWebPageJsonLd,
} from "@/lib/metadata";

type PageProps = {
  params: Promise<{ slug: string }>;
};

export function generateStaticParams() {
  return getBlogSlugs().map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: PageProps) {
  const { slug } = await params;
  const post = getBlogPost(slug);
  if (!post) return {};
  return buildPageMetadata({
    title: post.title,
    description: post.description,
    path: `/blog/${post.slug}`,
    ogType: "article",
    keywords: post.tags,
  });
}

export default async function BlogPostPage({ params }: PageProps) {
  const { slug } = await params;
  const post = getBlogPost(slug);
  if (!post) notFound();

  const path = `/blog/${post.slug}`;
  const articleJsonLd = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: post.title,
    description: post.description,
    datePublished: post.publishedAt,
    dateModified: post.updatedAt,
    author: {
      "@type": "Organization",
      name: "Call & Flow",
    },
    publisher: {
      "@type": "Organization",
      name: "Call & Flow",
      url: absoluteUrl("/"),
    },
    mainEntityOfPage: absoluteUrl(path),
  };

  const otherPosts = blogPosts.filter((item) => item.slug !== post.slug);

  return (
    <>
      <JsonLd
        data={buildWebPageJsonLd({
          path,
          name: post.title,
          description: post.description,
        })}
      />
      <JsonLd
        data={buildBreadcrumbJsonLd([
          { name: "Home", path: "/" },
          { name: "Resources", path: "/blog" },
          { name: post.title, path },
        ])}
      />
      <JsonLd data={articleJsonLd} />

      <MarketingShell>
        <PageHero
          eyebrow="Article"
          title={post.title}
          supporting={post.description}
          breadcrumbs={[
            { label: "Home", href: "/" },
            { label: "Resources", href: "/blog" },
            { label: post.title },
          ]}
          primaryCta={{ href: "/signup", label: "Start Free Trial" }}
          secondaryCta={{ href: "/ai-receptionist", label: "AI Receptionist" }}
        >
          <p className="mt-6 m-0 text-sm text-hero-muted">
            {new Date(post.publishedAt).toLocaleDateString("en-US", {
              month: "long",
              day: "numeric",
              year: "numeric",
            })}{" "}
            · {post.readingMinutes} min read
          </p>
        </PageHero>

        <article className="section-pad border-t border-line bg-surface">
          <div className="content-width max-w-3xl">
            <div className="mb-10">
              <BlogCover slug={post.slug} title={post.title} priority />
            </div>
            {post.sections.map((section) => (
              <section key={section.heading || section.paragraphs[0]} className="mb-10">
                {section.heading ? (
                  <h2 className="font-display m-0 text-2xl font-semibold tracking-[-0.03em] text-ink">
                    {section.heading}
                  </h2>
                ) : null}
                {section.paragraphs.map((paragraph) => (
                  <p
                    key={paragraph.slice(0, 48)}
                    className={`m-0 text-base leading-relaxed text-muted sm:text-lg ${
                      section.heading ? "mt-4" : "mt-0"
                    } [&+p]:mt-4`}
                  >
                    {paragraph}
                  </p>
                ))}
              </section>
            ))}

            <p className="m-0 rounded-[var(--radius-lg)] border border-line bg-bg p-5 text-sm leading-relaxed text-muted">
              Evaluating Call & Flow? Read the{" "}
              <Link href="/ai-receptionist" className="font-semibold text-teal">
                AI receptionist
              </Link>{" "}
              and{" "}
              <Link href="/ai-voice-agents" className="font-semibold text-teal">
                AI voice agents
              </Link>{" "}
              pages, then compare{" "}
              <Link href="/pricing" className="font-semibold text-teal">
                pricing
              </Link>
              .
            </p>
          </div>
        </article>

        <RelatedLinks
          title="More resources"
          links={otherPosts.map((item) => ({
            href: `/blog/${item.slug}`,
            label: item.title,
            description: item.description,
          }))}
        />

        <CtaBand />
      </MarketingShell>
    </>
  );
}

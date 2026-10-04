import assert from "node:assert/strict";
import test from "node:test";
import { blogPosts } from "./marketing/blog.ts";
import { industryPages } from "./marketing/industries.ts";
import {
  aiReceptionistPage,
  aiVoiceAgentsPage,
} from "./marketing/product-pages.ts";
import { PUBLIC_MARKETING_ROUTES, ROBOTS_DISALLOW } from "./marketing/routes.ts";
import { useCasePages, useCasesHub } from "./marketing/use-cases.ts";
import {
  industryStories,
  useCaseStories,
} from "./marketing/feature-sections.ts";
import {
  getIndustryHumanHero,
  getIndustryStoryMedia,
  getUseCaseHumanHero,
  getUseCaseStoryMedia,
  humanIndustries,
  humanUseCases,
} from "./marketing/human-assets.ts";
import {
  getIndustryBusinessVisual,
  getUseCaseBusinessVisual,
  industryBusinessVisuals,
  useCaseBusinessVisuals,
} from "./marketing/human-business-visuals.ts";
import {
  getIndustryHeroAsset,
  getIndustryStoryAssets,
  getUseCaseHeroAsset,
  getUseCaseStoryAssets,
  threeDIndustries,
  threeDUseCases,
} from "./marketing/three-d-assets.ts";
import { industryVisuals, useCaseVisuals } from "./marketing/visuals.ts";
import { absoluteUrl, getSiteUrl } from "./seo.ts";

function assertUniqueStrings(values: string[], label: string) {
  const seen = new Set<string>();
  for (const value of values) {
    assert.ok(value.trim().length > 0, `${label} must be non-empty`);
    assert.ok(!seen.has(value), `duplicate ${label}: ${value}`);
    seen.add(value);
  }
}

test("getSiteUrl and absoluteUrl normalize the canonical origin", () => {
  process.env.NEXT_PUBLIC_SITE_URL = "https://callandflow.com/";
  assert.equal(getSiteUrl(), "https://callandflow.com");
  assert.equal(absoluteUrl("/pricing"), "https://callandflow.com/pricing");
  assert.equal(absoluteUrl("/"), "https://callandflow.com");
});

test("marketing route registries cover commercial SEO pages", () => {
  const paths = PUBLIC_MARKETING_ROUTES.map((route) => route.path);
  assert.ok(paths.includes("/"));
  assert.ok(paths.includes("/ai-receptionist"));
  assert.ok(paths.includes("/ai-voice-agents"));
  assert.ok(paths.includes("/pricing"));
  assert.ok(paths.includes("/industries"));
  assert.ok(paths.includes("/use-cases"));
  assert.ok(paths.includes("/blog"));
  assert.equal(industryPages.length, 12);
  assert.equal(useCasePages.length, 5);
  assert.ok(blogPosts.length >= 7);
  assert.ok(ROBOTS_DISALLOW.includes("/dashboard"));
  assert.ok(ROBOTS_DISALLOW.includes("/api/"));
});

test("robots disallow does not block public marketing paths", () => {
  const publicPaths = [
    "/",
    "/ai-receptionist",
    "/ai-voice-agents",
    "/pricing",
    "/industries",
    "/industries/hvac",
    "/use-cases",
    "/use-cases/call-answering",
    "/blog",
    "/blog/what-is-an-ai-receptionist",
    "/signup",
  ];
  for (const path of publicPaths) {
    for (const rule of ROBOTS_DISALLOW) {
      assert.ok(
        path !== rule && !path.startsWith(rule.replace(/\/$/, "")),
        `robots disallow ${rule} must not block ${path}`,
      );
    }
  }
});

test("sitemap sources include hubs, landers, pricing, blog, and posts", () => {
  const paths = new Set(PUBLIC_MARKETING_ROUTES.map((route) => route.path));
  for (const required of [
    "/",
    "/ai-receptionist",
    "/ai-voice-agents",
    "/pricing",
    "/industries",
    "/use-cases",
    "/blog",
  ]) {
    assert.ok(paths.has(required), `missing sitemap static route ${required}`);
  }
  assert.equal(industryPages.length, 12);
  assert.equal(useCasePages.length, 5);
  assert.ok(blogPosts.every((post) => post.slug.length > 0));
});

test("industry and use-case pages have unique titles, descriptions, and H1s", () => {
  assertUniqueStrings(
    industryPages.map((page) => page.title),
    "industry title",
  );
  assertUniqueStrings(
    industryPages.map((page) => page.description),
    "industry description",
  );
  assertUniqueStrings(
    industryPages.map((page) => page.h1),
    "industry h1",
  );
  assertUniqueStrings(
    useCasePages.map((page) => page.title),
    "use-case title",
  );
  assertUniqueStrings(
    useCasePages.map((page) => page.description),
    "use-case description",
  );
  assertUniqueStrings(
    useCasePages.map((page) => page.h1),
    "use-case h1",
  );
});

test("product, industry, use-case, and blog entries have required SEO fields", () => {
  for (const page of [aiReceptionistPage, aiVoiceAgentsPage]) {
    assert.ok(page.path.startsWith("/"));
    assert.ok(page.title.length > 20);
    assert.ok(page.description.length > 40);
    assert.ok(page.h1.length > 10);
    assert.ok(page.keywords.length >= 3);
  }

  assert.ok(useCasesHub.title.length > 10);
  assert.ok(useCasesHub.description.length > 40);
  assert.ok(useCasesHub.h1.length > 5);

  for (const page of industryPages) {
    assert.ok(page.slug.length > 0);
    assert.ok(page.title.length > 10);
    assert.ok(page.description.length > 40);
    assert.ok(page.h1.length > 10);
    assert.ok(page.keywords.length >= 2);
    assert.ok(page.faqs.length >= 2);
    assert.ok(page.relatedSlugs.length >= 1);
    assert.ok(page.useCaseHrefs.length >= 1);
    for (const href of page.useCaseHrefs) {
      assert.ok(href.startsWith("/use-cases/"));
    }
  }

  for (const page of useCasePages) {
    assert.ok(page.slug.length > 0);
    assert.ok(page.title.length > 10);
    assert.ok(page.description.length > 40);
    assert.ok(page.h1.length > 10);
    assert.ok(page.keywords.length >= 2);
    assert.ok(page.faqs.length >= 2);
    assert.ok(page.relatedIndustries.length >= 1);
    assert.ok(page.relatedUseCases.length >= 1);
  }

  assertUniqueStrings(
    blogPosts.map((post) => post.slug),
    "blog slug",
  );
  assertUniqueStrings(
    blogPosts.map((post) => post.title),
    "blog title",
  );
  for (const post of blogPosts) {
    assert.ok(post.description.length > 40);
    assert.ok(post.sections.length >= 3);
    assert.ok(post.publishedAt.length > 0);
    assert.ok(post.updatedAt.length > 0);
    assert.ok((post.relatedLinks?.length ?? 0) >= 1);
    for (const link of post.relatedLinks ?? []) {
      assert.ok(link.href.startsWith("/"));
      assert.ok(!link.href.startsWith("//"));
    }
  }
});

test("pillar and use-case intents stay differentiated", () => {
  assert.notEqual(aiReceptionistPage.title, useCasePages.find((p) => p.slug === "call-answering")?.title);
  assert.notEqual(aiReceptionistPage.h1, useCasePages.find((p) => p.slug === "call-answering")?.h1);
  assert.notEqual(aiVoiceAgentsPage.title, useCasePages.find((p) => p.slug === "sales-calls")?.title);
  assert.notEqual(aiVoiceAgentsPage.h1, useCasePages.find((p) => p.slug === "sales-calls")?.h1);
  assert.notEqual(useCasesHub.title, useCasePages[0]?.title);
  assert.ok(useCasesHub.h1.toLowerCase().includes("use case"));
});

test("every industry and use-case page has a unique visual config", () => {
  for (const industry of industryPages) {
    assert.ok(
      industryVisuals[industry.slug],
      `missing industry visual for ${industry.slug}`,
    );
  }
  for (const useCase of useCasePages) {
    assert.ok(
      useCaseVisuals[useCase.slug],
      `missing use-case visual for ${useCase.slug}`,
    );
  }
});

test("every industry and use-case page has alternating story sections", () => {
  for (const industry of industryPages) {
    const story = industryStories[industry.slug];
    assert.ok(story, `missing industry story for ${industry.slug}`);
    assert.equal(story.sections.length, 4);
  }
  for (const useCase of useCasePages) {
    const story = useCaseStories[useCase.slug];
    assert.ok(story, `missing use-case story for ${useCase.slug}`);
    assert.equal(story.sections.length, 4);
  }
});

test("every industry and use-case page maps unique 3D story assets", () => {
  for (const industry of industryPages) {
    assert.ok(
      threeDIndustries[industry.slug],
      `missing industry 3D asset for ${industry.slug}`,
    );
    assert.ok(getIndustryHeroAsset(industry.slug).src.includes("/images/3d/"));
    const storyAssets = getIndustryStoryAssets(industry.slug);
    assert.equal(storyAssets.length, 4);
  }
  for (const useCase of useCasePages) {
    assert.ok(
      threeDUseCases[useCase.slug],
      `missing use-case 3D asset for ${useCase.slug}`,
    );
    assert.ok(getUseCaseHeroAsset(useCase.slug).src.includes("/images/3d/"));
    const storyAssets = getUseCaseStoryAssets(useCase.slug);
    assert.equal(storyAssets.length, 4);
  }
});

test("every industry and use-case page maps human + mixed story media", () => {
  const compositions = new Set([
    "human-product",
    "three-d",
    "human-3d",
    "human-handoff",
  ]);
  for (const industry of industryPages) {
    assert.ok(
      humanIndustries[industry.slug],
      `missing industry human asset for ${industry.slug}`,
    );
    assert.ok(
      getIndustryHumanHero(industry.slug).src.includes(
        "/images/human/business/industries/",
      ),
    );
    const media = getIndustryStoryMedia(industry.slug);
    assert.equal(media.length, 4);
    assert.equal(media[0].composition, "human-product");
    assert.equal(media[1].composition, "three-d");
    assert.ok(media[0].human);
    assert.ok(media[1].threeD);
    for (const item of media) {
      assert.ok(compositions.has(item.composition));
    }
  }
  for (const useCase of useCasePages) {
    assert.ok(
      humanUseCases[useCase.slug],
      `missing use-case human asset for ${useCase.slug}`,
    );
    assert.ok(
      getUseCaseHumanHero(useCase.slug).src.includes(
        "/images/human/business/use-cases/",
      ),
    );
    const media = getUseCaseStoryMedia(useCase.slug);
    assert.equal(media.length, 4);
    assert.equal(media[0].composition, "human-product");
    assert.ok(media.some((item) => item.composition === "three-d"));
  }
});

test("every industry and use-case page has a unique human-business campaign visual", () => {
  const industrySources = new Set<string>();
  const useCaseSources = new Set<string>();

  for (const industry of industryPages) {
    const visual = getIndustryBusinessVisual(industry.slug);
    assert.ok(visual, `missing industry business visual for ${industry.slug}`);
    assert.ok(industryBusinessVisuals[industry.slug]);
    assert.ok(visual.image.src.includes("/images/human/business/industries/"));
    assert.ok(visual.personRole.length > 0);
    assert.ok(visual.environment.length > 0);
    assert.ok(visual.workflow.length >= 3);
    assert.ok(visual.overlayCards.length >= 3);
    assert.ok(visual.threeDAsset?.src.includes("/images/3d/"));
    industrySources.add(visual.image.src);
  }
  assert.equal(industrySources.size, industryPages.length);

  for (const useCase of useCasePages) {
    const visual = getUseCaseBusinessVisual(useCase.slug);
    assert.ok(visual, `missing use-case business visual for ${useCase.slug}`);
    assert.ok(useCaseBusinessVisuals[useCase.slug]);
    assert.ok(visual.image.src.includes("/images/human/business/use-cases/"));
    assert.ok(visual.workflow.length >= 3);
    assert.ok(visual.overlayCards.length >= 3);
    useCaseSources.add(visual.image.src);
  }
  assert.equal(useCaseSources.size, useCasePages.length);
});

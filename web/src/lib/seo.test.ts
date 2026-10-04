import assert from "node:assert/strict";
import test from "node:test";
import { industryPages } from "./marketing/industries.ts";
import { PUBLIC_MARKETING_ROUTES, ROBOTS_DISALLOW } from "./marketing/routes.ts";
import { useCasePages } from "./marketing/use-cases.ts";
import {
  industryStories,
  useCaseStories,
} from "./marketing/feature-sections.ts";
import { industryVisuals, useCaseVisuals } from "./marketing/visuals.ts";
import { absoluteUrl, getSiteUrl } from "./seo.ts";

test("getSiteUrl and absoluteUrl normalize the canonical origin", () => {
  process.env.NEXT_PUBLIC_SITE_URL = "https://callandflow.com/";
  assert.equal(getSiteUrl(), "https://callandflow.com");
  assert.equal(absoluteUrl("/pricing"), "https://callandflow.com/pricing");
  assert.equal(absoluteUrl("/"), "https://callandflow.com");
});

test("marketing route registries cover commercial SEO pages", () => {
  const paths = PUBLIC_MARKETING_ROUTES.map((route) => route.path);
  assert.ok(paths.includes("/ai-receptionist"));
  assert.ok(paths.includes("/ai-voice-agents"));
  assert.ok(paths.includes("/pricing"));
  assert.ok(paths.includes("/industries"));
  assert.equal(industryPages.length, 12);
  assert.equal(useCasePages.length, 5);
  assert.ok(ROBOTS_DISALLOW.includes("/dashboard"));
  assert.ok(ROBOTS_DISALLOW.includes("/api/"));
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

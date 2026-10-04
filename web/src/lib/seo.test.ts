import assert from "node:assert/strict";
import test from "node:test";
import { industryPages } from "./marketing/industries.ts";
import { PUBLIC_MARKETING_ROUTES, ROBOTS_DISALLOW } from "./marketing/routes.ts";
import { useCasePages } from "./marketing/use-cases.ts";
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

import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  isSignupSlugFormatValid,
  normalizeSignupSlug,
  slugifyBusinessName,
} from "./signup-slug.ts";

describe("signup-slug", () => {
  it("slugifies business names", () => {
    assert.equal(slugifyBusinessName("Acme HVAC Co."), "acme-hvac-co");
    assert.equal(slugifyBusinessName("  --Hello--  "), "hello");
    assert.equal(slugifyBusinessName("!!!"), "workspace");
  });

  it("validates format without hitting the network", () => {
    assert.equal(isSignupSlugFormatValid("acme"), true);
    assert.equal(isSignupSlugFormatValid("acme-hvac"), true);
    assert.equal(isSignupSlugFormatValid("a"), false);
    assert.equal(isSignupSlugFormatValid("Acme"), true);
    assert.equal(isSignupSlugFormatValid("acme_hvac"), false);
    assert.equal(isSignupSlugFormatValid("-acme"), false);
  });

  it("normalizes for comparison", () => {
    assert.equal(normalizeSignupSlug("  AcMe  "), "acme");
  });
});

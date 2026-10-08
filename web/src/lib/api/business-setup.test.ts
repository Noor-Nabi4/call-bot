import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { confidenceLabel } from "./business-setup-format.ts";

describe("business-setup confidenceLabel", () => {
  it("maps confidence bands", () => {
    assert.equal(confidenceLabel("high"), "High confidence");
    assert.equal(confidenceLabel("medium"), "Medium confidence");
    assert.equal(confidenceLabel("low"), "Low confidence");
    assert.equal(confidenceLabel("unknown"), "Confidence unknown");
  });
});

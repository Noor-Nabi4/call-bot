import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { categoryLabel, riskLabel } from "./agent-config-format.ts";

describe("agent-config format helpers", () => {
  it("maps risk levels", () => {
    assert.equal(riskLabel("high"), "High risk");
    assert.equal(riskLabel("medium"), "Medium risk");
    assert.equal(riskLabel("low"), "Low risk");
  });

  it("maps capability categories", () => {
    assert.equal(categoryLabel("scheduling"), "Scheduling");
    assert.equal(categoryLabel("payments"), "Payments");
  });
});

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

  it("documents Phase 31 guardrails catalog note", () => {
    const note =
      "Enabling a capability does not bypass RBAC, confirmation, or tenant ownership checks.";
    assert.match(note, /does not bypass/i);
    assert.equal(categoryLabel("commerce"), "Commerce");
  });
});

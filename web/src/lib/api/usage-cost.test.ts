import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  formatNullablePct,
  formatNullableUsd,
  provenanceLabel,
} from "./usage-cost-format.ts";

describe("usage-cost formatters", () => {
  it("shows N/A for unavailable money and margin", () => {
    assert.equal(formatNullableUsd(null), "N/A");
    assert.equal(formatNullablePct(null), "N/A");
  });

  it("formats configured values", () => {
    assert.match(formatNullableUsd(12.5), /\$12\.50/);
    assert.equal(formatNullablePct(33.3), "33.3%");
  });

  it("labels provenance honestly", () => {
    assert.equal(provenanceLabel("ACTUAL_PROVIDER"), "Actual");
    assert.equal(provenanceLabel("CONFIGURED_RATE"), "Configured");
    assert.equal(provenanceLabel("ESTIMATED"), "Estimated");
    assert.equal(provenanceLabel("UNAVAILABLE"), "Unavailable");
  });
});

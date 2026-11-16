import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { formatMoney, formatPercent } from "./metrics-format.ts";

describe("formatMoney", () => {
  it("formats USD amounts", () => {
    const out = formatMoney(1284);
    assert.ok(out.includes("1") && out.includes("284"));
  });

  it("returns em dash for null", () => {
    assert.equal(formatMoney(null), "—");
  });
});

describe("formatPercent", () => {
  it("formats rates as percent", () => {
    assert.equal(formatPercent(0.875), "88%");
  });

  it("returns em dash for null", () => {
    assert.equal(formatPercent(null), "—");
  });
});

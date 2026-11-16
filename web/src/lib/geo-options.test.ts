import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  catalogToOptions,
  normalizeCountryCode,
  normalizeCurrencyCode,
  optionsWithCurrent,
} from "./geo-options.ts";

describe("geo-options", () => {
  it("normalizes country and currency codes", () => {
    assert.equal(normalizeCountryCode("pk"), "PK");
    assert.equal(normalizeCountryCode("Pakistan"), "");
    assert.equal(normalizeCurrencyCode(" usd "), "USD");
  });

  it("maps catalog items and preserves current values", () => {
    assert.deepEqual(catalogToOptions([{ key: "US", name: "United States" }]), [
      { value: "US", label: "United States" },
    ]);
    const opts = optionsWithCurrent(
      [{ value: "US", label: "United States" }],
      "XX",
    );
    assert.equal(opts[0]?.value, "XX");
  });
});

import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  catalogToCountryOptions,
  catalogToCurrencyOptions,
  catalogToOptions,
  countryFlagEmoji,
  currencySymbol,
  defaultCurrencyForCountry,
  formatCountryLabel,
  formatCurrencyLabel,
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

  it("builds flag and currency labels", () => {
    assert.equal(countryFlagEmoji("PK"), "🇵🇰");
    assert.equal(formatCountryLabel("US", "United States"), "🇺🇸 United States");
    assert.equal(currencySymbol("USD", "$"), "$");
    assert.match(formatCurrencyLabel("PKR", "Pakistani Rupee", "₨"), /₨ PKR/);
  });

  it("maps catalog items and preserves current values", () => {
    assert.deepEqual(catalogToOptions([{ key: "US", name: "United States" }]), [
      { value: "US", label: "United States" },
    ]);
    assert.equal(
      catalogToCountryOptions([
        { key: "PK", name: "Pakistan", default_currency_code: "PKR" },
      ])[0]?.label,
      "🇵🇰 Pakistan",
    );
    assert.match(
      catalogToCurrencyOptions([
        { key: "PKR", name: "Pakistani Rupee", symbol: "₨" },
      ])[0]?.label || "",
      /₨ PKR/,
    );
    const opts = optionsWithCurrent(
      [{ value: "US", label: "United States" }],
      "XX",
    );
    assert.equal(opts[0]?.value, "XX");
    assert.equal(
      defaultCurrencyForCountry("PK", [
        { key: "PK", name: "Pakistan", default_currency_code: "PKR" },
      ]),
      "PKR",
    );
  });
});

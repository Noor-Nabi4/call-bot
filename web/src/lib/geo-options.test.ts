import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  applyLiveGeoDefaults,
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

  it("applies live defaults only over blank geo fields", () => {
    const countries = [
      { key: "PK", name: "Pakistan", default_currency_code: "PKR" },
      { key: "US", name: "United States", default_currency_code: "USD" },
    ];
    const filled = applyLiveGeoDefaults(
      {
        country: "US",
        currency: "USD",
        timezone: "America/New_York",
      },
      countries,
    );
    assert.equal(filled.country, "US");
    assert.equal(filled.currency, "USD");
    assert.equal(filled.timezone, "America/New_York");

    // Saved US+USD must survive refresh even when wall clock is Asia/Karachi.
    const karachiSavedUs = applyLiveGeoDefaults(
      { country: "US", currency: "USD", timezone: "Asia/Karachi" },
      countries,
    );
    assert.equal(karachiSavedUs.country, "US");
    assert.equal(karachiSavedUs.currency, "USD");
    assert.equal(karachiSavedUs.timezone, "Asia/Karachi");

    // Blank country may be inferred from timezone for first-time fill only.
    const blank = applyLiveGeoDefaults(
      { country: null, currency: null, timezone: "Asia/Karachi" },
      countries,
    );
    assert.equal(blank.country, "PK");
    assert.equal(blank.currency, "PKR");
    assert.equal(blank.timezone, "Asia/Karachi");

    // Explicit UTC stays UTC; blank timezone may take browser/live value.
    const explicitUtc = applyLiveGeoDefaults(
      { country: "GB", currency: "GBP", timezone: "UTC" },
      countries,
    );
    assert.equal(explicitUtc.country, "GB");
    assert.equal(explicitUtc.currency, "GBP");
    assert.equal(explicitUtc.timezone, "UTC");
  });
});

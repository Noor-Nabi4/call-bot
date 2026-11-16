import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { formatDurationSeconds } from "./analytics-format.ts";

describe("formatDurationSeconds", () => {
  it("formats seconds", () => {
    assert.equal(formatDurationSeconds(45), "45s");
  });

  it("formats minutes", () => {
    assert.equal(formatDurationSeconds(90), "1m 30s");
  });

  it("returns em dash for null", () => {
    assert.equal(formatDurationSeconds(null), "—");
  });
});

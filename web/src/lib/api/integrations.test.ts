import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { statusLabel } from "./integrations-format.ts";

describe("integrations statusLabel", () => {
  it("maps known statuses", () => {
    assert.equal(statusLabel("CONNECTED"), "Connected");
    assert.equal(statusLabel("SYNCED"), "Connected");
    assert.equal(statusLabel("SYNCING"), "Syncing");
    assert.equal(statusLabel("REAUTH_REQUIRED"), "Reauthorization required");
    assert.equal(statusLabel("DISCONNECTED"), "Disconnected");
    assert.equal(statusLabel("ERROR"), "Error");
  });
});

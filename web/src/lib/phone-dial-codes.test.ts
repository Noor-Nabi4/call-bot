import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  joinPhoneE164,
  splitPhoneE164,
} from "./phone-dial-codes.ts";

describe("phone-dial-codes", () => {
  it("splits Pakistani E.164 with preferred country", () => {
    const parts = splitPhoneE164("+923056466676", "PK");
    assert.equal(parts.iso, "PK");
    assert.equal(parts.dial, "92");
    assert.equal(parts.national, "3056466676");
  });

  it("joins dial + national into E.164", () => {
    assert.equal(joinPhoneE164("92", "3056466676"), "+923056466676");
    assert.equal(joinPhoneE164("92", "03056466676"), "+923056466676");
    assert.equal(joinPhoneE164("92", ""), "");
  });

  it("keeps US number when preferred is US", () => {
    const parts = splitPhoneE164("+15551234567", "US");
    assert.equal(parts.iso, "US");
    assert.equal(parts.dial, "1");
    assert.equal(parts.national, "5551234567");
  });
});

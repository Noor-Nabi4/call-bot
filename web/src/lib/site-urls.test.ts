import assert from "node:assert/strict";
import test from "node:test";
import {
  opsLoginUrl,
  opsPlaygroundUrl,
  opsUrl,
  resolveFooterHref,
} from "./site-urls.ts";

test("ops and marketing share same-origin paths", () => {
  assert.equal(opsLoginUrl(), "/login");
  assert.equal(opsPlaygroundUrl(), "/playground");
  assert.equal(opsUrl(), "/login");
  assert.equal(resolveFooterHref("playground"), "/playground");
  assert.equal(resolveFooterHref("ops"), "/login");
  assert.equal(resolveFooterHref("login"), "/login");
  assert.equal(resolveFooterHref("pricing"), "/#pricing");
});

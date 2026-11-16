import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  ORDER_CANCELLABLE,
  ORDER_FORWARD_TRANSITIONS,
  ORDER_STATUSES,
} from "./order-constants.ts";

describe("orders transition map", () => {
  it("exposes all statuses", () => {
    assert.equal(ORDER_STATUSES.length, 8);
    assert.ok(ORDER_STATUSES.includes("DRAFT"));
    assert.ok(ORDER_STATUSES.includes("REFUNDED"));
  });

  it("only allows forward transitions via dedicated map", () => {
    assert.deepEqual(ORDER_FORWARD_TRANSITIONS.DRAFT, ["PENDING"]);
    assert.deepEqual(ORDER_FORWARD_TRANSITIONS.DELIVERED, []);
    assert.ok(ORDER_CANCELLABLE.has("SHIPPED"));
    assert.ok(!ORDER_CANCELLABLE.has("DELIVERED"));
    assert.ok(!ORDER_CANCELLABLE.has("REFUNDED"));
  });
});

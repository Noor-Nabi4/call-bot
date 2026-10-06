import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  JOB_ACTIVE_STATUSES,
  JOB_ASSIGNABLE_STATUSES,
  JOB_CANCELLABLE,
  JOB_FORWARD_TRANSITIONS,
  JOB_STATUSES,
  JOB_TERMINAL_STATUSES,
  jobStatusLabel,
} from "./job-constants.ts";

describe("job status constants", () => {
  it("exposes all statuses, uppercase", () => {
    assert.equal(JOB_STATUSES.length, 10);
    assert.ok(JOB_STATUSES.includes("NEW"));
    assert.ok(JOB_STATUSES.includes("CANCELLED"));
    for (const s of JOB_STATUSES) {
      assert.equal(s, s.toUpperCase());
    }
  });

  it("marks exactly the terminal statuses", () => {
    assert.ok(JOB_TERMINAL_STATUSES.has("COMPLETED"));
    assert.ok(JOB_TERMINAL_STATUSES.has("CANCELLED"));
    assert.ok(JOB_TERMINAL_STATUSES.has("NO_SHOW"));
    assert.ok(!JOB_TERMINAL_STATUSES.has("IN_PROGRESS"));
  });

  it("active statuses are the complement of terminal statuses", () => {
    for (const s of JOB_STATUSES) {
      assert.equal(
        JOB_ACTIVE_STATUSES.has(s),
        !JOB_TERMINAL_STATUSES.has(s),
      );
    }
  });

  it("only allows forward transitions via the dedicated map", () => {
    assert.deepEqual(JOB_FORWARD_TRANSITIONS.NEW, ["SCHEDULED"]);
    assert.deepEqual(JOB_FORWARD_TRANSITIONS.COMPLETED, []);
    assert.deepEqual(JOB_FORWARD_TRANSITIONS.CANCELLED, []);
    assert.ok(JOB_CANCELLABLE.has("DISPATCHED"));
    assert.ok(!JOB_CANCELLABLE.has("COMPLETED"));
    assert.ok(!JOB_CANCELLABLE.has("CANCELLED"));
  });

  it("technicians may only be assigned through DISPATCHED", () => {
    assert.ok(JOB_ASSIGNABLE_STATUSES.has("SCHEDULED"));
    assert.ok(JOB_ASSIGNABLE_STATUSES.has("DISPATCHED"));
    assert.ok(!JOB_ASSIGNABLE_STATUSES.has("EN_ROUTE"));
    assert.ok(!JOB_ASSIGNABLE_STATUSES.has("IN_PROGRESS"));
    assert.ok(!JOB_ASSIGNABLE_STATUSES.has("COMPLETED"));
    assert.ok(!JOB_ASSIGNABLE_STATUSES.has("CANCELLED"));
  });

  it("labels normalize casing and fall back to a humanized string", () => {
    assert.equal(jobStatusLabel("in_progress"), "In progress");
    assert.equal(jobStatusLabel("IN_PROGRESS"), "In progress");
    assert.equal(jobStatusLabel("SOMETHING_ELSE"), "SOMETHING ELSE");
  });
});

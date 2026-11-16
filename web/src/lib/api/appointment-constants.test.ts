import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  APPOINTMENT_CANCELLABLE,
  APPOINTMENT_FORWARD,
  APPOINTMENT_STATUSES,
  APPOINTMENT_TERMINAL,
  appointmentStatusLabel,
} from "./appointment-constants.ts";
import { ApiError, isBookingConflict } from "./api-error.ts";

describe("appointment status constants", () => {
  it("exposes all statuses uppercase", () => {
    assert.equal(APPOINTMENT_STATUSES.length, 7);
    for (const s of APPOINTMENT_STATUSES) {
      assert.equal(s, s.toUpperCase());
    }
  });

  it("marks terminal statuses", () => {
    assert.ok(APPOINTMENT_TERMINAL.has("COMPLETED"));
    assert.ok(APPOINTMENT_TERMINAL.has("CANCELLED"));
    assert.ok(APPOINTMENT_TERMINAL.has("NO_SHOW"));
    assert.ok(!APPOINTMENT_TERMINAL.has("IN_PROGRESS"));
  });

  it("cancellable matches active booking set", () => {
    assert.ok(APPOINTMENT_CANCELLABLE.has("SCHEDULED"));
    assert.ok(APPOINTMENT_CANCELLABLE.has("IN_PROGRESS"));
    assert.ok(!APPOINTMENT_CANCELLABLE.has("COMPLETED"));
  });

  it("forward map has no exits from terminal", () => {
    assert.deepEqual(APPOINTMENT_FORWARD.COMPLETED, []);
    assert.deepEqual(APPOINTMENT_FORWARD.CANCELLED, []);
    assert.deepEqual(APPOINTMENT_FORWARD.NO_SHOW, []);
  });

  it("labels normalize casing", () => {
    assert.equal(appointmentStatusLabel("in_progress"), "In progress");
    assert.equal(appointmentStatusLabel("NO_SHOW"), "No show");
  });
});

describe("booking conflict detection", () => {
  it("treats 409 and slot_conflict as booking conflicts", () => {
    assert.equal(
      isBookingConflict(new ApiError("taken", 409, "slot_conflict")),
      true,
    );
    assert.equal(
      isBookingConflict(new ApiError("taken", 409, "appointment_conflict")),
      true,
    );
    assert.equal(
      isBookingConflict(new ApiError("bad", 400, "invalid_transition")),
      false,
    );
    assert.equal(isBookingConflict(new Error("taken")), false);
  });
});

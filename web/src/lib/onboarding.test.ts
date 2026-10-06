import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  progressLabel,
  resumeTarget,
  type OnboardingState,
} from "./onboarding.ts";

function state(partial: Partial<OnboardingState>): OnboardingState {
  return {
    id: "1",
    tenant_id: "t",
    status: "IN_PROGRESS",
    current_step: "industry",
    resume_step: "industry",
    completed_steps: ["business_profile"],
    skipped_steps: [],
    progress_percent: 9,
    completed_count: 1,
    total_count: 11,
    required_remaining: ["industry"],
    can_resume: true,
    steps: [],
    state_data: {},
    ...partial,
  };
}

describe("onboarding helpers", () => {
  it("formats progress label", () => {
    assert.equal(
      progressLabel(state({})),
      "1 of 11 steps · 9%",
    );
  });

  it("resumeTarget prefers resume_step while in progress", () => {
    assert.equal(resumeTarget(state({})), "industry");
    assert.equal(
      resumeTarget(state({ status: "COMPLETED", resume_step: null })),
      null,
    );
    assert.equal(
      resumeTarget(
        state({
          resume_step: null,
          current_step: "business_model",
          status: "IN_PROGRESS",
        }),
      ),
      "business_model",
    );
  });
});

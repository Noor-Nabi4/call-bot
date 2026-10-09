import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { OpsUser } from "../types/index.ts";
import {
  isAiSetupConfirmed,
  isOnboardingComplete,
  progressLabel,
  resumeTarget,
  setupPathFromState,
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

function user(
  partial: Partial<OpsUser> & {
    onboarding_complete?: boolean;
    onboarding_status?: OpsUser["onboarding_status"];
  },
): OpsUser {
  return {
    id: "1",
    tenant_id: "t",
    tenant_slug: "t",
    tenant_name: "T",
    email: "a@t.test",
    name: "A",
    role: "admin",
    technician_id: null,
    roles: [],
    permissions: [],
    ...partial,
  };
}

describe("onboarding helpers", () => {
  it("formats progress label", () => {
    assert.equal(progressLabel(state({})), "1 of 11 steps · 9%");
  });

  it("resumeTarget prefers resume_step while in progress", () => {
    assert.equal(resumeTarget(state({})), "industry");
    assert.equal(
      resumeTarget(state({ status: "COMPLETED", resume_step: null })),
      null,
    );
  });

  it("setupPathFromState reads AI/manual choice from state_data", () => {
    assert.equal(setupPathFromState(state({})), null);
    assert.equal(
      setupPathFromState(state({ state_data: { setup_path: "ai" } })),
      "ai",
    );
    assert.equal(
      setupPathFromState(state({ state_data: { setup_path: "manual" } })),
      "manual",
    );
    assert.equal(
      setupPathFromState(
        state({ status: "COMPLETED", state_data: { setup_path: "ai" } }),
      ),
      null,
    );
  });

  it("isAiSetupConfirmed requires CONFIRMED blob", () => {
    assert.equal(isAiSetupConfirmed(state({})), false);
    assert.equal(
      isAiSetupConfirmed(
        state({ state_data: { ai_business_setup: { status: "REVIEW" } } }),
      ),
      false,
    );
    assert.equal(
      isAiSetupConfirmed(
        state({ state_data: { ai_business_setup: { status: "CONFIRMED" } } }),
      ),
      true,
    );
  });

  it("incomplete status is not complete; COMPLETED/SKIPPED are", () => {
    assert.equal(
      isOnboardingComplete(user({ onboarding_status: "NOT_STARTED" })),
      false,
    );
    assert.equal(
      isOnboardingComplete(user({ onboarding_status: "COMPLETED" })),
      true,
    );
  });
});

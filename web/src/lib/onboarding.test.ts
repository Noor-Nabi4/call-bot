import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { OpsUser } from "../types/index.ts";
import {
  isAiSetupConfirmed,
  isOnboardingComplete,
  isPhoneSetupReady,
  needsPhoneSetup,
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
      resumeTarget(
        state({
          status: "COMPLETED",
          resume_step: null,
          phone_setup: { state: "ready", eligible_count: 1 },
        }),
      ),
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

  it("access requires COMPLETED business setup AND phone_ready", () => {
    assert.equal(
      isOnboardingComplete(user({ onboarding_status: "COMPLETED" })),
      false,
    );
    assert.equal(
      isOnboardingComplete(
        user({
          onboarding_status: "COMPLETED",
          business_onboarding_complete: true,
          phone_ready: false,
        }),
      ),
      false,
    );
    assert.equal(
      isOnboardingComplete(
        user({
          onboarding_status: "COMPLETED",
          business_onboarding_complete: true,
          phone_ready: true,
        }),
      ),
      true,
    );
    assert.equal(
      isOnboardingComplete(user({ onboarding_complete: true })),
      true,
    );
    assert.equal(
      needsPhoneSetup(
        user({
          onboarding_status: "COMPLETED",
          business_onboarding_complete: true,
          phone_ready: false,
        }),
      ),
      true,
    );
  });

  it("resumeTarget allows SKIPPED orgs to resume", () => {
    assert.equal(
      resumeTarget(state({ status: "SKIPPED", resume_step: "industry" })),
      "industry",
    );
  });

  it("resumeTarget sends COMPLETED orgs without phone to phone_setup", () => {
    assert.equal(
      resumeTarget(state({ status: "COMPLETED", resume_step: null })),
      "phone_setup",
    );
  });

  it("isPhoneSetupReady requires ready state from backend", () => {
    assert.equal(isPhoneSetupReady(state({})), false);
    assert.equal(
      isPhoneSetupReady(
        state({
          phone_setup: {
            state: "setup_in_progress",
            eligible_count: 0,
          },
        }),
      ),
      false,
    );
    assert.equal(
      isPhoneSetupReady(
        state({
          phone_setup: {
            state: "ready",
            eligible_count: 1,
            primary_e164: "+15551234567",
          },
        }),
      ),
      true,
    );
  });
});

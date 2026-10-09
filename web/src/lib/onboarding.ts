/** Onboarding state types and helpers (Task 2.1 foundation). */

import type { OpsUser } from "../types";

export type OnboardingStatus =
  | "NOT_STARTED"
  | "IN_PROGRESS"
  | "COMPLETED"
  | "SKIPPED";

export type OnboardingStepState = "completed" | "skipped" | "pending";

export type OnboardingStep = {
  key: string;
  title: string;
  required: boolean;
  description?: string;
  state: OnboardingStepState;
};

export type PhoneSetupReadiness = {
  state:
    | "ready"
    | "not_configured"
    | "setup_in_progress"
    | "action_required"
    | string;
  eligible_count: number;
  primary_e164?: string | null;
  primary_phone_number_id?: string | null;
  connection_status?: string;
  verification_status?: string;
  message?: string;
};

export type OnboardingState = {
  id: string;
  tenant_id: string;
  status: OnboardingStatus;
  current_step: string | null;
  resume_step: string | null;
  completed_steps: string[];
  skipped_steps: string[];
  progress_percent: number;
  completed_count: number;
  total_count: number;
  required_remaining: string[];
  can_resume: boolean;
  steps: OnboardingStep[];
  state_data: Record<string, unknown>;
  phone_setup?: PhoneSetupReadiness;
};

export const ONBOARDING_PATH = "/onboarding";
export const ONBOARDING_AI_PATH = "/onboarding/ai-setup";
export const PHONES_ONBOARDING_PATH = "/phones?from=onboarding";

/** Persisted in OrganizationOnboarding.state_data — visual path choice only. */
export const SETUP_PATH_KEY = "setup_path";
export type OnboardingSetupPath = "ai" | "manual";

/**
 * Application access for routing. Matches backend gate:
 * COMPLETED business onboarding AND eligible inbound phone.
 */
export function isOnboardingComplete(
  user:
    | Pick<
        OpsUser,
        | "onboarding_complete"
        | "onboarding_status"
        | "phone_ready"
        | "business_onboarding_complete"
      >
    | null
    | undefined,
): boolean {
  if (!user) return false;
  if (typeof user.onboarding_complete === "boolean") {
    return user.onboarding_complete;
  }
  const businessDone =
    user.business_onboarding_complete === true ||
    user.onboarding_status === "COMPLETED";
  const phoneReady = user.phone_ready === true;
  return businessDone && phoneReady;
}

export function needsPhoneSetup(
  user:
    | Pick<
        OpsUser,
        "onboarding_status" | "phone_ready" | "business_onboarding_complete"
      >
    | null
    | undefined,
): boolean {
  if (!user) return false;
  const businessDone =
    user.business_onboarding_complete === true ||
    user.onboarding_status === "COMPLETED";
  return businessDone && user.phone_ready !== true;
}

export function setupPathFromState(
  state: Pick<OnboardingState, "state_data" | "status"> | null | undefined,
): OnboardingSetupPath | null {
  if (!state || state.status === "COMPLETED") {
    return null;
  }
  const raw = state.state_data?.[SETUP_PATH_KEY];
  if (raw === "ai" || raw === "manual") return raw;
  return null;
}

/** Whether Phase 29 AI setup has been owner-confirmed (domain persist). */
export function isAiSetupConfirmed(
  state: Pick<OnboardingState, "state_data"> | null | undefined,
): boolean {
  const blob = state?.state_data?.ai_business_setup;
  if (!blob || typeof blob !== "object") return false;
  return (blob as { status?: string }).status === "CONFIRMED";
}

export function progressLabel(state: OnboardingState): string {
  return `${state.completed_count} of ${state.total_count} steps · ${state.progress_percent}%`;
}

export function resumeTarget(state: OnboardingState): string | null {
  if (state.status === "COMPLETED") {
    return isPhoneSetupReady(state) ? null : "phone_setup";
  }
  return state.resume_step ?? state.current_step;
}

export function isPhoneSetupReady(
  state: Pick<OnboardingState, "phone_setup"> | null | undefined,
): boolean {
  return state?.phone_setup?.state === "ready";
}

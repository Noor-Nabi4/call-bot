/** Onboarding state types and helpers (Task 2.1 foundation). */

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
};

export function progressLabel(state: OnboardingState): string {
  return `${state.completed_count} of ${state.total_count} steps · ${state.progress_percent}%`;
}

export function resumeTarget(state: OnboardingState): string | null {
  if (state.status === "COMPLETED" || state.status === "SKIPPED") return null;
  return state.resume_step ?? state.current_step;
}

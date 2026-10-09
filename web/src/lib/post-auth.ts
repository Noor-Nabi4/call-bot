/** Shared post-authentication navigation helpers. */

import type { OpsUser } from "@/types";
import { isOnboardingComplete, ONBOARDING_PATH } from "@/lib/onboarding";
import { isTechnicianShell } from "@/lib/permissions";

/** Destination after login/signup session establishment. */
export function postAuthPath(user: OpsUser): string {
  if (isTechnicianShell(user)) return "/tech";
  if (!isOnboardingComplete(user)) return ONBOARDING_PATH;
  return "/dashboard";
}

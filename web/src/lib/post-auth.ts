/** Shared post-authentication navigation helpers. */

import type { OpsUser } from "@/types";
import {
  isOnboardingComplete,
  needsPhoneSetup,
  ONBOARDING_PATH,
  PHONES_ONBOARDING_PATH,
} from "@/lib/onboarding";
import { isTechnicianShell } from "@/lib/permissions";

/** Destination after login/signup session establishment. */
export function postAuthPath(user: OpsUser): string {
  // Mandatory setup wins over technician shell and postAuth destinations.
  if (needsPhoneSetup(user)) return PHONES_ONBOARDING_PATH;
  if (!isOnboardingComplete(user)) return ONBOARDING_PATH;
  if (isTechnicianShell(user)) return "/tech";
  return "/dashboard";
}

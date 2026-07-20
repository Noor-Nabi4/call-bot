/** Lightweight conversion analytics for the marketing site. */

export type AnalyticsEvent =
  | "cta_start_trial"
  | "cta_try_voice_demo"
  | "nav_click"
  | "voice_demo_start"
  | "voice_demo_connected"
  | "voice_demo_end"
  | "voice_demo_error"
  | "feature_tab_select"
  | "pricing_plan_select"
  | "signup_step"
  | "signup_submit"
  | "signup_error";

type AnalyticsProps = Record<string, string | number | boolean | undefined>;

declare global {
  interface Window {
    dataLayer?: Array<Record<string, unknown>>;
    callbotTrack?: (event: string, props?: AnalyticsProps) => void;
  }
}

export function track(event: AnalyticsEvent, props: AnalyticsProps = {}): void {
  if (typeof window === "undefined") return;

  const payload = {
    event,
    ...props,
    ts: Date.now(),
    path: window.location.pathname,
  };

  window.dispatchEvent(new CustomEvent("callbot:analytics", { detail: payload }));

  if (Array.isArray(window.dataLayer)) {
    window.dataLayer.push(payload);
  }

  if (typeof window.callbotTrack === "function") {
    try {
      window.callbotTrack(event, props);
    } catch {
      // Ignore integrator errors.
    }
  }

  if (process.env.NODE_ENV === "development") {
    console.debug("[callbot:analytics]", payload);
  }
}

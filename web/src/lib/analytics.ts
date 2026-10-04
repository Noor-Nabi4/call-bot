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
    callandflowTrack?: (event: string, props?: AnalyticsProps) => void;
    voxpilotTrack?: (event: string, props?: AnalyticsProps) => void;
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

  window.dispatchEvent(new CustomEvent("callandflow:analytics", { detail: payload }));
  window.dispatchEvent(new CustomEvent("voxpilot:analytics", { detail: payload })); // legacy
  // Back-compat for existing integrators
  window.dispatchEvent(new CustomEvent("callbot:analytics", { detail: payload }));

  if (Array.isArray(window.dataLayer)) {
    window.dataLayer.push(payload);
  }

  const tracker = window.callandflowTrack || window.voxpilotTrack || window.callbotTrack;
  if (typeof tracker === "function") {
    try {
      tracker(event, props);
    } catch {
      // Ignore integrator errors.
    }
  }

  if (process.env.NODE_ENV === "development") {
    console.debug("[callandflow:analytics]", payload);
  }
}

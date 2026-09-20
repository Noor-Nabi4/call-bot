/** Currency and duration helpers for the internal COGS dashboard. */

export function formatUsd(
  value: number | null | undefined,
  opts?: { digits?: number; compactSmall?: boolean },
): string {
  if (value == null || Number.isNaN(value)) return "N/A";
  const abs = Math.abs(value);
  let digits = opts?.digits;
  if (digits == null) {
    if (opts?.compactSmall !== false && abs > 0 && abs < 1) digits = 4;
    else digits = 2;
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

export function formatPct(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return "N/A";
  return `${value.toFixed(digits)}%`;
}

export function formatMinutes(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return "N/A";
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: digits,
    minimumFractionDigits: 0,
  }).format(value);
}

export function formatCount(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "N/A";
  return new Intl.NumberFormat("en-US").format(value);
}

export function formatDurationSeconds(seconds: number | null | undefined): string {
  if (seconds == null || seconds < 0 || Number.isNaN(seconds)) return "N/A";
  const whole = Math.floor(seconds);
  const m = Math.floor(whole / 60);
  const s = whole % 60;
  return `${m}m ${s.toString().padStart(2, "0")}s`;
}

export function shortCallId(id: string): string {
  if (!id) return "—";
  return id.length > 8 ? `#${id.slice(0, 8)}` : `#${id}`;
}

export type BreakdownItem = {
  key: string;
  label: string;
  usd: number;
  pct: number;
};

export function buildCogsBreakdown(variable: {
  openai_usd: number;
  livekit_agent_usd: number;
  livekit_sip_usd: number;
  livekit_bvc_usd: number;
  twilio_origination_usd: number;
  twilio_termination_usd: number;
  total_usd: number;
}): BreakdownItem[] {
  const rows: Array<{ key: string; label: string; usd: number }> = [
    { key: "openai", label: "OpenAI Realtime", usd: variable.openai_usd },
    { key: "agent", label: "LiveKit Agent", usd: variable.livekit_agent_usd },
    { key: "sip", label: "LiveKit SIP", usd: variable.livekit_sip_usd },
    { key: "bvc", label: "LiveKit BVC", usd: variable.livekit_bvc_usd },
    {
      key: "twilio_orig",
      label: "Twilio Origination",
      usd: variable.twilio_origination_usd,
    },
    {
      key: "twilio_term",
      label: "Twilio Termination (warm)",
      usd: variable.twilio_termination_usd,
    },
  ];
  const total = variable.total_usd;
  return rows.map((row) => ({
    ...row,
    pct: total > 0 ? (row.usd / total) * 100 : 0,
  }));
}

export function channelLabel(key: string): string {
  if (key === "pstn_sip") return "PSTN / SIP";
  if (key === "browser_webrtc") return "Browser / WebRTC";
  return key || "Unknown";
}

export function transferLabel(key: string): string {
  if (key === "warm") return "Warm transfer";
  if (key === "cold") return "Cold transfer";
  if (key === "none") return "No transfer";
  return key || "Unknown";
}

export function openaiSourceLabel(source: string | null | undefined): string {
  if (source === "token") return "Token usage";
  if (source === "per_minute_estimate") return "Estimated ($/min)";
  return source || "Unknown";
}

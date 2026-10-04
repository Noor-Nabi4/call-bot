import assert from "node:assert/strict";
import test from "node:test";
import {
  buildCogsBreakdown,
  formatDurationSeconds,
  formatPct,
  formatUsd,
  shortCallId,
} from "./cogs-format.ts";

test("formatUsd uses 4 digits for sub-dollar COGS rates", () => {
  assert.equal(formatUsd(0.0862), "$0.0862");
  assert.equal(formatUsd(1234.5), "$1,234.50");
  assert.equal(formatUsd(null), "N/A");
});

test("formatPct and duration helpers", () => {
  assert.equal(formatPct(82.76), "82.8%");
  assert.equal(formatPct(null), "N/A");
  assert.equal(formatDurationSeconds(272), "4m 32s");
  assert.equal(shortCallId("abcdefghijklmnop"), "#abcdefgh");
});

test("buildCogsBreakdown percentages sum near 100", () => {
  const rows = buildCogsBreakdown({
    openai_usd: 67.6,
    livekit_agent_usd: 10,
    livekit_sip_usd: 4,
    livekit_bvc_usd: 1.2,
    twilio_origination_usd: 3.4,
    twilio_termination_usd: 0,
    total_usd: 86.2,
  });
  const sum = rows.reduce((acc, r) => acc + r.pct, 0);
  assert.ok(Math.abs(sum - 100) < 0.1);
  assert.equal(rows[0]?.label, "OpenAI Realtime");
});

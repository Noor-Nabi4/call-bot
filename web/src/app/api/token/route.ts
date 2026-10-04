import {
  AccessToken,
  type AccessTokenOptions,
  RoomAgentDispatch,
  RoomConfiguration,
  type VideoGrant,
} from "livekit-server-sdk";
import { createHmac } from "node:crypto";
import { NextResponse } from "next/server";

export const runtime = "nodejs";

type TokenRequest = {
  roomName?: string;
  participantName?: string;
};

const RATE_WINDOW_MS = 10 * 60 * 1000;
const RATE_LIMIT = 12;
const rateBuckets = new Map<string, number[]>();

function clientKey(req: Request): string {
  const forwarded = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  return forwarded || req.headers.get("x-real-ip")?.trim() || "local";
}

function allowRequest(key: string): boolean {
  const now = Date.now();
  const recent = (rateBuckets.get(key) || []).filter(
    (ts) => now - ts < RATE_WINDOW_MS,
  );
  if (recent.length >= RATE_LIMIT) {
    rateBuckets.set(key, recent);
    return false;
  }
  recent.push(now);
  rateBuckets.set(key, recent);
  return true;
}

function requireEnv(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

function canonicalJson(payload: Record<string, unknown>): string {
  const sorted: Record<string, unknown> = {};
  for (const key of Object.keys(payload).sort()) {
    sorted[key] = payload[key];
  }
  return JSON.stringify(sorted);
}

function signAgentMetadata(payload: Record<string, unknown>): string {
  const secret = process.env.METADATA_HMAC_SECRET?.trim();
  const body: Record<string, unknown> = { ...payload };
  delete body.sig;
  if (!secret) {
    return JSON.stringify(body);
  }
  const canonical = canonicalJson(body);
  const sig = createHmac("sha256", secret).update(canonical).digest("hex");
  return JSON.stringify({ ...JSON.parse(canonical), sig });
}

async function createParticipantToken(
  userInfo: AccessTokenOptions,
  roomName: string,
  agentName: string,
): Promise<string> {
  const apiKey = requireEnv("LIVEKIT_API_KEY");
  const apiSecret = requireEnv("LIVEKIT_API_SECRET");

  const at = new AccessToken(apiKey, apiSecret, {
    ...userInfo,
    ttl: "10m",
  });

  const grant: VideoGrant = {
    room: roomName,
    roomJoin: true,
    canPublish: true,
    canSubscribe: true,
    canPublishData: true,
  };
  at.addGrant(grant);

  // Explicit agent dispatch — https://docs.livekit.io/agents/server/agent-dispatch/
  // Marketing demo is tenant-less: voice-agent uses a fixed Call & Flow persona.
  const metadataPayload: Record<string, unknown> = {
    source: "marketing",
  };
  at.roomConfig = new RoomConfiguration({
    agents: [
      new RoomAgentDispatch({
        agentName,
        metadata: signAgentMetadata(metadataPayload),
      }),
    ],
  });

  return at.toJwt();
}

/**
 * Marketing-site voice demo token endpoint.
 * Rate-limited; still requires LiveKit credentials and a running voice-agent worker.
 */
export async function POST(req: Request) {
  try {
    if (!allowRequest(clientKey(req))) {
      return NextResponse.json(
        { error: "Too many demo requests. Please try again shortly." },
        { status: 429 },
      );
    }

    const livekitUrl = requireEnv("LIVEKIT_URL");
    const agentName = process.env.AGENT_NAME?.trim() || "voice-agent";
    const body = (await req.json().catch(() => ({}))) as TokenRequest;

    const roomName =
      body.roomName?.trim() ||
      `marketing-${Math.floor(Math.random() * 10_000)}`;
    const participantName =
      body.participantName?.trim() ||
      `visitor-${Math.floor(Math.random() * 10_000)}`;

    const token = await createParticipantToken(
      {
        identity: participantName,
        name: participantName,
      },
      roomName,
      agentName,
    );

    return NextResponse.json({
      serverUrl: livekitUrl,
      roomName,
      participantName,
      participantToken: token,
      agentName,
    });
  } catch (error) {
    console.error("marketing voice demo token error", error);
    return NextResponse.json(
      { error: "We could not start the demo. Please try again." },
      { status: 500 },
    );
  }
}

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
  tenantId?: string;
};

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
    // Dev fallback: unsigned metadata (agent may use env tenant fallback).
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
  tenantId: string | undefined,
): Promise<string> {
  const apiKey = requireEnv("LIVEKIT_API_KEY");
  const apiSecret = requireEnv("LIVEKIT_API_SECRET");

  const at = new AccessToken(apiKey, apiSecret, {
    ...userInfo,
    ttl: "15m",
  });

  const grant: VideoGrant = {
    room: roomName,
    roomJoin: true,
    canPublish: true,
    canSubscribe: true,
    canPublishData: true,
  };
  at.addGrant(grant);

  // Explicit dispatch to the Python worker registered as agent_name="voice-agent".
  // https://docs.livekit.io/agents/server/agent-dispatch/
  const metadataPayload: Record<string, unknown> = {
    source: "playground",
    tenant_id: tenantId ?? null,
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
 * Local playground token endpoint.
 * Do not expose this route publicly without authentication.
 */
export async function POST(req: Request) {
  try {
    const livekitUrl = requireEnv("LIVEKIT_URL");
    const agentName = process.env.AGENT_NAME?.trim() || "voice-agent";
    const body = (await req.json().catch(() => ({}))) as TokenRequest;

    const roomName =
      body.roomName?.trim() ||
      `playground-${Math.floor(Math.random() * 10_000)}`;
    const participantName =
      body.participantName?.trim() ||
      `caller-${Math.floor(Math.random() * 10_000)}`;
    const tenantId =
      body.tenantId?.trim() || process.env.TENANT_ID?.trim() || undefined;

    const token = await createParticipantToken(
      {
        identity: participantName,
        name: participantName,
      },
      roomName,
      agentName,
      tenantId,
    );

    return NextResponse.json({
      serverUrl: livekitUrl,
      roomName,
      participantName,
      participantToken: token,
      agentName,
      tenantId: tenantId ?? null,
    });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Unable to create token";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

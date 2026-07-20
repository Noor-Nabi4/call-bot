"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AppShell } from "@/components/shell";
import { IdlePlayground, VoicePlayground } from "@/components/ops/voice-playground";
import { useAuth } from "@/lib/use-auth";
import {
  createTestCall,
  listAgentProfiles,
  type AgentProfile,
  type TestCallSession,
} from "@/lib/api";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  ErrorState,
  Field,
  LoadingSkeleton,
  PageHeader,
  Select,
  Surface,
  useToast,
} from "@/components/ui";

export default function PlaygroundPage() {
  const { user, loading } = useAuth({ roles: ["admin"] });
  const toast = useToast();
  const searchParams = useSearchParams();
  const profileFromQuery = searchParams.get("profile");

  const [profiles, setProfiles] = useState<AgentProfile[]>([]);
  const [profileId, setProfileId] = useState("");
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [session, setSession] = useState<TestCallSession | null>(null);
  const [callError, setCallError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const data = await listAgentProfiles();
    const active = data.profiles.filter((p) => p.status === "active");
    setProfiles(active);
    const preferred =
      (profileFromQuery &&
        active.find((p) => p.id === profileFromQuery)?.id) ||
      active.find((p) => p.is_default)?.id ||
      active[0]?.id ||
      "";
    setProfileId(preferred);
  }, [profileFromQuery]);

  useEffect(() => {
    if (!user) return;
    setFetching(true);
    load()
      .catch((err) => setError(safeUserError(err, "Could not load agents")))
      .finally(() => setFetching(false));
  }, [user, load]);

  const selected = useMemo(
    () => profiles.find((p) => p.id === profileId) ?? null,
    [profiles, profileId],
  );

  async function onStart() {
    if (!profileId) {
      toast.push("Select an agent profile first", "error");
      return;
    }
    setConnecting(true);
    setCallError(null);
    try {
      const next = await createTestCall(profileId);
      setSession(next);
      toast.push("Test call connected", "success");
    } catch (err) {
      const message = safeUserError(err, "Could not start test call");
      setCallError(message);
      toast.push(message, "error");
    } finally {
      setConnecting(false);
    }
  }

  function onEnded() {
    setSession(null);
  }

  if (loading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={8} />
      </div>
    );
  }

  return (
    <AppShell user={user}>
      <PageHeader
        title="Playground"
        description="Test your tenant agents in the browser before going live on phone numbers."
        actions={
          <Link href="/agents">
            <Button variant="secondary" size="sm">
              Manage agents
            </Button>
          </Link>
        }
      />

      {error ? (
        <ErrorState message={error} onRetry={() => void load()} />
      ) : fetching ? (
        <LoadingSkeleton rows={6} />
      ) : profiles.length === 0 ? (
        <Surface className="p-6">
          <p className="m-0 text-sm text-text-secondary">
            Create an agent profile first, then return here to run a voice test.
          </p>
          <Link href="/agents" className="mt-4 inline-block">
            <Button size="sm">Create agent</Button>
          </Link>
        </Surface>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,18rem)_minmax(0,1fr)]">
          <Surface className="h-fit p-5">
            <Field label="Agent profile">
              <Select
                value={profileId}
                onChange={(e) => setProfileId(e.target.value)}
                disabled={!!session}
              >
                {profiles.map((profile) => (
                  <option key={profile.id} value={profile.id}>
                    {profile.name}
                    {profile.is_default ? " (default)" : ""}
                  </option>
                ))}
              </Select>
            </Field>
            {selected ? (
              <dl className="mt-4 grid gap-2 text-sm text-text-secondary">
                <div className="flex justify-between gap-3">
                  <dt>Type</dt>
                  <dd className="text-text-primary">{selected.agent_type}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt>Language</dt>
                  <dd className="text-text-primary">
                    {selected.language || "en"}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt>Version</dt>
                  <dd className="text-text-primary">
                    v{selected.profile_version ?? 1}
                  </dd>
                </div>
              </dl>
            ) : null}
            <p className="mt-4 text-xs leading-relaxed text-text-muted">
              Sessions use signed tenant metadata (`ops_test_call`) so the voice
              agent loads your real profile, tools, and knowledge.
            </p>
          </Surface>

          {session ? (
            <VoicePlayground
              session={session}
              onEnded={onEnded}
              onError={setCallError}
            />
          ) : (
            <IdlePlayground
              connecting={connecting}
              error={callError}
              onStart={() => void onStart()}
              disabled={!profileId}
            />
          )}
        </div>
      )}
    </AppShell>
  );
}

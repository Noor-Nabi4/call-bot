"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { AppShell } from "@/components/shell";
import {
  AUTOMATION_ACTIONS,
  AUTOMATION_EVENTS,
  createAutomation,
  publishAutomation,
  activateAutomation,
} from "@/lib/api/automations";
import { useAuth } from "@/lib/use-auth";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  ErrorState,
  Field,
  Input,
  LoadingSkeleton,
  PageHeader,
  Select,
  Textarea,
} from "@/components/ui";

export default function NewAutomationPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [name, setName] = useState("");
  const [trigger, setTrigger] = useState("JOB_COMPLETED");
  const [actionType, setActionType] = useState("CREATE_TASK");
  const [actionBody, setActionBody] = useState("Follow up on completed job");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const config =
        actionType === "SEND_SMS" ||
        actionType === "SEND_EMAIL" ||
        actionType === "REQUEST_REVIEW"
          ? { body: actionBody }
          : actionType === "CREATE_TASK"
            ? { title: actionBody || "Follow up" }
            : actionType === "WEBHOOK"
              ? { url: actionBody }
              : actionType === "CREATE_JOB"
                ? { service_type: actionBody || "Follow-up" }
                : {};
      const created = await createAutomation({
        name: name.trim(),
        trigger_event: trigger,
        definition: {
          conditions: null,
          actions: [{ type: actionType, config }],
        },
      });
      await publishAutomation(created.workflow.id);
      await activateAutomation(created.workflow.id);
      router.push(`/crm/automations/${created.workflow.id}`);
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setBusy(false);
    }
  }

  if (authLoading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton />
      </div>
    );
  }

  return (
    <AppShell user={user}>
      <PageHeader title="New workflow" />
      <p className="mb-4 text-sm">
        <Link href="/crm/automations" className="underline-offset-2 hover:underline">
          Back to automations
        </Link>
      </p>
      {error ? <ErrorState message={error} /> : null}
      <form className="max-w-xl space-y-6" onSubmit={onSubmit}>
        <section className="space-y-3">
          <h2 className="text-base font-medium">WHEN</h2>
          <Field label="Name">
            <Input value={name} onChange={(e) => setName(e.target.value)} required />
          </Field>
          <Field label="Trigger event">
            <Select
              value={trigger}
              onChange={(e) => setTrigger(e.target.value)}
              aria-label="Trigger event"
            >
              {AUTOMATION_EVENTS.map((ev) => (
                <option key={ev} value={ev}>
                  {ev}
                </option>
              ))}
            </Select>
          </Field>
        </section>
        <section className="space-y-3">
          <h2 className="text-base font-medium">THEN</h2>
          <Field label="Action">
            <Select
              value={actionType}
              onChange={(e) => setActionType(e.target.value)}
              aria-label="Action type"
            >
              {AUTOMATION_ACTIONS.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </Select>
          </Field>
          <Field
            label={
              actionType === "WEBHOOK"
                ? "HTTPS URL"
                : actionType === "CREATE_TASK"
                  ? "Task title"
                  : "Message / config"
            }
          >
            <Textarea
              rows={3}
              value={actionBody}
              onChange={(e) => setActionBody(e.target.value)}
              required={actionType !== "SEND_PAYMENT_LINK"}
            />
          </Field>
        </section>
        <Button type="submit" variant="ink" disabled={busy}>
          {busy ? "Saving…" : "Publish & activate"}
        </Button>
      </form>
    </AppShell>
  );
}

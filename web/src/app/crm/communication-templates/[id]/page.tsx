"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import {
  archiveCommunicationTemplate,
  getCommunicationTemplate,
  getTemplateVariables,
  previewCommunicationTemplate,
  publishCommunicationTemplate,
  updateCommunicationTemplate,
  validateCommunicationTemplate,
  type CommunicationTemplate,
} from "@/lib/api/communication-templates";
import { safeUserError } from "@/lib/safe-error";
import { errors } from "@/lib/ops-copy";
import {
  Button,
  ErrorState,
  ForbiddenState,
  LoadingSkeleton,
  PageHeader,
  StatusPill,
  Textarea,
  useToast,
} from "@/components/ui";

export default function CommunicationTemplateDetailPage() {
  const params = useParams();
  const id = String(params.id || "");
  const { user, loading, forbidden } = useAuth({
    permission: "communication_templates.read",
  });
  const toast = useToast();
  const [row, setRow] = useState<CommunicationTemplate | null>(null);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [variables, setVariables] = useState<string[]>([]);
  const [preview, setPreview] = useState<string | null>(null);
  const [previewSubject, setPreviewSubject] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await getCommunicationTemplate(id);
      setRow(res.template);
      setSubject(res.template.subject_template || "");
      setBody(res.template.body_template || "");
      const vars = await getTemplateVariables(res.template.template_key);
      setVariables(vars.variables || []);
    } catch (e) {
      setError(safeUserError(e, errors.loadFailed));
    }
  }, [id]);

  useEffect(() => {
    if (!user || !id) return;
    void load();
  }, [user, id, load]);

  function insertVariable(v: string) {
    const token = `{{${v}}}`;
    setBody((prev) => `${prev}${prev.endsWith(" ") || !prev ? "" : " "}${token}`);
  }

  async function runValidate() {
    setBusy(true);
    try {
      const res = await validateCommunicationTemplate(id, {
        subject_template: subject || null,
        body_template: body,
      });
      setValidationErrors(res.errors || []);
      if (res.valid) toast.push("Template is valid", "success");
      else toast.push("Validation failed", "error");
    } catch (e) {
      toast.push(safeUserError(e, errors.saveFailed), "error");
    } finally {
      setBusy(false);
    }
  }

  async function runPreview() {
    setBusy(true);
    try {
      const res = await previewCommunicationTemplate(id, {
        subject_template: subject || null,
        body_template: body,
      });
      setPreview(res.rendered);
      setPreviewSubject(res.rendered_subject);
      setValidationErrors([]);
    } catch (e) {
      toast.push(safeUserError(e, errors.saveFailed), "error");
    } finally {
      setBusy(false);
    }
  }

  async function runSave(publish: boolean) {
    setBusy(true);
    try {
      const res = await updateCommunicationTemplate(id, {
        subject_template: row?.channel === "EMAIL" ? subject : null,
        body_template: body,
        publish,
      });
      setRow(res.template);
      setSubject(res.template.subject_template || "");
      setBody(res.template.body_template || "");
      toast.push(publish ? "Published new version" : "Draft saved", "success");
    } catch (e) {
      toast.push(safeUserError(e, errors.saveFailed), "error");
    } finally {
      setBusy(false);
    }
  }

  async function runPublishDraft() {
    setBusy(true);
    try {
      const res = await publishCommunicationTemplate(id);
      setRow(res.template);
      setSubject(res.template.subject_template || "");
      setBody(res.template.body_template || "");
      toast.push("Draft published", "success");
    } catch (e) {
      toast.push(safeUserError(e, errors.saveFailed), "error");
    } finally {
      setBusy(false);
    }
  }

  async function runArchive() {
    setBusy(true);
    try {
      const res = await archiveCommunicationTemplate(id);
      setRow(res.template);
      toast.push("Template archived", "success");
    } catch (e) {
      toast.push(safeUserError(e, errors.saveFailed), "error");
    } finally {
      setBusy(false);
    }
  }

  if (loading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={8} />
      </div>
    );
  }
  if (forbidden) {
    return (
      <AppShell user={user}>
        <ForbiddenState />
      </AppShell>
    );
  }

  const smsLen = body.length;

  return (
    <AppShell user={user}>
      <div className="mb-4">
        <Link
          href="/crm/communication-templates"
          className="text-sm text-brand hover:underline"
        >
          ← Back to templates
        </Link>
      </div>
      <PageHeader
        title={row?.name || "Template"}
        description={
          row
            ? `${row.channel} · ${row.template_key} · active v${row.active_version}`
            : "Loading…"
        }
        actions={
          row ? (
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="secondary" disabled={busy} onClick={() => void runValidate()}>
                Validate
              </Button>
              <Button size="sm" variant="secondary" disabled={busy} onClick={() => void runPreview()}>
                Preview
              </Button>
              <Button size="sm" variant="secondary" disabled={busy} onClick={() => void runSave(false)}>
                Save draft
              </Button>
              <Button size="sm" disabled={busy} onClick={() => void runSave(true)}>
                Save & publish
              </Button>
              <Button size="sm" variant="secondary" disabled={busy} onClick={() => void runPublishDraft()}>
                Publish draft
              </Button>
              <Button size="sm" variant="secondary" disabled={busy || row.status === "ARCHIVED"} onClick={() => void runArchive()}>
                Archive
              </Button>
            </div>
          ) : null
        }
      />

      {error ? (
        <ErrorState className="mb-4" message={error} onRetry={() => void load()} />
      ) : null}

      {!row ? (
        <LoadingSkeleton rows={6} />
      ) : (
        <div className="mx-auto grid max-w-4xl gap-6 lg:grid-cols-[1fr_220px]">
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <StatusPill status={row.status.toLowerCase()} />
              <span className="text-sm text-text-muted">{row.channel}</span>
            </div>

            {row.channel === "EMAIL" ? (
              <label className="block space-y-1">
                <span className="text-xs font-medium text-text-muted">Subject</span>
                <Textarea
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  rows={2}
                  className="font-mono text-sm"
                />
              </label>
            ) : null}

            <label className="block space-y-1">
              <span className="text-xs font-medium text-text-muted">
                Body
                {row.channel === "SMS" ? ` · ${smsLen} chars` : ""}
              </span>
              <Textarea
                value={body}
                onChange={(e) => setBody(e.target.value)}
                rows={10}
                className="font-mono text-sm"
              />
            </label>

            {validationErrors.length > 0 ? (
              <ul className="space-y-1 rounded-md border border-danger/40 bg-danger/5 p-3 text-sm text-danger">
                {validationErrors.map((err) => (
                  <li key={err}>{err}</li>
                ))}
              </ul>
            ) : null}

            {preview !== null ? (
              <section className="space-y-2 border-t border-border pt-4">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                  Preview (not sent)
                </h3>
                {previewSubject ? (
                  <p className="text-sm font-medium">{previewSubject}</p>
                ) : null}
                <p className="whitespace-pre-wrap text-sm text-text-primary">{preview}</p>
              </section>
            ) : null}
          </div>

          <aside className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Variables
            </h3>
            <p className="text-xs text-text-secondary">
              Only variables valid for this template key. Backend rejects unknown paths.
            </p>
            <ul className="max-h-96 space-y-1 overflow-y-auto text-sm">
              {variables.map((v) => (
                <li key={v}>
                  <button
                    type="button"
                    className="w-full rounded px-2 py-1 text-left font-mono text-xs hover:bg-surface-muted"
                    onClick={() => insertVariable(v)}
                  >
                    {`{{${v}}}`}
                  </button>
                </li>
              ))}
            </ul>
          </aside>
        </div>
      )}
    </AppShell>
  );
}

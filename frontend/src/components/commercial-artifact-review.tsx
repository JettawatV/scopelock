import { Check, Eye, FileText, Mail, Send, ShieldCheck, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  humanize,
  money,
  StatusPill,
  time,
} from "@/components/dashboard-primitives";
import { correlationId } from "@/lib/api";
import type { Artifact, InboxMessage, Project } from "@/lib/types";

type ArtifactReviewProps = {
  artifact: Artifact;
  project?: Project;
  inboxMessages: InboxMessage[];
  demo: boolean;
  compact?: boolean;
  operatorId: string;
  setOperatorId: (value: string) => void;
  busy: boolean;
  onCommand: (path: string, payload: Record<string, string>) => Promise<void>;
};

type PreviewTab = "proposal" | "email";

function emailPreview(artifact: Artifact, project?: Project) {
  const title = project?.title?.trim() || "your project";
  const greeting = project?.client_name?.trim()
    ? `Hello ${project.client_name.trim()},`
    : "Hello,";
  const isChangeOrder = artifact.artifact_type === "CHANGE_ORDER";
  const opening = isChangeOrder
    ? `Following up on the additional requirements for ${title}, I have attached Change Order #${artifact.change_order_number || artifact.version_number} for your review.`
    : `Following up on our conversation about ${title}, I have attached the proposal for your review.`;
  const includedWork = artifact.pricing_result.line_items
    .slice(0, 5)
    .map((item) => item.module_key.replace(/_/g, " "))
    .join(", ");

  return [
    greeting,
    "",
    opening,
    "",
    "Summary:",
    `• Investment: USD ${artifact.pricing_result.total_usd.toLocaleString("en-US")}`,
    `• Delivery: ${artifact.timeline_result.total_days} business days`,
    ...(includedWork ? [`• Included work: ${includedWork}`] : []),
    "",
    "Please reply to confirm that this scope works for you, or let me know if you would like to discuss any detail. Once confirmed, we will schedule the next steps.",
    "",
    "Best regards,",
    "JVL Team",
  ].join("\n");
}

function ArtifactPreviewModal({
  artifact,
  project,
  open,
  initialTab,
  onClose,
}: {
  artifact: Artifact;
  project?: Project;
  open: boolean;
  initialTab: PreviewTab;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<PreviewTab>(initialTab);

  useEffect(() => {
    if (!open) return;
    setTab(initialTab);
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [initialTab, onClose, open]);

  if (!open) return null;

  return (
    <div
      className="preview-modal-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        className="preview-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={`preview-title-${artifact.id}`}
      >
        <div className="flex items-start justify-between gap-4 border-b border-[var(--line)] px-5 py-4 sm:px-6">
          <div>
            <p className="eyebrow">Review packet</p>
            <h2 id={`preview-title-${artifact.id}`} className="mt-1 text-xl font-black tracking-[-0.03em]">
              Proposal and email draft
            </h2>
            <p className="mt-1 text-xs text-[var(--muted)]">
              Check the client-facing details before creating or sending a Gmail draft.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid size-11 shrink-0 place-items-center rounded-lg text-[var(--muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--ink)]"
            aria-label="Close review packet"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        <div className="flex gap-1 border-b border-[var(--line)] px-5 pt-3 sm:px-6">
          {([
            ["proposal", "Proposal preview", FileText],
            ["email", "Email draft", Mail],
          ] as const).map(([key, label, Icon]) => (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              aria-selected={tab === key}
              role="tab"
              className={`preview-modal-tab ${tab === key ? "is-active" : ""}`}
            >
              <Icon size={15} aria-hidden="true" /> {label}
            </button>
          ))}
        </div>

        <div className="preview-modal-body">
          {tab === "proposal" ? (
            <div className="grid gap-5">
              <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-[10px] font-extrabold uppercase tracking-[0.12em] text-[var(--muted)]">{humanize(artifact.artifact_type)} · Version {artifact.version_number}</p>
                    <h3 className="mt-2 text-xl font-black tracking-[-0.03em]">{project?.title ?? "Commercial proposal"}</h3>
                    <p className="mt-1 text-sm text-[var(--muted)]">Prepared for {project?.client_name ?? "client review"}</p>
                  </div>
                  <StatusPill status={artifact.status} />
                </div>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-xl border border-[var(--line)] bg-white p-4">
                  <p className="text-[10px] font-extrabold uppercase tracking-[0.12em] text-[var(--muted)]">Total investment</p>
                  <p className="tabular mt-2 text-2xl font-black">{money(artifact.pricing_result.total_usd)}</p>
                  <p className="mt-1 text-xs text-[var(--muted)]">Calculated from {artifact.sop_version}</p>
                </div>
                <div className="rounded-xl border border-[var(--line)] bg-white p-4">
                  <p className="text-[10px] font-extrabold uppercase tracking-[0.12em] text-[var(--muted)]">Delivery timeline</p>
                  <p className="tabular mt-2 text-2xl font-black">{artifact.timeline_result.total_days} business days</p>
                  <p className="mt-1 text-xs text-[var(--muted)]">Scope and timeline remain approval-gated</p>
                </div>
              </div>
              <div>
                <div className="flex items-center justify-between gap-3">
                  <p className="eyebrow">Included work</p>
                  <span className="text-xs font-bold text-[var(--muted)]">{artifact.pricing_result.line_items.length} line items</span>
                </div>
                <div className="mt-3 divide-y divide-[var(--line)] overflow-hidden rounded-xl border border-[var(--line)] bg-white">
                  {artifact.pricing_result.line_items.map((line) => (
                    <div key={line.module_key} className="flex items-center justify-between gap-4 px-4 py-3">
                      <div>
                        <p className="text-sm font-extrabold">{humanize(line.module_key)}</p>
                        <p className="mt-0.5 text-xs text-[var(--muted)]">Qty {line.quantity} · {humanize(line.unit_rule)}</p>
                      </div>
                      <p className="tabular shrink-0 text-sm font-black">{money(line.subtotal_usd)}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="grid gap-4">
              <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-[10px] font-extrabold uppercase tracking-[0.12em] text-[var(--muted)]">Reply in the existing Gmail thread</p>
                    <p className="mt-1 text-sm font-black">{project?.client_name ?? "Client"} · {project?.client_email ?? "Client email"}</p>
                  </div>
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--line)] bg-white px-2.5 py-1 text-[10px] font-extrabold text-[var(--muted-strong)]"><Mail size={13} /> Attachment included</span>
                </div>
              </div>
              <pre className="preview-email-body">{emailPreview(artifact, project)}</pre>
              <p className="flex items-start gap-2 text-xs leading-5 text-[var(--muted)]"><ShieldCheck size={15} className="mt-0.5 shrink-0 text-[var(--ink)]" /> The draft is prepared for review only. Sending remains a separate, explicit approval-gated action.</p>
            </div>
          )}
        </div>
        <div className="flex items-center justify-end border-t border-[var(--line)] px-5 py-4 sm:px-6">
          <button type="button" onClick={onClose} className="min-h-11 rounded-lg bg-[var(--ink)] px-4 text-sm font-extrabold text-white hover:bg-[var(--ink-strong)]">Close preview</button>
        </div>
      </section>
    </div>
  );
}

export function ArtifactReview({
  artifact,
  project,
  inboxMessages,
  demo,
  compact = false,
  operatorId,
  setOperatorId,
  busy,
  onCommand,
}: ArtifactReviewProps) {
  const [sendConfirm, setSendConfirm] = useState(false);
  const [revisionReason, setRevisionReason] = useState("");
  const [acceptanceRecordId, setAcceptanceRecordId] = useState("");
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewTab, setPreviewTab] = useState<PreviewTab>("proposal");
  const stale = Boolean(
    project?.active_proposal_id && project.active_proposal_id !== artifact.id,
  );
  const canDecide = artifact.status === "AWAITING_USER_REVIEW" && !stale;
  const canSend = artifact.status === "APPROVED" && !stale;
  const canAccept = artifact.status === "SENT" && !stale;
  const acceptanceCandidates = useMemo(
    () =>
      inboxMessages
        .filter(
          (message) =>
            message.project_id === artifact.project_id &&
            message.direction === "INBOUND" &&
            message.sender_email.toLowerCase() ===
              project?.client_email.toLowerCase() &&
            new Date(message.received_at) > new Date(artifact.created_at),
        )
        .sort(
          (left, right) =>
            new Date(right.received_at).getTime() -
            new Date(left.received_at).getTime(),
        ),
    [artifact.created_at, artifact.project_id, inboxMessages, project?.client_email],
  );
  const selectedAcceptanceId =
    acceptanceRecordId || acceptanceCandidates[0]?.id || "";

  if (compact) {
    return (
      <CompactArtifactReview
        artifact={artifact}
        project={project}
        demo={demo}
        operatorId={operatorId}
        setOperatorId={setOperatorId}
        busy={busy}
        onCommand={onCommand}
        stale={stale}
        canDecide={canDecide}
        canSend={canSend}
        canAccept={canAccept}
        sendConfirm={sendConfirm}
        setSendConfirm={setSendConfirm}
        acceptanceCandidates={acceptanceCandidates}
        selectedAcceptanceId={selectedAcceptanceId}
        setAcceptanceRecordId={setAcceptanceRecordId}
        previewOpen={previewOpen}
        previewTab={previewTab}
        setPreviewOpen={setPreviewOpen}
        setPreviewTab={setPreviewTab}
      />
    );
  }

  return (
    <article
      id={`artifact-${artifact.id}`}
      className="panel scroll-mt-6 overflow-hidden"
    >
      <div className="flex flex-col gap-5 border-b border-[var(--line)] p-6 sm:flex-row sm:items-start sm:justify-between sm:p-8">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill status={artifact.status} />
            <span className="text-xs font-bold text-[var(--muted)]">
              {humanize(artifact.artifact_type)} v{artifact.version_number}
            </span>
          </div>
          <h2 className="mt-4 text-balance text-2xl font-black tracking-[-0.035em] sm:text-3xl">
            {project?.title ?? "Commercial artifact awaiting review"}
          </h2>
          <p className="mt-2 text-sm text-[var(--muted)]">
            {project
              ? `${project.client_name} · ${project.client_email}`
              : artifact.project_id}
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <button type="button" onClick={() => { setPreviewTab("proposal"); setPreviewOpen(true); }} className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-[var(--line-dark)] bg-white px-3 text-xs font-extrabold hover:bg-[var(--surface-muted)]"><Eye size={15} /> Preview proposal</button>
            <button type="button" onClick={() => { setPreviewTab("email"); setPreviewOpen(true); }} className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-[var(--line)] bg-white px-3 text-xs font-extrabold text-[var(--muted-strong)] hover:bg-[var(--surface-muted)]"><Mail size={15} /> View email draft</button>
          </div>
        </div>
        <div className="grid min-w-44 grid-cols-2 gap-4 rounded-lg bg-[var(--surface-muted)] p-4 sm:text-right">
          <div>
            <p className="text-[10px] font-extrabold uppercase tracking-[0.1em] text-[var(--muted)]">
              Price
            </p>
            <p className="tabular mt-1 text-xl font-black text-[var(--ink)]">
              {money(artifact.pricing_result.total_usd)}
            </p>
          </div>
          <div>
            <p className="text-[10px] font-extrabold uppercase tracking-[0.1em] text-[var(--muted)]">
              Timeline
            </p>
            <p className="tabular mt-1 text-xl font-black">
              {artifact.timeline_result.total_days}d
            </p>
          </div>
        </div>
      </div>

      {stale ? (
        <div
          role="status"
          className="border-b border-[var(--line-strong)] bg-[var(--surface-soft)] px-6 py-3 text-sm font-bold text-[var(--ink)] sm:px-8"
        >
          Historical artifact - review actions are disabled because a newer active
          artifact exists.
        </div>
      ) : null}

      <div className="grid gap-7 p-6 sm:p-8 lg:grid-cols-[1.15fr_0.85fr]">
        <div>
          <p className="eyebrow">Deterministic line items</p>
          <div className="mt-4 overflow-hidden rounded-lg border border-[var(--line)]">
            {artifact.pricing_result.line_items.length ? (
              artifact.pricing_result.line_items.map((line) => (
                <div
                  key={line.module_key}
                  className="grid grid-cols-[1fr_auto] gap-4 border-b border-[var(--line)] px-4 py-3 last:border-b-0"
                >
                  <div>
                    <p className="text-sm font-extrabold">
                      {humanize(line.module_key)}
                    </p>
                    <p className="mt-0.5 text-xs text-[var(--muted)]">
                      Qty {line.quantity} · {humanize(line.unit_rule)} ·{" "}
                      {artifact.sop_version}
                    </p>
                  </div>
                  <p className="tabular self-center text-sm font-black">
                    {money(line.subtotal_usd)}
                  </p>
                </div>
              ))
            ) : (
              <p className="px-4 py-5 text-sm text-[var(--muted)]">
                Line-item details are not present in this fixture.
              </p>
            )}
          </div>
          <p className="mt-4 flex items-center gap-2 text-xs font-bold text-[var(--muted)]">
            <ShieldCheck size={15} className="text-[var(--ink)]" />
            Gemini selected modules; application code calculated every amount.
          </p>
        </div>

        <div className="rounded-lg border border-[var(--line)] bg-[var(--surface-soft)] p-5">
          <p className="eyebrow">Human approval gate</p>
          <label
            htmlFor={`operator-${artifact.id}`}
            className="mt-4 block text-xs font-extrabold"
          >
            Approver identity
          </label>
          <input
            id={`operator-${artifact.id}`}
            type="email"
            value={operatorId}
            onChange={(event) => setOperatorId(event.target.value)}
            disabled={demo}
            placeholder="you@example.com"
            className="mt-2 min-h-11 w-full rounded-lg border border-[var(--line-strong)] bg-white px-3 text-sm disabled:bg-[var(--surface-muted)]"
          />

          {canDecide ? (
            <div className="mt-4 grid grid-cols-2 gap-2">
              <button
                type="button"
                disabled={busy || demo || !operatorId}
                onClick={() =>
                  onCommand(`/artifacts/${artifact.id}/approve`, {
                    approver_id: operatorId,
                    correlation_id: correlationId(),
                  })
                }
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-[var(--ink)] px-3 text-sm font-extrabold text-white hover:bg-[var(--ink-strong)] disabled:opacity-45"
              >
                <Check size={16} /> Approve
              </button>
              <button
                type="button"
                disabled={busy || demo || !operatorId}
                onClick={() =>
                  onCommand(`/artifacts/${artifact.id}/reject`, {
                    approver_id: operatorId,
                    correlation_id: correlationId(),
                  })
                }
                className="min-h-11 rounded-lg border border-[var(--line-dark)] bg-white px-3 text-sm font-extrabold text-[var(--ink)] hover:bg-[var(--surface-muted)] disabled:opacity-45"
              >
                Reject
              </button>
            </div>
          ) : null}

          {canDecide ? (
            <div className="mt-4 border-t border-[var(--line)] pt-4">
              <label
                htmlFor={`revision-${artifact.id}`}
                className="text-xs font-extrabold"
              >
                Revision note
              </label>
              <textarea
                id={`revision-${artifact.id}`}
                rows={2}
                value={revisionReason}
                onChange={(event) => setRevisionReason(event.target.value)}
                disabled={demo}
                className="mt-2 w-full rounded-lg border border-[var(--line-strong)] bg-white px-3 py-2 text-sm disabled:bg-[var(--surface-muted)]"
                placeholder="What needs to change?"
              />
              <button
                type="button"
                disabled={busy || demo || !operatorId || !revisionReason.trim()}
                onClick={() =>
                  onCommand(`/artifacts/${artifact.id}/revise`, {
                    operator_id: operatorId,
                    correlation_id: correlationId(),
                    reason: revisionReason.trim(),
                  })
                }
                className="mt-2 min-h-11 w-full rounded-lg border border-[var(--line-strong)] bg-white px-3 text-xs font-extrabold hover:bg-[var(--surface-muted)] disabled:opacity-45"
              >
                Return for revision
              </button>
            </div>
          ) : null}

          {canSend ? (
            <div className="mt-4 grid gap-2">
              <button
                type="button"
                disabled={busy || demo}
                onClick={() =>
                  onCommand(`/artifacts/${artifact.id}/draft`, {
                    correlation_id: correlationId(),
                  })
                }
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-[var(--line-dark)] bg-white px-3 text-sm font-extrabold text-[var(--ink)] hover:bg-[var(--surface-muted)] disabled:opacity-45"
              >
                <Mail size={16} /> Create Gmail draft
              </button>
              {!sendConfirm ? (
                <button
                  type="button"
                  disabled={busy || demo}
                  onClick={() => setSendConfirm(true)}
                  className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-[var(--ink)] px-3 text-sm font-extrabold text-white hover:bg-[var(--ink-strong)] disabled:opacity-45"
                >
                  <Send size={16} /> Send approved email
                </button>
              ) : (
                <div className="rounded-lg border border-[var(--line-strong)] bg-[var(--surface-soft)] p-3">
                  <p className="text-xs font-bold leading-5 text-[var(--ink)]">
                    This sends the approved artifact in the client&apos;s Gmail
                    thread.
                  </p>
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => setSendConfirm(false)}
                      className="min-h-11 rounded-lg border border-[var(--line-dark)] bg-white text-xs font-extrabold"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() =>
                        onCommand(`/artifacts/${artifact.id}/send`, {
                          correlation_id: correlationId(),
                        })
                      }
                      className="min-h-11 rounded-lg bg-[var(--ink)] text-xs font-extrabold text-white disabled:opacity-45"
                    >
                      Confirm send
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : null}

          {canAccept ? (
            <div className="mt-4 border-t border-[var(--line)] pt-4">
              <p className="text-xs font-extrabold">Confirm client acceptance</p>
              <p className="mt-2 text-xs leading-5 text-[var(--muted)]">
                Select the persisted client reply that explicitly accepts this
                commercial artifact. ScopeLock validates the sender and Gmail
                thread on the server.
              </p>
              {acceptanceCandidates.length ? (
                <>
                  <label
                    htmlFor={`acceptance-${artifact.id}`}
                    className="sr-only"
                  >
                    Client acceptance email
                  </label>
                  <select
                    id={`acceptance-${artifact.id}`}
                    value={selectedAcceptanceId}
                    onChange={(event) => setAcceptanceRecordId(event.target.value)}
                    disabled={busy || demo}
                    className="mt-3 min-h-11 w-full rounded-lg border border-[var(--line-strong)] bg-white px-3 text-sm disabled:bg-[var(--surface-muted)]"
                  >
                    {acceptanceCandidates.map((message) => (
                      <option key={message.id} value={message.id}>
                        {message.subject || "No subject"} - {time(message.received_at)}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    disabled={busy || demo || !selectedAcceptanceId}
                    onClick={() =>
                      onCommand(`/artifacts/${artifact.id}/accept`, {
                        source_inbound_message_id: selectedAcceptanceId,
                        correlation_id: correlationId(),
                      })
                    }
                    className="mt-2 min-h-11 w-full rounded-lg border border-[var(--line-dark)] bg-white px-3 text-xs font-extrabold hover:bg-[var(--surface-muted)] disabled:opacity-45"
                  >
                    Mark client accepted
                  </button>
                </>
              ) : (
                <p className="mt-3 rounded-lg bg-white px-3 py-2 text-xs font-bold text-[var(--muted)]">
                  Waiting for a later inbound reply from this client.
                </p>
              )}
            </div>
          ) : null}

          {demo ? (
            <p className="mt-4 rounded-lg bg-[var(--surface-soft)] px-3 py-2 text-xs font-bold text-[var(--ink)]">
              Demo fixture: all external actions are disabled.
            </p>
          ) : null}
        </div>
      </div>
      <ArtifactPreviewModal artifact={artifact} project={project} open={previewOpen} initialTab={previewTab} onClose={() => setPreviewOpen(false)} />
    </article>
  );
}

function CompactArtifactReview({
  artifact,
  project,
  demo,
  operatorId,
  setOperatorId,
  busy,
  onCommand,
  stale,
  canDecide,
  canSend,
  canAccept,
  sendConfirm,
  setSendConfirm,
  acceptanceCandidates,
  selectedAcceptanceId,
  setAcceptanceRecordId,
  previewOpen,
  previewTab,
  setPreviewOpen,
  setPreviewTab,
}: {
  artifact: Artifact;
  project?: Project;
  demo: boolean;
  operatorId: string;
  setOperatorId: (value: string) => void;
  busy: boolean;
  onCommand: (path: string, payload: Record<string, string>) => Promise<void>;
  stale: boolean;
  canDecide: boolean;
  canSend: boolean;
  canAccept: boolean;
  sendConfirm: boolean;
  setSendConfirm: (value: boolean) => void;
  acceptanceCandidates: InboxMessage[];
  selectedAcceptanceId: string;
  setAcceptanceRecordId: (value: string) => void;
  previewOpen: boolean;
  previewTab: PreviewTab;
  setPreviewOpen: (value: boolean) => void;
  setPreviewTab: (value: PreviewTab) => void;
}) {
  return (
    <article id={`artifact-${artifact.id}`} className="panel overview-artifact-card scroll-mt-6 overflow-hidden">
      <div className="border-b border-[var(--line)] px-5 py-4 sm:px-6">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <StatusPill status={artifact.status} />
              <span className="text-[11px] font-bold text-[var(--muted)]">{humanize(artifact.artifact_type)} · v{artifact.version_number}</span>
            </div>
            <h2 className="mt-2 truncate text-lg font-bold tracking-[-0.025em]">{project?.title ?? "Commercial artifact"}</h2>
            <p className="mt-1 truncate text-xs text-[var(--muted)]">{project?.client_name ?? artifact.project_id}</p>
            <div className="mt-3">
              <button type="button" onClick={() => { setPreviewTab("proposal"); setPreviewOpen(true); }} className="inline-flex min-h-11 items-center gap-1.5 rounded-lg border border-[var(--line-strong)] bg-white px-3 text-xs font-bold hover:bg-[var(--surface-muted)]"><Eye size={14} /> Review packet</button>
            </div>
          </div>
          <div className="grid shrink-0 grid-cols-2 gap-4 text-right">
            <div>
              <p className="text-[9px] font-extrabold uppercase tracking-[0.1em] text-[var(--muted)]">Price</p>
              <p className="tabular mt-1 text-lg font-black">{money(artifact.pricing_result.total_usd)}</p>
            </div>
            <div>
              <p className="text-[9px] font-extrabold uppercase tracking-[0.1em] text-[var(--muted)]">Timeline</p>
              <p className="tabular mt-1 text-lg font-black">{artifact.timeline_result.total_days}d</p>
            </div>
          </div>
        </div>
        {stale ? <p className="mt-3 rounded-lg bg-[var(--surface-soft)] px-3 py-2 text-xs font-bold text-[var(--muted)]">Historical artifact — newer active version exists.</p> : null}
      </div>

      <div className="grid gap-4 px-5 py-4 sm:px-6 lg:grid-cols-[1fr_0.9fr]">
        <div className="min-w-0">
          <div className="flex items-center justify-between gap-3">
            <p className="eyebrow">Calculated scope</p>
            <span className="inline-flex items-center gap-1 text-[10px] font-bold text-[var(--muted)]"><ShieldCheck size={13} /> SOP locked</span>
          </div>
          <div className="mt-3 divide-y divide-[var(--line)] overflow-hidden rounded-lg border border-[var(--line)]">
            {artifact.pricing_result.line_items.slice(0, 2).map((line) => (
              <div key={line.module_key} className="flex items-center justify-between gap-3 px-3 py-2.5">
                <div className="min-w-0">
                  <p className="truncate text-xs font-bold">{humanize(line.module_key)}</p>
                  <p className="mt-0.5 text-[10px] text-[var(--muted)]">Qty {line.quantity} · {humanize(line.unit_rule)}</p>
                </div>
                <p className="tabular shrink-0 text-xs font-black">{money(line.subtotal_usd)}</p>
              </div>
            ))}
          </div>
          {artifact.pricing_result.line_items.length > 2 ? <p className="mt-2 text-[10px] font-bold text-[var(--muted)]">+{artifact.pricing_result.line_items.length - 2} more in the preview</p> : null}
        </div>

        <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-4">
          <p className="eyebrow">Approval</p>
          <label htmlFor={`compact-operator-${artifact.id}`} className="mt-3 block text-[11px] font-extrabold">Approver identity</label>
          <input id={`compact-operator-${artifact.id}`} type="email" value={operatorId} onChange={(event) => setOperatorId(event.target.value)} disabled={demo} placeholder="you@example.com" className="mt-1.5 min-h-11 w-full rounded-lg border border-[var(--line-strong)] bg-white px-3 text-sm disabled:bg-[var(--surface-muted)]" />

          {canDecide ? (
            <div className="mt-3 grid grid-cols-2 gap-2">
              <button type="button" disabled={busy || demo || !operatorId} onClick={() => onCommand(`/artifacts/${artifact.id}/approve`, { approver_id: operatorId, correlation_id: correlationId() })} className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-lg bg-[var(--ink)] px-3 text-xs font-extrabold text-white hover:bg-[var(--ink-strong)] disabled:opacity-45"><Check size={14} /> Approve</button>
              <button type="button" disabled={busy || demo || !operatorId} onClick={() => onCommand(`/artifacts/${artifact.id}/reject`, { approver_id: operatorId, correlation_id: correlationId() })} className="min-h-11 rounded-lg border border-[var(--line-dark)] bg-white px-3 text-xs font-extrabold hover:bg-[var(--surface-muted)] disabled:opacity-45">Reject</button>
            </div>
          ) : null}

          {canSend ? (
            <div className="mt-3 grid gap-2">
              <button type="button" disabled={busy || demo} onClick={() => onCommand(`/artifacts/${artifact.id}/draft`, { correlation_id: correlationId() })} className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-lg border border-[var(--line-dark)] bg-white px-3 text-xs font-extrabold hover:bg-[var(--surface-muted)] disabled:opacity-45"><Mail size={14} /> Create draft</button>
              {!sendConfirm ? <button type="button" disabled={busy || demo} onClick={() => setSendConfirm(true)} className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-lg bg-[var(--ink)] px-3 text-xs font-extrabold text-white hover:bg-[var(--ink-strong)] disabled:opacity-45"><Send size={14} /> Send approved email</button> : <div className="rounded-lg border border-[var(--line-strong)] bg-white p-3"><p className="text-[11px] font-bold leading-4">Send this approved artifact in the client thread?</p><div className="mt-2 grid grid-cols-2 gap-2"><button type="button" onClick={() => setSendConfirm(false)} className="min-h-11 rounded-lg border border-[var(--line)] text-[11px] font-extrabold">Cancel</button><button type="button" disabled={busy} onClick={() => onCommand(`/artifacts/${artifact.id}/send`, { correlation_id: correlationId() })} className="min-h-11 rounded-lg bg-[var(--ink)] text-[11px] font-extrabold text-white disabled:opacity-45">Confirm</button></div></div>}
            </div>
          ) : null}

          {canAccept ? (
            <div className="mt-3 border-t border-[var(--line)] pt-3">
              <p className="text-[11px] font-extrabold">Confirm client acceptance</p>
              {acceptanceCandidates.length ? <><label htmlFor={`compact-acceptance-${artifact.id}`} className="sr-only">Client acceptance email</label><select id={`compact-acceptance-${artifact.id}`} value={selectedAcceptanceId} onChange={(event) => setAcceptanceRecordId(event.target.value)} disabled={busy || demo} className="mt-2 min-h-10 w-full rounded-lg border border-[var(--line-strong)] bg-white px-2 text-xs disabled:bg-[var(--surface-muted)]">{acceptanceCandidates.map((message) => <option key={message.id} value={message.id}>{message.subject || "No subject"} · {time(message.received_at)}</option>)}</select><button type="button" disabled={busy || demo || !selectedAcceptanceId} onClick={() => onCommand(`/artifacts/${artifact.id}/accept`, { source_inbound_message_id: selectedAcceptanceId, correlation_id: correlationId() })} className="mt-2 min-h-10 w-full rounded-lg border border-[var(--line-dark)] bg-white px-3 text-[11px] font-extrabold hover:bg-[var(--surface-muted)] disabled:opacity-45">Mark client accepted</button></> : <p className="mt-2 rounded-lg bg-white px-3 py-2 text-[10px] font-bold text-[var(--muted)]">Waiting for a later inbound reply.</p>}
            </div>
          ) : null}
        </div>
      </div>
      <ArtifactPreviewModal artifact={artifact} project={project} open={previewOpen} initialTab={previewTab} onClose={() => setPreviewOpen(false)} />
    </article>
  );
}

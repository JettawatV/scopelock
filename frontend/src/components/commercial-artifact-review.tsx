import { Check, Mail, Send, ShieldCheck } from "lucide-react";
import { useMemo, useState } from "react";

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
  operatorId: string;
  setOperatorId: (value: string) => void;
  busy: boolean;
  onCommand: (path: string, payload: Record<string, string>) => Promise<void>;
};

export function ArtifactReview({
  artifact,
  project,
  inboxMessages,
  demo,
  operatorId,
  setOperatorId,
  busy,
  onCommand,
}: ArtifactReviewProps) {
  const [sendConfirm, setSendConfirm] = useState(false);
  const [revisionReason, setRevisionReason] = useState("");
  const [acceptanceRecordId, setAcceptanceRecordId] = useState("");
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
    </article>
  );
}

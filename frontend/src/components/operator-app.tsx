import {
  Activity,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  Clock3,
  FileCheck2,
  Inbox,
  KeyRound,
  LockKeyhole,
  LogOut,
  Mail,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { apiRequest, correlationId } from "@/lib/api";
import { demoDashboard, demoProjectDetails } from "@/lib/demo-data";
import type {
  AgentRun,
  Artifact,
  DashboardSnapshot,
  Project,
  ProjectDetailSnapshot,
  ScopeBuffer,
  ScopeEvent,
} from "@/lib/types";

type View = "overview" | "projects" | "evals";
type Health = "checking" | "online" | "offline";

const OPERATOR_ID_KEY = "scopelock.operatorId";
const REVIEW_STATUSES = new Set([
  "AWAITING_USER_REVIEW",
  "NEEDS_REVIEW",
  "SEND_FAILED",
]);

function money(value: number, signed = false) {
  const prefix = signed && value > 0 ? "+" : "";
  return `${prefix}${new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value)}`;
}

function time(value?: string | null) {
  if (!value) return "Pending";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function humanize(value: string) {
  return value.toLowerCase().replaceAll("_", " ");
}

function statusTone(status: string) {
  if (["PASS", "COMPLETED", "APPROVED", "ACCEPTED", "SENT"].includes(status)) {
    return "status-positive";
  }
  if (["FAILED", "SEND_FAILED", "NEEDS_REVIEW", "REJECTED"].includes(status)) {
    return "status-negative";
  }
  if (["AWAITING_USER_REVIEW", "READY_TO_FINALIZE", "BUFFERED"].includes(status)) {
    return "status-action";
  }
  return "status-neutral";
}

function StatusPill({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-extrabold uppercase tracking-[0.08em] ${statusTone(status)}`}
    >
      {humanize(status)}
    </span>
  );
}

function EmptyState({ children }: { children: string }) {
  return (
    <div className="rounded-lg border border-dashed border-[var(--line)] bg-[var(--surface-soft)] px-5 py-8 text-center text-sm text-[var(--muted)]">
      {children}
    </div>
  );
}

function AppHeader({
  view,
  health,
  connected,
  demo,
  onDisconnect,
}: {
  view: View;
  health: Health;
  connected: boolean;
  demo: boolean;
  onDisconnect: () => void;
}) {
  const navigation: Array<[View, string, string]> = [
    ["overview", "Overview", "/"],
    ["projects", "Projects", "/projects/"],
    ["evals", "Agent readiness", "/evals/"],
  ];
  return (
    <header className="operator-header border-b border-white/10 bg-[var(--ink)] text-white">
      <div className="mx-auto flex min-h-20 max-w-[1480px] flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-7 lg:px-10">
        <div className="flex w-full min-w-0 items-center justify-between gap-3 sm:contents">
          <a href="/" className="flex min-w-0 items-center gap-3 rounded-lg">
            <span className="brand-mark grid size-10 shrink-0 place-items-center rounded-lg bg-white text-[var(--ink)]">
              <LockKeyhole aria-hidden="true" size={20} strokeWidth={2.4} />
            </span>
            <span className="min-w-0">
              <span className="block text-lg font-black tracking-[-0.03em]">ScopeLock</span>
              <span className="block text-[10px] font-bold uppercase tracking-[0.18em] text-[var(--status-muted)]">
                Operator console
              </span>
            </span>
          </a>
          <div className="flex shrink-0 items-center gap-3 text-xs font-bold">
            <span
              className="inline-flex items-center gap-2 rounded-full border border-white/15 px-3 py-2 text-[var(--on-dark)]"
              aria-label={demo ? "Demo fixture" : health === "online" ? "Service online" : health}
            >
              <span
                className={`size-2 rounded-full ${
                  health === "online"
                    ? "bg-[var(--status-light)]"
                    : health === "offline"
                      ? "bg-[var(--status-dark)]"
                      : "bg-[var(--status-muted)]"
                }`}
              />
              {demo ? "Demo fixture" : health === "online" ? "Service online" : health}
            </span>
            {connected && !demo ? (
              <button
                type="button"
                onClick={onDisconnect}
                className="grid size-11 place-items-center rounded-lg text-[var(--status-muted)] hover:bg-white/8 hover:text-white"
                aria-label="Disconnect operator session"
                title="Disconnect"
              >
                <LogOut size={18} aria-hidden="true" />
              </button>
            ) : null}
          </div>
        </div>

        <nav aria-label="Primary" className="order-3 flex w-full gap-1 overflow-x-auto sm:order-none sm:w-auto">
          {navigation.map(([key, label, href]) => (
            <a
              key={key}
              href={href}
              aria-current={view === key ? "page" : undefined}
              className={`min-h-11 whitespace-nowrap rounded-lg px-4 py-3 text-sm font-bold transition-colors ${
                view === key
                  ? "bg-white text-[var(--ink)]"
                  : "text-[var(--status-muted)] hover:bg-white/8 hover:text-white"
              }`}
            >
              {label}
            </a>
          ))}
        </nav>

      </div>
    </header>
  );
}

function ConnectPanel({
  busy,
  error,
  onConnect,
}: {
  busy: boolean;
  error: string | null;
  onConnect: (key: string) => Promise<void>;
}) {
  const [value, setValue] = useState("");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    void onConnect(value.trim());
  };

  return (
    <main id="main-content" className="mx-auto grid min-h-[calc(100vh-81px)] max-w-[1180px] place-items-center px-4 py-12 sm:px-7">
      <section className="panel grid w-full overflow-hidden lg:grid-cols-[1.05fr_0.95fr]">
        <div className="onboarding-hero p-7 text-white sm:p-10 lg:p-14">
          <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-[var(--on-dark)]">
            Calculate instantly. Communicate deliberately.
          </p>
          <h1 className="mt-5 max-w-xl text-balance text-4xl font-black tracking-[-0.045em] sm:text-5xl">
            Keep every commercial decision under human control.
          </h1>
          <p className="mt-6 max-w-lg text-base leading-7 text-[var(--on-dark)]">
            Review Gemini&apos;s evidence, verify deterministic price and timeline,
            and approve an email only when the scope is correct.
          </p>
          <ul className="mt-10 grid gap-4 text-sm font-semibold text-[var(--on-dark)]">
            {[
              "Operator key stays in memory until this page is refreshed",
              "Raw email bodies and agent payloads are not exposed",
              "Approval and send remain separate actions",
            ].map((item) => (
              <li key={item} className="flex items-start gap-3">
                <CheckCircle2 className="mt-0.5 shrink-0 text-[var(--status-muted)]" size={18} />
                {item}
              </li>
            ))}
          </ul>
        </div>
        <div className="p-7 sm:p-10 lg:p-14">
          <span className="grid size-12 place-items-center rounded-lg bg-[var(--surface-muted)] text-[var(--ink)]">
            <KeyRound aria-hidden="true" size={22} />
          </span>
          <p className="eyebrow mt-8">Protected workspace</p>
          <h2 className="mt-2 text-2xl font-black tracking-[-0.035em]">Connect as operator</h2>
          <p className="mt-3 text-sm leading-6 text-[var(--muted)]">
            Cloud Run verifies your Google identity first. ScopeLock then verifies
            the dedicated operator key for business actions.
          </p>
          <form onSubmit={submit} className="mt-8">
            <label htmlFor="operator-key" className="text-sm font-extrabold">
              Operator API key
            </label>
            <input
              id="operator-key"
              type="password"
              autoComplete="off"
              required
              minLength={32}
              value={value}
              onChange={(event) => setValue(event.target.value)}
              aria-describedby="operator-key-help"
              className="mt-2 min-h-12 w-full rounded-lg border border-[var(--line-strong)] bg-white px-4 text-sm shadow-inner"
              placeholder="Paste the generated key"
            />
            <p id="operator-key-help" className="mt-2 text-xs leading-5 text-[var(--muted)]">
              Held in page memory—not in browser storage, a cookie, URL, build, or server log.
            </p>
            {error ? (
              <p role="alert" className="mt-4 flex gap-2 rounded-lg bg-[var(--surface-muted)] px-3 py-3 text-sm font-semibold text-[var(--ink)]">
                <CircleAlert className="mt-0.5 shrink-0" size={17} aria-hidden="true" />
                {error}
              </p>
            ) : null}
            <button
              type="submit"
              disabled={busy}
              className="mt-6 inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-lg bg-[var(--ink)] px-5 font-extrabold text-white hover:bg-[var(--ink-strong)] disabled:cursor-wait disabled:opacity-60"
            >
              {busy ? <RefreshCw className="animate-spin" size={17} /> : <ShieldCheck size={18} />}
              {busy ? "Verifying…" : "Open operator console"}
            </button>
          </form>
          <a
            href="/?demo=1"
            className="mt-6 inline-flex min-h-11 items-center gap-2 rounded-lg text-sm font-extrabold text-[var(--ink)] underline decoration-[var(--line-dark)] underline-offset-4"
          >
            View reviewed demo fixture <ArrowRight size={15} aria-hidden="true" />
          </a>
        </div>
      </section>
    </main>
  );
}

function MetricCard({
  label,
  value,
  detail,
  icon,
  accent = false,
}: {
  label: string;
  value: string;
  detail: string;
  icon: React.ReactNode;
  accent?: boolean;
}) {
  return (
    <article className={`panel p-5 sm:p-6 ${accent ? "border-[var(--line-strong)] bg-[var(--surface-soft)]" : ""}`}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-extrabold uppercase tracking-[0.11em] text-[var(--muted)]">{label}</p>
          <p className="tabular mt-3 text-3xl font-black tracking-[-0.045em]">{value}</p>
        </div>
        <span className="grid size-10 place-items-center rounded-lg bg-[var(--surface-muted)] text-[var(--ink)]">{icon}</span>
      </div>
      <p className="mt-4 text-xs font-semibold leading-5 text-[var(--muted)]">{detail}</p>
    </article>
  );
}

function ArtifactReview({
  artifact,
  project,
  demo,
  operatorId,
  setOperatorId,
  busy,
  onCommand,
}: {
  artifact: Artifact;
  project?: Project;
  demo: boolean;
  operatorId: string;
  setOperatorId: (value: string) => void;
  busy: boolean;
  onCommand: (path: string, payload: Record<string, string>) => Promise<void>;
}) {
  const [sendConfirm, setSendConfirm] = useState(false);
  const [revisionReason, setRevisionReason] = useState("");
  const stale = Boolean(
    project?.active_proposal_id && project.active_proposal_id !== artifact.id,
  );
  const canDecide = artifact.status === "AWAITING_USER_REVIEW" && !stale;
  const canSend = artifact.status === "APPROVED" && !stale;

  return (
    <article id={`artifact-${artifact.id}`} className="panel scroll-mt-6 overflow-hidden">
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
            {project ? `${project.client_name} · ${project.client_email}` : artifact.project_id}
          </p>
        </div>
        <div className="grid min-w-44 grid-cols-2 gap-4 rounded-lg bg-[var(--surface-muted)] p-4 sm:text-right">
          <div>
            <p className="text-[10px] font-extrabold uppercase tracking-[0.1em] text-[var(--muted)]">Price</p>
            <p className="tabular mt-1 text-xl font-black text-[var(--ink)]">{money(artifact.pricing_result.total_usd)}</p>
          </div>
          <div>
            <p className="text-[10px] font-extrabold uppercase tracking-[0.1em] text-[var(--muted)]">Timeline</p>
            <p className="tabular mt-1 text-xl font-black">{artifact.timeline_result.total_days}d</p>
          </div>
        </div>
      </div>

      {stale ? (
        <div role="status" className="border-b border-[var(--line-strong)] bg-[var(--surface-soft)] px-6 py-3 text-sm font-bold text-[var(--ink)] sm:px-8">
          Historical artifact—review actions are disabled because a newer active artifact exists.
        </div>
      ) : null}

      <div className="grid gap-7 p-6 sm:p-8 lg:grid-cols-[1.15fr_0.85fr]">
        <div>
          <p className="eyebrow">Deterministic line items</p>
          <div className="mt-4 overflow-hidden rounded-lg border border-[var(--line)]">
            {artifact.pricing_result.line_items.length ? (
              artifact.pricing_result.line_items.map((line) => (
                <div key={line.module_key} className="grid grid-cols-[1fr_auto] gap-4 border-b border-[var(--line)] px-4 py-3 last:border-b-0">
                  <div>
                    <p className="text-sm font-extrabold">{humanize(line.module_key)}</p>
                    <p className="mt-0.5 text-xs text-[var(--muted)]">
                      Qty {line.quantity} · {humanize(line.unit_rule)} · {artifact.sop_version}
                    </p>
                  </div>
                  <p className="tabular self-center text-sm font-black">{money(line.subtotal_usd)}</p>
                </div>
              ))
            ) : (
              <p className="px-4 py-5 text-sm text-[var(--muted)]">Line-item details are not present in this fixture.</p>
            )}
          </div>
          <p className="mt-4 flex items-center gap-2 text-xs font-bold text-[var(--muted)]">
            <ShieldCheck size={15} className="text-[var(--ink)]" />
            Gemini selected modules; application code calculated every amount.
          </p>
        </div>

        <div className="rounded-lg border border-[var(--line)] bg-[var(--surface-soft)] p-5">
          <p className="eyebrow">Human approval gate</p>
          <label htmlFor={`operator-${artifact.id}`} className="mt-4 block text-xs font-extrabold">
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
                onClick={() => onCommand(`/artifacts/${artifact.id}/approve`, { approver_id: operatorId, correlation_id: correlationId() })}
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-[var(--ink)] px-3 text-sm font-extrabold text-white hover:bg-[var(--ink-strong)] disabled:opacity-45"
              >
                <Check size={16} /> Approve
              </button>
              <button
                type="button"
                disabled={busy || demo || !operatorId}
                onClick={() => onCommand(`/artifacts/${artifact.id}/reject`, { approver_id: operatorId, correlation_id: correlationId() })}
                className="min-h-11 rounded-lg border border-[var(--line-dark)] bg-white px-3 text-sm font-extrabold text-[var(--ink)] hover:bg-[var(--surface-muted)] disabled:opacity-45"
              >
                Reject
              </button>
            </div>
          ) : null}

          {canDecide ? (
            <div className="mt-4 border-t border-[var(--line)] pt-4">
              <label htmlFor={`revision-${artifact.id}`} className="text-xs font-extrabold">Revision note</label>
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
                onClick={() => onCommand(`/artifacts/${artifact.id}/revise`, { operator_id: operatorId, correlation_id: correlationId(), reason: revisionReason.trim() })}
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
                onClick={() => onCommand(`/artifacts/${artifact.id}/draft`, { correlation_id: correlationId() })}
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
                    This sends the approved artifact in the client&apos;s Gmail thread.
                  </p>
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    <button type="button" onClick={() => setSendConfirm(false)} className="min-h-11 rounded-lg border border-[var(--line-dark)] bg-white text-xs font-extrabold">
                      Cancel
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => onCommand(`/artifacts/${artifact.id}/send`, { correlation_id: correlationId() })}
                      className="min-h-11 rounded-lg bg-[var(--ink)] text-xs font-extrabold text-white disabled:opacity-45"
                    >
                      Confirm send
                    </button>
                  </div>
                </div>
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

function ScopeEventList({ events }: { events: ScopeEvent[] }) {
  if (!events.length) return <EmptyState>No scope events recorded yet.</EmptyState>;
  return (
    <div className="grid gap-3">
      {events.slice(0, 6).map((event) => (
        <article key={event.id} className="rounded-lg border border-[var(--line)] bg-white p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <StatusPill status={event.review_required ? "NEEDS_REVIEW" : event.classification} />
            <span className="tabular text-xs font-bold text-[var(--muted)]">{time(event.created_at)}</span>
          </div>
          <p className="mt-3 text-sm font-extrabold leading-6">{event.description}</p>
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs font-bold text-[var(--muted)]">
            <span className={event.price_delta_usd ? "text-[var(--ink)]" : ""}>{money(event.price_delta_usd, true)}</span>
            <span>{event.timeline_delta_days > 0 ? "+" : ""}{event.timeline_delta_days} days</span>
            <span>{event.evidence.length} evidence ref{event.evidence.length === 1 ? "" : "s"}</span>
          </div>
          {event.evidence[0] ? (
            <blockquote className="mt-3 border-l-2 border-[var(--line-dark)] pl-3 text-xs italic leading-5 text-[var(--muted)]">
              “{event.evidence[0].quote_or_rule}”
            </blockquote>
          ) : null}
        </article>
      ))}
    </div>
  );
}

function AgentActivity({ runs }: { runs: AgentRun[] }) {
  if (!runs.length) return <EmptyState>No hosted agent runs recorded yet.</EmptyState>;
  return (
    <div className="grid gap-3">
      {runs.slice(0, 5).map((run) => (
        <div key={run.id} className="flex min-w-0 items-center gap-3 rounded-lg border border-[var(--line)] bg-white p-4">
          <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-[var(--surface-muted)] text-[var(--ink)]">
            <Sparkles size={17} aria-hidden="true" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-extrabold">{humanize(run.agent_name)}</p>
            <p className="mt-1 truncate text-xs text-[var(--muted)]">{run.prompt_version} · {run.tool_count} tool records</p>
          </div>
          <div className="text-right">
            <StatusPill status={run.status} />
            <p className="mt-1 text-[10px] font-bold text-[var(--muted)]">{time(run.completed_at)}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

function BufferCard({
  buffer,
  demo,
  busy,
  onCommand,
}: {
  buffer: ScopeBuffer;
  demo: boolean;
  busy: boolean;
  onCommand: (path: string, payload: Record<string, string>) => Promise<void>;
}) {
  return (
    <article className="rounded-lg border border-[var(--line-strong)] bg-[var(--surface-soft)] p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <StatusPill status={buffer.status} />
        <span className="text-xs font-bold text-[var(--muted)]">{buffer.event_ids.length} buffered event{buffer.event_ids.length === 1 ? "" : "s"}</span>
      </div>
      <div className="mt-5 grid grid-cols-2 gap-4">
        <div>
          <p className="text-[10px] font-extrabold uppercase tracking-[0.1em] text-[var(--muted)]">Net price delta</p>
          <p className="tabular mt-1 text-2xl font-black text-[var(--ink)]">{money(buffer.net_price_delta_usd, true)}</p>
        </div>
        <div>
          <p className="text-[10px] font-extrabold uppercase tracking-[0.1em] text-[var(--muted)]">Timeline delta</p>
          <p className="tabular mt-1 text-2xl font-black">{buffer.net_timeline_delta_days > 0 ? "+" : ""}{buffer.net_timeline_delta_days}d</p>
        </div>
      </div>
      <p className="mt-4 text-xs leading-5 text-[var(--muted)]">Quiet window ends {time(buffer.quiet_window_expires_at)}. Finalizing prepares a reviewable revision; it does not send.</p>
      {buffer.status !== "FINALIZED" ? (
        <button
          type="button"
          disabled={busy || demo}
          onClick={() => onCommand(`/buffers/${buffer.id}/finalize`, { correlation_id: correlationId() })}
          className="mt-4 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-[var(--ink)] px-4 text-sm font-extrabold text-white hover:bg-[var(--ink)] disabled:opacity-45"
        >
          <FileCheck2 size={17} /> Finalize revision
        </button>
      ) : null}
    </article>
  );
}

function WorkspaceCommandCenter({
  artifact,
  actionCount,
  pendingDelta,
  demo,
  busy,
  onRefresh,
}: {
  artifact?: Artifact;
  actionCount: number;
  pendingDelta: number;
  demo: boolean;
  busy: boolean;
  onRefresh: () => void;
}) {
  const openArtifact = () => {
    if (!artifact) return;
    document.getElementById(`artifact-${artifact.id}`)?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  };

  return (
    <aside className="panel p-5 sm:p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="eyebrow">Command center</p>
          <h2 className="mt-1 text-xl font-black tracking-[-0.03em]">Decide the next move</h2>
        </div>
        <span className="grid size-10 place-items-center rounded-full bg-[var(--ink)] text-white"><CheckCircle2 size={19} /></span>
      </div>
      <dl className="mt-5 grid grid-cols-2 gap-3">
        <div className="rounded-lg border border-[var(--line)] bg-[var(--surface-soft)] p-3">
          <dt className="text-[10px] font-extrabold uppercase tracking-[0.1em] text-[var(--muted)]">Action required</dt>
          <dd className="tabular mt-1 text-2xl font-black">{actionCount}</dd>
        </div>
        <div className="rounded-lg border border-[var(--line)] bg-[var(--surface-soft)] p-3">
          <dt className="text-[10px] font-extrabold uppercase tracking-[0.1em] text-[var(--muted)]">Scope delta</dt>
          <dd className="tabular mt-1 text-lg font-black">{money(pendingDelta, true)}</dd>
        </div>
      </dl>
      <button
        type="button"
        disabled={!artifact}
        onClick={openArtifact}
        className="mt-5 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-[var(--ink)] px-4 text-sm font-extrabold text-white hover:bg-[var(--ink-strong)] disabled:opacity-45"
      >
        <FileCheck2 size={17} /> {artifact ? "Open full proposal" : "No proposal to review"}
      </button>
      <div className="mt-3 grid grid-cols-2 gap-3">
        <a href="/projects/" className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-[var(--line-strong)] bg-white px-3 text-center text-sm font-extrabold hover:bg-[var(--surface-soft)]"><Inbox size={16} /> Projects</a>
        <button type="button" disabled={busy || demo} onClick={onRefresh} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-[var(--line-strong)] bg-white px-3 text-sm font-extrabold hover:bg-[var(--surface-soft)] disabled:opacity-45"><RefreshCw className={busy ? "animate-spin" : ""} size={16} /> Refresh</button>
      </div>
      <a href="/evals/" className="mt-4 inline-flex items-center gap-1 text-xs font-extrabold text-[var(--muted)] underline underline-offset-4">Review agent evidence <ChevronRight size={14} /></a>
    </aside>
  );
}

function GmailReviewPanel({
  data,
  demo,
  busy,
  onCommand,
}: {
  data: DashboardSnapshot;
  demo: boolean;
  busy: boolean;
  onCommand: (path: string, payload: Record<string, string>) => Promise<void>;
}) {
  const [confirmWatch, setConfirmWatch] = useState(false);
  const projectsById = new Map(data.projects.map((project) => [project.id, project]));
  const watch = data.gmail_watch;

  const registerWatch = () => {
    setConfirmWatch(false);
    void onCommand("/gmail/watch", {});
  };

  return (
    <section className="panel flex min-h-[31rem] min-w-0 flex-col p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[var(--line)] pb-5">
        <div>
          <p className="eyebrow">Project-linked Gmail</p>
          <h2 className="mt-1 text-xl font-black tracking-[-0.03em]">Gmail review</h2>
          <p className="mt-2 text-xs leading-5 text-[var(--muted)]">Metadata only. ScopeLock shows messages linked to a project—never a full mailbox.</p>
        </div>
        {watch ? <StatusPill status="MONITORING" /> : <StatusPill status="NOT_CONNECTED" />}
      </div>

      {watch ? (
        <div className="mt-4 rounded-lg bg-[var(--surface-soft)] px-4 py-3 text-xs leading-5 text-[var(--muted)]">
          Monitoring <span className="font-extrabold text-[var(--ink)]">{watch.mailbox}</span> · watch expires {time(watch.expiration)}
        </div>
      ) : null}

      {data.inbox_messages.length ? (
        <div className="mt-4 min-h-0 flex-1 overflow-y-auto pr-1">
          <div className="grid gap-2">
            {data.inbox_messages.map((message) => {
              const project = projectsById.get(message.project_id);
              return (
                <article key={message.id} className="rounded-lg border border-[var(--line)] bg-white p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-extrabold">{message.subject || "No subject"}</p>
                      <p className="mt-1 truncate text-xs text-[var(--muted)]">{message.sender_name || message.sender_email || "Unknown sender"} · {project?.title ?? "Project"}</p>
                    </div>
                    <p className="shrink-0 text-[10px] font-bold text-[var(--muted)]">{time(message.received_at)}</p>
                  </div>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <StatusPill status={message.direction} />
                    {message.attachment_count ? <span className="text-[10px] font-bold text-[var(--muted)]">{message.attachment_count} attachment{message.attachment_count === 1 ? "" : "s"}</span> : null}
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      ) : (
        <div className="flex flex-1 flex-col items-center justify-center py-8 text-center">
          <span className="grid size-12 place-items-center rounded-full bg-[var(--surface-muted)] text-[var(--ink)]"><Mail size={21} /></span>
          <h3 className="mt-4 text-base font-black">{watch ? "Waiting for a project email" : "Gmail monitoring is not active"}</h3>
          <p className="mt-2 max-w-sm text-sm leading-6 text-[var(--muted)]">{watch ? "Project-linked messages will appear here after the Gmail event workflow records them." : "Register Gmail notifications only after the OAuth and Pub/Sub checks are complete."}</p>
          {!watch ? (
            <div className="mt-5 w-full max-w-sm">
              {confirmWatch ? (
                <div className="rounded-lg border border-[var(--line-strong)] bg-[var(--surface-soft)] p-4 text-left">
                  <p className="text-sm font-extrabold">Start Gmail notifications?</p>
                  <p className="mt-2 text-xs leading-5 text-[var(--muted)]">This registers Gmail <code>users.watch</code> for the configured dedicated mailbox. It does not send email, but it begins Pub/Sub delivery.</p>
                  <div className="mt-4 grid grid-cols-2 gap-3">
                    <button type="button" onClick={() => setConfirmWatch(false)} className="min-h-10 rounded-lg border border-[var(--line-strong)] bg-white px-3 text-sm font-extrabold">Cancel</button>
                    <button type="button" disabled={busy || demo} onClick={registerWatch} className="min-h-10 rounded-lg bg-[var(--ink)] px-3 text-sm font-extrabold text-white disabled:opacity-45">Confirm watch</button>
                  </div>
                </div>
              ) : (
                <button type="button" disabled={busy || demo} onClick={() => setConfirmWatch(true)} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-[var(--ink)] px-4 text-sm font-extrabold text-white disabled:opacity-45"><Mail size={17} /> {demo ? "Demo fixture" : "Connect Gmail"}</button>
              )}
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}

function Overview({
  data,
  demo,
  operatorId,
  setOperatorId,
  busy,
  onCommand,
  onRefresh,
}: {
  data: DashboardSnapshot;
  demo: boolean;
  operatorId: string;
  setOperatorId: (value: string) => void;
  busy: boolean;
  onCommand: (path: string, payload: Record<string, string>) => Promise<void>;
  onRefresh: () => void;
}) {
  const artifact = data.artifacts.find((item) => REVIEW_STATUSES.has(item.status)) ?? data.artifacts[0];
  const project = artifact ? data.projects.find((item) => item.id === artifact.project_id) : undefined;
  const actionCount = data.artifacts.filter((item) => REVIEW_STATUSES.has(item.status)).length + data.scope_buffers.filter((item) => item.status === "READY_TO_FINALIZE").length;
  const pendingDelta = data.scope_buffers.filter((item) => item.status !== "FINALIZED").reduce((sum, item) => sum + item.net_price_delta_usd, 0);

  return (
    <>
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Action required" value={String(actionCount)} detail="Review items and ready scope buffers" icon={<CircleAlert size={19} />} accent={actionCount > 0} />
        <MetricCard label="Monitored projects" value={String(data.projects.length)} detail="Gmail threads with application state" icon={<Inbox size={19} />} />
        <MetricCard label="Pending scope delta" value={money(pendingDelta, true)} detail="Calculated now; never sent automatically" icon={<Activity size={19} />} />
        <MetricCard label="Agent gate" value={data.readiness.status} detail={`${data.readiness.checks.reduce((sum, item) => sum + item.passed, 0)} reviewed checks passed`} icon={<ShieldCheck size={19} />} />
      </section>

      <section className="mt-6 grid min-w-0 gap-6 xl:grid-cols-[minmax(0,1fr)_390px]">
        <GmailReviewPanel data={data} demo={demo} busy={busy} onCommand={onCommand} />
        <WorkspaceCommandCenter artifact={artifact} actionCount={actionCount} pendingDelta={pendingDelta} demo={demo} busy={busy} onRefresh={onRefresh} />
      </section>

      <section className="mt-6">
        <div className="mb-4 flex items-end justify-between gap-4">
          <div>
            <p className="eyebrow">Priority queue</p>
            <h2 className="mt-1 text-xl font-black tracking-[-0.03em]">Commercial review</h2>
          </div>
          <a href="/projects/" className="inline-flex min-h-11 items-center gap-1 rounded-lg px-3 text-sm font-extrabold text-[var(--ink)]">All projects <ChevronRight size={16} /></a>
        </div>
        {artifact ? (
          <ArtifactReview artifact={artifact} project={project} demo={demo} operatorId={operatorId} setOperatorId={setOperatorId} busy={busy} onCommand={onCommand} />
        ) : (
          <EmptyState>No commercial artifact needs review.</EmptyState>
        )}
      </section>

      <section className="mt-6 grid min-w-0 gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
        <div className="panel min-w-0 p-5 sm:p-6">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <p className="eyebrow">Thread intelligence</p>
              <h2 className="mt-1 text-xl font-black tracking-[-0.03em]">Recent scope events</h2>
            </div>
            <Activity className="text-[var(--ink)]" size={20} />
          </div>
          <ScopeEventList events={data.scope_events} />
        </div>
        <div className="grid min-w-0 content-start gap-6">
          <div className="panel min-w-0 p-5 sm:p-6">
            <p className="eyebrow">Consolidation</p>
            <h2 className="mt-1 text-xl font-black tracking-[-0.03em]">Scope buffer</h2>
            <div className="mt-4">
              {data.scope_buffers[0] ? <BufferCard buffer={data.scope_buffers[0]} demo={demo} busy={busy} onCommand={onCommand} /> : <EmptyState>No scope change is waiting to be consolidated.</EmptyState>}
            </div>
          </div>
          <div className="panel min-w-0 p-5 sm:p-6">
            <p className="eyebrow">Observability</p>
            <h2 className="mt-1 text-xl font-black tracking-[-0.03em]">Recent agent activity</h2>
            <div className="mt-4"><AgentActivity runs={data.agent_runs} /></div>
          </div>
        </div>
      </section>
    </>
  );
}

function Projects({ data, demo, operatorKey, operatorId, setOperatorId, busy, onCommand }: {
  data: DashboardSnapshot;
  demo: boolean;
  operatorKey: string;
  operatorId: string;
  setOperatorId: (value: string) => void;
  busy: boolean;
  onCommand: (path: string, payload: Record<string, string>) => Promise<void>;
}) {
  const [selectedId, setSelectedId] = useState(data.projects[0]?.id ?? "");
  const [detail, setDetail] = useState<ProjectDetailSnapshot | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const project = data.projects.find((item) => item.id === selectedId) ?? data.projects[0];
  const artifacts = data.artifacts.filter((item) => item.project_id === project?.id);
  const events = data.scope_events.filter((item) => item.project_id === project?.id);
  const buffers = data.scope_buffers.filter((item) => item.project_id === project?.id);
  const effectiveDetail = demo ? demoProjectDetails[selectedId] ?? null : detail;
  const scope = effectiveDetail?.scope_versions.find(
    (item) => item.id === project?.active_scope_version_id,
  ) ?? effectiveDetail?.scope_versions[0];

  useEffect(() => {
    if (demo || !selectedId || !operatorKey) {
      setDetail(null);
      setDetailError(null);
      setDetailLoading(false);
      return;
    }
    let active = true;
    setDetail(null);
    setDetailError(null);
    setDetailLoading(true);
    apiRequest<ProjectDetailSnapshot>(`/api/projects/${encodeURIComponent(selectedId)}`, operatorKey)
      .then((result) => {
        if (active) {
          setDetail(result);
          setDetailLoading(false);
        }
      })
      .catch((caught) => {
        if (active) {
          setDetailLoading(false);
          setDetailError(
            caught instanceof Error ? caught.message : "Project scope could not be loaded.",
          );
        }
      });
    return () => {
      active = false;
    };
  }, [demo, operatorKey, selectedId]);

  if (!project) return <EmptyState>No projects have been created yet.</EmptyState>;
  return (
    <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
      <aside className="panel h-fit p-3">
        <p className="px-3 pb-2 pt-3 text-xs font-extrabold uppercase tracking-[0.12em] text-[var(--muted)]">Project inbox</p>
        <div className="grid gap-2">
          {data.projects.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setSelectedId(item.id)}
              aria-pressed={item.id === project.id}
              className={`min-h-20 rounded-lg border p-4 text-left ${item.id === project.id ? "border-[var(--line-dark)] bg-[var(--surface-muted)]" : "border-transparent hover:border-[var(--line)] hover:bg-[var(--surface-soft)]"}`}
            >
              <span className="block truncate text-sm font-black">{item.title}</span>
              <span className="mt-1 block truncate text-xs text-[var(--muted)]">{item.client_name}</span>
              <span className="mt-2 block"><StatusPill status={item.lifecycle_status} /></span>
            </button>
          ))}
        </div>
      </aside>
      <div className="min-w-0">
        <section className="panel p-6 sm:p-8">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="eyebrow">Project workspace</p>
              <h1 className="mt-2 text-balance text-3xl font-black tracking-[-0.045em]">{project.title}</h1>
              <p className="mt-2 text-sm text-[var(--muted)]">{project.client_name} · {project.client_email}</p>
            </div>
            <StatusPill status={project.lifecycle_status} />
          </div>
          <dl className="mt-7 grid grid-cols-2 gap-4 border-t border-[var(--line)] pt-6 sm:grid-cols-4">
            <div><dt className="text-[10px] font-extrabold uppercase tracking-[0.1em] text-[var(--muted)]">Current value</dt><dd className="tabular mt-1 text-xl font-black">{money(project.current_price_usd)}</dd></div>
            <div><dt className="text-[10px] font-extrabold uppercase tracking-[0.1em] text-[var(--muted)]">Timeline</dt><dd className="tabular mt-1 text-xl font-black">{project.current_timeline_days}d</dd></div>
            <div><dt className="text-[10px] font-extrabold uppercase tracking-[0.1em] text-[var(--muted)]">Artifacts</dt><dd className="tabular mt-1 text-xl font-black">{artifacts.length}</dd></div>
            <div><dt className="text-[10px] font-extrabold uppercase tracking-[0.1em] text-[var(--muted)]">Scope events</dt><dd className="tabular mt-1 text-xl font-black">{events.length}</dd></div>
          </dl>
        </section>
        <div className="mt-6 grid gap-6">
          <section className="panel p-6 sm:p-8">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div><p className="eyebrow">Authoritative context</p><h2 className="mt-1 text-xl font-black">Current scope snapshot</h2></div>
              {scope ? <StatusPill status={scope.status} /> : null}
            </div>
            {detailError ? <p role="alert" className="mt-4 rounded-lg bg-[var(--surface-muted)] px-4 py-3 text-sm font-bold text-[var(--ink)]">{detailError}</p> : null}
            {detailLoading ? <p role="status" className="mt-4 rounded-lg bg-[var(--surface-muted)] px-4 py-3 text-sm font-bold text-[var(--muted)]">Loading the authoritative scope and version history…</p> : null}
            <div className="mt-5 grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
              <div>
                <p className="text-xs font-extrabold uppercase tracking-[0.1em] text-[var(--muted)]">Included modules</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {(scope?.module_selections ?? artifacts[0]?.calculation_inputs ?? []).map((module) => (
                    <span key={module.module_key} className="rounded-full border border-[var(--line)] bg-[var(--surface-muted)] px-3 py-1.5 text-xs font-extrabold text-[var(--ink)]">
                      {humanize(module.module_key)} · {module.quantity}
                    </span>
                  ))}
                  {!scope && !artifacts[0] ? <span className="text-sm text-[var(--muted)]">No active scope yet.</span> : null}
                </div>
                {scope?.requirements.length ? (
                  <div className="mt-5 grid gap-2">
                    {scope.requirements.map((requirement) => (
                      <div key={requirement.requirement_id} className="rounded-lg border border-[var(--line)] bg-white px-4 py-3">
                        <p className="text-xs font-extrabold text-[var(--ink)]">{requirement.requirement_id} · {requirement.category}</p>
                        <p className="mt-1 text-sm font-semibold leading-6">{requirement.description}</p>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-1">
                <div className="rounded-lg bg-[var(--surface-soft)] p-4">
                  <p className="text-xs font-extrabold uppercase tracking-[0.1em] text-[var(--muted)]">Assumptions</p>
                  {scope?.assumptions.length ? <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-5">{scope.assumptions.map((item) => <li key={item}>{item}</li>)}</ul> : <p className="mt-3 text-sm text-[var(--muted)]">No assumptions recorded in this view.</p>}
                </div>
                <div className="rounded-lg bg-[var(--surface-soft)] p-4">
                  <p className="text-xs font-extrabold uppercase tracking-[0.1em] text-[var(--muted)]">Explicit exclusions</p>
                  {scope?.exclusions.length ? <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-5">{scope.exclusions.map((item) => <li key={item}>{item}</li>)}</ul> : <p className="mt-3 text-sm text-[var(--muted)]">No exclusions recorded in this view.</p>}
                </div>
              </div>
            </div>
            {effectiveDetail?.scope_versions.length ? (
              <div className="mt-6 border-t border-[var(--line)] pt-5">
                <p className="text-xs font-extrabold uppercase tracking-[0.1em] text-[var(--muted)]">Immutable scope versions</p>
                <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                  {effectiveDetail.scope_versions.map((version) => (
                    <article key={version.id} className="rounded-lg border border-[var(--line)] bg-white p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-black">Version {version.version_number}</p>
                        <StatusPill status={version.status} />
                      </div>
                      <p className="tabular mt-3 text-sm font-extrabold text-[var(--ink)]">{money(version.total_price_usd)} · {version.timeline_days}d</p>
                      <p className="mt-1 text-xs text-[var(--muted)]">{version.sop_version} · {time(version.created_at)}</p>
                    </article>
                  ))}
                </div>
              </div>
            ) : null}
          </section>
          {artifacts.map((artifact) => <ArtifactReview key={artifact.id} artifact={artifact} project={project} demo={demo} operatorId={operatorId} setOperatorId={setOperatorId} busy={busy} onCommand={onCommand} />)}
          {!artifacts.length ? <EmptyState>No commercial artifacts for this project.</EmptyState> : null}
          <section className="grid gap-6 xl:grid-cols-2">
            <div className="panel p-5 sm:p-6"><p className="eyebrow">Evidence trail</p><h2 className="mt-1 text-xl font-black">Scope events</h2><div className="mt-4"><ScopeEventList events={events} /></div></div>
            <div className="panel p-5 sm:p-6"><p className="eyebrow">Pending changes</p><h2 className="mt-1 text-xl font-black">Buffers</h2><div className="mt-4 grid gap-3">{buffers.length ? buffers.map((buffer) => <BufferCard key={buffer.id} buffer={buffer} demo={demo} busy={busy} onCommand={onCommand} />) : <EmptyState>No open buffer for this project.</EmptyState>}</div></div>
          </section>
          <section className="panel p-5 sm:p-6">
            <p className="eyebrow">Application audit</p>
            <h2 className="mt-1 text-xl font-black">Project agent runs</h2>
            <div className="mt-4"><AgentActivity runs={effectiveDetail?.agent_runs ?? []} /></div>
          </section>
        </div>
      </div>
    </div>
  );
}

function Evals({ data }: { data: DashboardSnapshot }) {
  const passed = data.readiness.checks.reduce((sum, check) => sum + check.passed, 0);
  const expected = data.readiness.checks.reduce((sum, check) => sum + check.expected, 0);
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
      <section className="panel p-6 sm:p-8">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="eyebrow">Release evidence</p>
            <h1 className="mt-2 text-balance text-3xl font-black tracking-[-0.045em]">Agent readiness is measurable.</h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--muted)]">These are the packaged results of the latest reviewed pre-Gmail gate—not marketing estimates or live production uptime.</p>
          </div>
          <StatusPill status={data.readiness.status} />
        </div>
        <div className="mt-8 grid gap-3">
          {data.readiness.checks.map((check) => (
            <article key={check.key} className="grid grid-cols-[auto_1fr_auto] items-center gap-4 rounded-lg border border-[var(--line)] bg-white p-4">
              <span className="grid size-10 place-items-center rounded-full bg-[var(--surface-muted)] text-[var(--ink)]"><Check size={19} /></span>
              <div><h2 className="text-sm font-extrabold">{check.label}</h2><p className="mt-1 text-xs text-[var(--muted)]">{check.key === "repeatability" ? "Six difficult scenarios repeated three times" : "Reviewed contract gate"}</p></div>
              <p className="tabular text-lg font-black text-[var(--ink)]">{check.passed}/{check.expected}</p>
            </article>
          ))}
        </div>
      </section>
      <aside className="grid content-start gap-6">
        <section className="readiness-total rounded-lg border border-[var(--ink)] bg-[var(--ink)] p-6 text-white shadow-[var(--shadow-panel)]">
          <p className="text-xs font-extrabold uppercase tracking-[0.12em] text-[var(--on-dark)]">Verified total</p>
          <p className="tabular mt-3 text-5xl font-black tracking-[-0.05em]">{passed}<span className="text-2xl text-[var(--on-dark)]">/{expected}</span></p>
          <p className="mt-4 text-sm leading-6 text-[var(--on-dark)]">{data.readiness.note}</p>
          <div className="mt-6 border-t border-white/15 pt-5 text-xs font-bold text-[var(--on-dark)]">
            <p>{data.readiness.model ?? "Model not recorded"}</p>
            <p className="mt-2">Verified {time(data.readiness.verified_at)}</p>
          </div>
        </section>
        <section className="panel p-6">
          <p className="eyebrow">Safety invariant</p>
          <div className="mt-4 flex gap-3"><ShieldCheck className="shrink-0 text-[var(--ink)]" size={22} /><div><p className="font-black">Approval-gate violations: 0</p><p className="mt-2 text-xs leading-5 text-[var(--muted)]">Agents have no Gmail send, pricing, approval, or state-mutation tools.</p></div></div>
        </section>
      </aside>
    </div>
  );
}

export function OperatorApp({ view }: { view: View }) {
  const [health, setHealth] = useState<Health>("checking");
  const [operatorKey, setOperatorKey] = useState("");
  const [operatorId, setOperatorIdState] = useState("");
  const [data, setData] = useState<DashboardSnapshot | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [demo, setDemo] = useState(false);

  const load = async (key: string) => {
    const snapshot = await apiRequest<DashboardSnapshot>("/api/dashboard", key);
    setData(snapshot);
  };

  useEffect(() => {
    fetch("/health", { cache: "no-store" })
      .then((response) => setHealth(response.ok ? "online" : "offline"))
      .catch(() => setHealth("offline"));
    const params = new URLSearchParams(window.location.search);
    if (params.get("demo") === "1") {
      setDemo(true);
      setHealth("online");
      setData(demoDashboard);
      return;
    }
    const storedId = sessionStorage.getItem(OPERATOR_ID_KEY) ?? "";
    setOperatorIdState(storedId);
  }, []);

  const setOperatorId = (value: string) => {
    setOperatorIdState(value);
    sessionStorage.setItem(OPERATOR_ID_KEY, value);
  };

  const connect = async (key: string) => {
    setBusy(true);
    setError(null);
    let keyAccepted = false;
    try {
      await apiRequest<{ status: "accepted" }>("/api/session", key);
      keyAccepted = true;
      await load(key);
      setOperatorKey(key);
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Unable to open the operator console.";
      setError(keyAccepted ? `Operator key accepted, but the dashboard could not load: ${message}` : message);
    } finally {
      setBusy(false);
    }
  };

  const disconnect = () => {
    setOperatorKey("");
    setData(null);
    setNotice(null);
  };

  const onCommand = async (path: string, payload: Record<string, string>) => {
    if (demo || !operatorKey) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await apiRequest(path, operatorKey, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      await load(operatorKey);
      setNotice("Action completed and the dashboard has been refreshed.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The action could not be completed.");
    } finally {
      setBusy(false);
    }
  };

  const title = useMemo(() => {
    if (view === "projects") return ["Project inbox", "Scope and commercial history"];
    if (view === "evals") return ["Agent readiness", "Measured confidence before automation"];
    return ["Good morning", "Protect the scope. Keep the relationship."];
  }, [view]);

  return (
    <div className="operator-shell">
      <AppHeader view={view} health={health} connected={Boolean(data)} demo={demo} onDisconnect={disconnect} />
      {!data ? <ConnectPanel busy={busy} error={error} onConnect={connect} /> : (
        <main id="main-content" className="mx-auto max-w-[1480px] px-4 py-8 sm:px-7 lg:px-10 lg:py-10">
          {demo ? (
            <div className="mb-6 flex flex-col gap-3 rounded-lg border border-[var(--line-strong)] bg-[var(--surface-soft)] px-4 py-3 text-sm font-bold text-[var(--ink)] sm:flex-row sm:items-center sm:justify-between">
              <span className="flex min-w-0 items-center gap-2 break-words"><TriangleAlert size={17} className="shrink-0" /> Reviewed demo fixture—no live Gmail data or external actions.</span>
              <a href={view === "overview" ? "/" : `/${view}/`} className="underline underline-offset-4">Leave demo</a>
            </div>
          ) : null}
          <header className="mb-7 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="eyebrow">{title[0]}</p>
              <h1 className="mt-2 text-balance text-3xl font-black tracking-[-0.045em] sm:text-4xl">{title[1]}</h1>
              <p className="mt-3 text-sm font-semibold text-[var(--muted)]">Last refreshed {time(data.generated_at)}</p>
            </div>
            <button
              type="button"
              disabled={busy || demo}
              onClick={() => void load(operatorKey)}
              className="inline-flex min-h-11 items-center justify-center gap-2 self-start rounded-lg border border-[var(--line-strong)] bg-white px-4 text-sm font-extrabold hover:bg-[var(--surface-soft)] disabled:opacity-45 sm:self-auto"
            >
              <RefreshCw className={busy ? "animate-spin" : ""} size={16} /> Refresh
            </button>
          </header>
          <div aria-live="polite" aria-atomic="true">
            {notice ? <p className="mb-6 flex gap-2 rounded-lg border border-[var(--line)] bg-[var(--surface-muted)] px-4 py-3 text-sm font-bold text-[var(--ink)]"><CheckCircle2 size={18} />{notice}</p> : null}
            {error ? <p role="alert" className="mb-6 flex gap-2 rounded-lg border border-[var(--line-dark)] bg-[var(--surface-muted)] px-4 py-3 text-sm font-bold text-[var(--ink)]"><CircleAlert size={18} />{error}</p> : null}
          </div>
          {data.warnings.length ? (
            <div className="mb-6 rounded-lg border border-[var(--line-strong)] bg-[var(--surface-soft)] px-4 py-3 text-sm text-[var(--ink)]">
              <p className="font-extrabold">Data warnings</p>
              <ul className="mt-2 list-disc pl-5">{data.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
            </div>
          ) : null}
          {view === "overview" ? <Overview data={data} demo={demo} operatorId={operatorId} setOperatorId={setOperatorId} busy={busy} onCommand={onCommand} onRefresh={() => void load(operatorKey)} /> : null}
          {view === "projects" ? <Projects data={data} demo={demo} operatorKey={operatorKey} operatorId={operatorId} setOperatorId={setOperatorId} busy={busy} onCommand={onCommand} /> : null}
          {view === "evals" ? <Evals data={data} /> : null}
          <footer className="mt-10 flex flex-col gap-2 border-t border-[var(--line)] py-6 text-xs font-semibold text-[var(--muted)] sm:flex-row sm:items-center sm:justify-between">
            <span>ScopeLock · approval-gated commercial automation</span>
            <span className="inline-flex items-center gap-2"><Clock3 size={14} /> Every action is correlation-ID logged</span>
          </footer>
        </main>
      )}
    </div>
  );
}

import {
  Activity,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  Clock3,
  FileCheck2,
  FileText,
  Inbox,
  KeyRound,
  LockKeyhole,
  LogOut,
  Mail,
  Paperclip,
  PanelLeftClose,
  PanelLeftOpen,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  X,
} from "lucide-react";
import { FormEvent, MouseEvent, useEffect, useMemo, useState } from "react";

import { apiRequest, correlationId } from "@/lib/api";
import { demoDashboard, demoInboxMessageDetails, demoProjectDetails } from "@/lib/demo-data";
import { ArtifactReview } from "@/components/commercial-artifact-review";
import {
  EmptyState,
  humanize,
  money,
  StatusPill,
  time,
} from "@/components/dashboard-primitives";
import type {
  AgentRun,
  Artifact,
  DashboardSnapshot,
  InboxMessage,
  InboxMessageDetail,
  Project,
  ProjectDetailSnapshot,
  ScopeBuffer,
  ScopeEvent,
} from "@/lib/types";

type View = "overview" | "projects" | "evals";
const OPERATOR_ID_KEY = "scopelock.operatorId";
const SIDEBAR_COLLAPSED_KEY = "scopelock.sidebarCollapsed";
const REVIEW_STATUSES = new Set([
  "AWAITING_USER_REVIEW",
  "NEEDS_REVIEW",
  "APPROVED",
  "SENT",
  "SEND_FAILED",
]);

function dashboardHref(path: string, demo: boolean) {
  return demo ? `${path}${path.includes("?") ? "&" : "?"}demo=1` : path;
}

function navigateWithinDashboard(event: MouseEvent<HTMLAnchorElement>) {
  if (
    event.defaultPrevented ||
    event.button !== 0 ||
    event.metaKey ||
    event.ctrlKey ||
    event.shiftKey ||
    event.altKey
  ) {
    return;
  }
  event.preventDefault();
  window.history.pushState({}, "", event.currentTarget.href);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function AppHeader({
  view,
  sidebarCollapsed,
  connected,
  demo,
  busy,
  onToggleSidebar,
  onRefresh,
  onScopeIntelligence,
  onDisconnect,
}: {
  view: View;
  sidebarCollapsed: boolean;
  connected: boolean;
  demo: boolean;
  busy: boolean;
  onToggleSidebar: () => void;
  onRefresh: () => void;
  onScopeIntelligence: () => void;
  onDisconnect: () => void;
}) {
  const navigation: Array<[View, string, string, React.ReactNode]> = [
    ["overview", "Overview", "/", <Inbox key="overview-icon" size={17} aria-hidden="true" />],
    ["projects", "Projects", "/projects/", <FileCheck2 key="projects-icon" size={17} aria-hidden="true" />],
    ["evals", "Agent readiness", "/evals/", <ShieldCheck key="evals-icon" size={17} aria-hidden="true" />],
  ];
  return (
    <>
      <aside id="workspace-navigation" className="operator-sidebar" aria-label="Workspace navigation">
        <a href={dashboardHref("/", demo)} onClick={navigateWithinDashboard} className="sidebar-brand rounded-lg" aria-label="ScopeLock home">
          <span className="sidebar-brand-mark grid size-10 shrink-0 place-items-center rounded-lg text-[var(--ink)]">
            <LockKeyhole aria-hidden="true" size={20} strokeWidth={2.4} />
          </span>
          <span className="sidebar-brand-copy min-w-0">
            <span className="block text-lg font-black tracking-[-0.035em]">ScopeLock</span>
            <span className="block text-[10px] font-bold uppercase tracking-[0.18em] text-[var(--muted)]">Operator console</span>
          </span>
        </a>
        <button
          type="button"
          onClick={onToggleSidebar}
          className="sidebar-toggle"
          aria-controls="workspace-navigation"
          aria-expanded={!sidebarCollapsed}
          aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {sidebarCollapsed ? <PanelLeftOpen size={18} aria-hidden="true" /> : <PanelLeftClose size={18} aria-hidden="true" />}
          <span className="sidebar-toggle-label">Collapse sidebar</span>
        </button>
        <p className="sidebar-section-label">Workspace</p>
        <nav aria-label="Primary" className="sidebar-nav">
          {navigation.map(([key, label, href, icon]) => (
            <a key={key} href={dashboardHref(href, demo)} onClick={navigateWithinDashboard} aria-label={label} title={sidebarCollapsed ? label : undefined} aria-current={view === key ? "page" : undefined} className={`sidebar-link ${view === key ? "is-active" : ""}`}>
              {icon}<span className="sidebar-link-label sidebar-link-label-full">{label}</span><span className="sidebar-link-label sidebar-link-label-mobile">{key === "evals" ? "Readiness" : label}</span>
            </a>
          ))}
        </nav>
        <div className="sidebar-note">
          <p className="text-[10px] font-extrabold uppercase tracking-[0.14em] text-[var(--muted)]">Guardrail</p>
          <p className="mt-2 text-xs font-semibold leading-5 text-[var(--muted-strong)]">Commercial sends stay behind explicit operator approval.</p>
        </div>
        <div className="sidebar-footer"><span className="size-2 rounded-full bg-[var(--ink)]" /> Human approval required</div>
      </aside>
      <header className="operator-header">
        <div className="operator-header-inner">
          <div className="operator-header-identity">
            <span className="operator-header-title">
              {view === "overview" ? "Workspace overview" : view === "projects" ? "Project inbox" : "Agent readiness"}
            </span>
          </div>
          <div className="operator-header-actions">
            {demo ? <span className="operator-demo-badge">Demo mode</span> : null}
            <button
              type="button"
              onClick={onRefresh}
              disabled={!connected || demo || busy}
              className="operator-header-icon-button"
              aria-label="Refresh workspace"
              title="Refresh workspace"
            >
              <RefreshCw size={17} className={busy ? "animate-spin" : ""} aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={onScopeIntelligence}
              className="operator-header-icon-button"
              aria-label="Open scope intelligence"
              title="Scope intelligence"
            >
              <Activity size={18} aria-hidden="true" />
            </button>
            {connected && !demo ? <button type="button" onClick={onDisconnect} className="grid size-11 place-items-center rounded-lg text-[var(--muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--ink)]" aria-label="Disconnect operator session" title="Disconnect"><LogOut size={18} aria-hidden="true" /></button> : null}
          </div>
        </div>
      </header>
    </>
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
  compact = false,
}: {
  label: string;
  value: string;
  detail: string;
  icon: React.ReactNode;
  accent?: boolean;
  compact?: boolean;
}) {
  return (
    <article className={`panel metric-card ${compact ? "p-4" : "p-5 sm:p-6"} ${accent ? "metric-card-accent" : ""}`}>
      <div className="flex items-center gap-3">
        <span className="metric-card-icon grid size-10 shrink-0 place-items-center rounded-lg text-[var(--ink)]">{icon}</span>
        <div className="min-w-0">
          <p className="metric-card-label font-extrabold uppercase text-[var(--muted)]">{label}</p>
          <p className={`tabular ${compact ? "mt-2 text-2xl" : "mt-3 text-3xl"} font-black tracking-[-0.045em]`}>{value}</p>
        </div>
      </div>
      <p className={`${compact ? "mt-2" : "mt-4"} text-xs font-semibold leading-5 text-[var(--muted)]`}>{detail}</p>
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

function ScopeIntelligenceModal({
  data,
  open,
  onClose,
}: {
  data: DashboardSnapshot | null;
  open: boolean;
  onClose: () => void;
}) {
  useEffect(() => {
    if (!open) return;
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
  }, [onClose, open]);

  if (!open) return null;

  const changeArtifact = data?.artifacts.find(
    (item) => item.artifact_type === "CHANGE_ORDER" && REVIEW_STATUSES.has(item.status),
  );
  const changeProject = changeArtifact
    ? data?.projects.find((item) => item.id === changeArtifact.project_id)
    : undefined;

  return (
    <div
      className="scope-intelligence-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        className="scope-intelligence-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="scope-intelligence-title"
      >
        <div className="flex items-start justify-between gap-4 border-b border-[var(--line)] px-5 py-4 sm:px-6">
          <div>
            <p className="eyebrow">Scope intelligence</p>
            <h2 id="scope-intelligence-title" className="mt-1 text-xl font-black tracking-[-0.03em]">How ScopeLock protects the baseline</h2>
            <p className="mt-1 max-w-xl text-xs leading-5 text-[var(--muted)]">
              New client messages are compared with the accepted scope, priced from the SOP, and held for your approval before any commercial communication.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid size-11 shrink-0 place-items-center rounded-lg text-[var(--muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--ink)]"
            aria-label="Close scope intelligence"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        <div className="scope-intelligence-body">
          <div className="grid gap-2">
            {[
              ["01", "Read the thread", "Project-linked Gmail messages are monitored without exposing the full mailbox."],
              ["02", "Classify the change", "The agent distinguishes clarification, expansion, reduction, and replacement."],
              ["03", "Calculate the impact", "Deterministic SOP rules calculate price and timeline deltas for review."],
            ].map(([step, title, description]) => (
              <article key={step} className="scope-intelligence-step flex items-start gap-3">
                <span className="scope-intelligence-step-number shrink-0">{step}</span>
                <div className="min-w-0">
                  <h3 className="text-sm font-black">{title}</h3>
                  <p className="mt-1 text-xs leading-5 text-[var(--muted)]">{description}</p>
                </div>
              </article>
            ))}
          </div>

          {changeArtifact && changeProject ? (
            <section className="mt-5 rounded-xl border border-[var(--line-strong)] bg-[var(--surface-soft)] p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="eyebrow">Current signal</p>
                  <h3 className="mt-1 text-base font-black">{changeProject.title}</h3>
                  <p className="mt-1 text-xs font-semibold text-[var(--muted)]">Initial scope change awaiting review</p>
                </div>
                <StatusPill status="NEEDS_REVIEW" />
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <div className="rounded-lg border border-[var(--line)] bg-white p-3">
                  <p className="text-[10px] font-extrabold uppercase tracking-[0.1em] text-[var(--muted)]">Price impact</p>
                  <p className="tabular mt-1 text-xl font-black">{money(changeArtifact.pricing_result.total_usd - changeProject.current_price_usd, true)}</p>
                </div>
                <div className="rounded-lg border border-[var(--line)] bg-white p-3">
                  <p className="text-[10px] font-extrabold uppercase tracking-[0.1em] text-[var(--muted)]">Timeline impact</p>
                  <p className="tabular mt-1 text-xl font-black">+{Math.max(0, changeArtifact.timeline_result.total_days - changeProject.current_timeline_days)} days</p>
                </div>
              </div>
            </section>
          ) : null}

          <section className="mt-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="eyebrow">Evidence trail</p>
                <h3 className="mt-1 text-base font-black">Latest scope events</h3>
              </div>
              <span className="text-xs font-bold text-[var(--muted)]">{data?.scope_events.length ?? 0} recorded</span>
            </div>
            <div className="mt-3">
              {data ? <ScopeEventList events={data.scope_events} /> : <EmptyState>Connect the operator console to view live scope events.</EmptyState>}
            </div>
          </section>
        </div>

        <div className="flex items-center justify-end border-t border-[var(--line)] px-5 py-4 sm:px-6">
          <button type="button" onClick={onClose} className="min-h-11 rounded-lg bg-[var(--ink)] px-4 text-sm font-extrabold text-white hover:bg-[var(--ink-strong)]">Close</button>
        </div>
      </section>
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

function GmailReviewPanel({
  data,
  demo,
  operatorKey,
  busy,
  onCommand,
  compact = false,
}: {
  data: DashboardSnapshot;
  demo: boolean;
  operatorKey: string;
  busy: boolean;
  onCommand: (path: string, payload: Record<string, string>) => Promise<void>;
  compact?: boolean;
}) {
  const [confirmWatch, setConfirmWatch] = useState(false);
  const [selectedMessage, setSelectedMessage] = useState<InboxMessage | null>(null);
  const [messageDetail, setMessageDetail] = useState<InboxMessageDetail | null>(null);
  const [messageLoading, setMessageLoading] = useState(false);
  const [messageError, setMessageError] = useState<string | null>(null);
  const projectsById = new Map(data.projects.map((project) => [project.id, project]));
  const watch = data.gmail_watch;

  const registerWatch = () => {
    setConfirmWatch(false);
    void onCommand("/gmail/watch", {});
  };

  const openMessage = async (message: InboxMessage) => {
    setSelectedMessage(message);
    setMessageDetail(null);
    setMessageError(null);
    if (demo) {
      setMessageDetail(demoInboxMessageDetails[message.id] ?? null);
      return;
    }
    setMessageLoading(true);
    try {
      const detail = await apiRequest<InboxMessageDetail>(
        `/api/messages/${encodeURIComponent(message.id)}`,
        operatorKey,
      );
      setMessageDetail(detail);
    } catch (caught) {
      setMessageError(
        caught instanceof Error ? caught.message : "The selected message could not be loaded.",
      );
    } finally {
      setMessageLoading(false);
    }
  };

  const closeMessage = () => {
    setSelectedMessage(null);
    setMessageDetail(null);
    setMessageError(null);
    setMessageLoading(false);
  };

  return (
    <>
    <section className={`panel gmail-review-panel flex min-w-0 flex-col p-5 sm:p-6 ${compact ? "overview-inbox-panel" : "min-h-[31rem]"}`}>
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[var(--line)] pb-5">
        <p className="eyebrow">Gmail review</p>
        {watch ? (
          <div className="gmail-monitoring-control">
            <button type="button" className="gmail-monitoring-button" aria-describedby="gmail-monitoring-tooltip">
              <Activity size={13} aria-hidden="true" /> Monitoring
            </button>
            <div id="gmail-monitoring-tooltip" role="tooltip" className="gmail-monitoring-tooltip">
              Monitoring <span className="font-extrabold text-[var(--ink)]">{watch.mailbox}</span> · watch expires {time(watch.expiration)}
            </div>
          </div>
        ) : <StatusPill status="NOT_CONNECTED" />}
      </div>

      {data.inbox_messages.length ? (
        <div className="mt-4 min-h-0 flex-1 overflow-y-auto pr-1">
          <div className={compact ? "overview-message-list" : "grid gap-2"}>
            {data.inbox_messages.slice(0, compact ? 3 : undefined).map((message) => {
              const project = projectsById.get(message.project_id);
              if (compact) {
                return (
                  <button key={message.id} type="button" onClick={() => void openMessage(message)} className="overview-message-row w-full bg-white px-4 py-3 text-left" aria-label={`Open email: ${message.subject || "No subject"}`}>
                    <div className="overview-message-grid">
                      <div className="min-w-0"><p className="truncate text-xs font-bold">{message.subject || "No subject"}</p><p className="mt-1 truncate text-[10px] text-[var(--muted)]">{message.sender_name || message.sender_email}</p></div>
                      <p className="truncate text-[10px] text-[var(--muted)]">{project?.title ?? "Project"}</p>
                      <p className="shrink-0 text-[10px] font-bold text-[var(--muted)]">{time(message.received_at)}</p>
                      <StatusPill status={message.direction} />
                    </div>
                  </button>
                );
              }
              return (
                <button key={message.id} type="button" onClick={() => void openMessage(message)} className="rounded-lg border border-[var(--line)] bg-white p-4 text-left hover:bg-[var(--surface-soft)]">
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
                </button>
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
    <MessageDetailModal message={selectedMessage} detail={messageDetail} loading={messageLoading} error={messageError} onClose={closeMessage} />
    </>
  );
}

function MessageDetailModal({ message, detail, loading, error, onClose }: {
  message: InboxMessage | null;
  detail: InboxMessageDetail | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
}) {
  useEffect(() => {
    if (!message) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [message, onClose]);

  if (!message) return null;
  return (
    <div className="preview-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="message-detail-modal" role="dialog" aria-modal="true" aria-labelledby="message-detail-title">
        <div className="flex items-start justify-between gap-4 border-b border-[var(--line)] px-5 py-4 sm:px-6">
          <div className="min-w-0">
            <p className="eyebrow">Client email</p>
            <h2 id="message-detail-title" className="mt-1 truncate text-xl font-black tracking-[-0.03em]">{message.subject || "No subject"}</h2>
            <p className="mt-1 text-xs text-[var(--muted)]">{message.sender_name || message.sender_email} · {time(message.received_at)}</p>
          </div>
          <button type="button" onClick={onClose} className="grid size-11 shrink-0 place-items-center rounded-lg text-[var(--muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--ink)]" aria-label="Close email"><X size={18} /></button>
        </div>
        <div className="message-detail-body">
          {loading ? <p className="text-sm font-bold text-[var(--muted)]">Loading the selected project email…</p> : null}
          {error ? <p role="alert" className="rounded-lg border border-[var(--line)] bg-[var(--surface-soft)] p-4 text-sm font-bold">{error}</p> : null}
          {detail ? <><pre className="message-body-copy">{detail.body || "This message has no text body."}</pre>{detail.attachments.length ? <div className="mt-4 grid gap-2">{detail.attachments.map((attachment) => <div key={`${attachment.filename}-${attachment.size}`} className="flex items-center gap-2 rounded-lg border border-[var(--line)] px-3 py-2 text-xs"><Paperclip size={14} /><span className="font-bold">{attachment.filename}</span><span className="text-[var(--muted)]">{attachment.mime_type}</span></div>)}</div> : null}</> : null}
        </div>
      </section>
    </div>
  );
}

function Overview({
  data,
  demo,
  operatorKey,
  operatorId,
  setOperatorId,
  busy,
  onCommand,
}: {
  data: DashboardSnapshot;
  demo: boolean;
  operatorKey: string;
  operatorId: string;
  setOperatorId: (value: string) => void;
  busy: boolean;
  onCommand: (path: string, payload: Record<string, string>) => Promise<void>;
}) {
  const artifact = data.artifacts.find((item) => REVIEW_STATUSES.has(item.status)) ?? data.artifacts[0];
  const project = artifact ? data.projects.find((item) => item.id === artifact.project_id) : undefined;
  const actionCount = data.artifacts.filter((item) => REVIEW_STATUSES.has(item.status)).length + data.scope_buffers.filter((item) => item.status === "READY_TO_FINALIZE").length;
  const bufferedDelta = data.scope_buffers
    .filter((item) => item.status !== "FINALIZED")
    .reduce((sum, item) => sum + item.net_price_delta_usd, 0);
  const artifactDelta = data.artifacts
    .filter(
      (item) =>
        item.artifact_type === "CHANGE_ORDER" && REVIEW_STATUSES.has(item.status),
    )
    .reduce((sum, item) => {
      const baselineProject = data.projects.find((candidate) => candidate.id === item.project_id);
      return sum + item.pricing_result.total_usd - (baselineProject?.current_price_usd ?? 0);
  }, 0);
  const pendingDelta = bufferedDelta + artifactDelta;

  return (
    <div className="overview-viewport">
      <section className="overview-metrics grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Action required" value={String(actionCount)} detail="Review items and ready scope buffers" icon={<CircleAlert size={19} />} accent={actionCount > 0} compact />
        <MetricCard label="Monitored projects" value={String(data.projects.length)} detail="Gmail threads with application state" icon={<Inbox size={19} />} compact />
        <MetricCard label="Pending scope delta" value={money(pendingDelta, true)} detail="Calculated now; never sent automatically" icon={<Activity size={19} />} compact />
        <MetricCard label="Agent gate" value={data.readiness.status} detail={`${data.readiness.checks.reduce((sum, item) => sum + item.passed, 0)} reviewed checks passed`} icon={<ShieldCheck size={19} />} compact />
      </section>

      <section className="sop-source-strip panel" aria-label="Active business SOP">
        <span className="sop-source-icon"><FileText size={18} aria-hidden="true" /></span>
        <div className="min-w-0 flex-1"><p className="text-xs font-black">Business SOP</p><p className="mt-0.5 truncate text-[10px] text-[var(--muted)]">Configured catalog · {artifact?.sop_version ?? "No active SOP version"}</p></div>
        <span className="rounded-full border border-[var(--line)] bg-[var(--surface-soft)] px-2.5 py-1 text-[10px] font-extrabold uppercase tracking-[0.08em] text-[var(--muted-strong)]">{artifact?.sop_version ? "SOP loaded" : "No SOP reference"}</span>
      </section>

      <section className="overview-board mt-2 min-w-0">
        <div className="overview-inbox min-w-0">
          <GmailReviewPanel data={data} demo={demo} operatorKey={operatorKey} busy={busy} onCommand={onCommand} compact />
        </div>

        <section className="panel overview-review priority-review-panel min-w-0 overflow-hidden">
          <div className="priority-review-header flex items-center justify-between gap-3 border-b border-[var(--line)] px-5 py-4 sm:px-6">
            <p className="eyebrow">Priority queue</p>
            <a href={dashboardHref("/projects/", demo)} onClick={navigateWithinDashboard} className="overview-all-projects inline-flex min-h-11 items-center gap-1 rounded-lg px-3 text-xs font-extrabold text-[var(--muted)] hover:text-[var(--ink)]">All projects <ChevronRight size={14} /></a>
          </div>
          {artifact ? <ArtifactReview artifact={artifact} project={project} inboxMessages={data.inbox_messages} demo={demo} operatorKey={operatorKey} compact operatorId={operatorId} setOperatorId={setOperatorId} busy={busy} onCommand={onCommand} /> : <div className="flex flex-1 items-center justify-center p-6"><EmptyState>No commercial artifact needs review.</EmptyState></div>}
        </section>
      </section>
    </div>
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
          {artifacts.map((artifact) => <ArtifactReview key={artifact.id} artifact={artifact} project={project} inboxMessages={data.inbox_messages} demo={demo} operatorKey={operatorKey} operatorId={operatorId} setOperatorId={setOperatorId} busy={busy} onCommand={onCommand} />)}
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
  const [operatorKey, setOperatorKey] = useState("");
  const [operatorId, setOperatorIdState] = useState("");
  const [data, setData] = useState<DashboardSnapshot | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [demo, setDemo] = useState(false);
  const [scopeIntelligenceOpen, setScopeIntelligenceOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      return window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "true";
    } catch {
      return false;
    }
  });

  const load = async (key: string) => {
    const snapshot = await apiRequest<DashboardSnapshot>("/api/dashboard", key);
    setData(snapshot);
  };

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("demo") === "1") {
      setDemo(true);
      setData(demoDashboard);
      return;
    }
    const storedId = sessionStorage.getItem(OPERATOR_ID_KEY) ?? "";
    setOperatorIdState(storedId);
  }, []);

  useEffect(() => {
    if (demo || !operatorKey) return;
    let active = true;
    let inFlight = false;
    const refresh = async () => {
      if (!active || inFlight || document.visibilityState === "hidden") return;
      inFlight = true;
      try {
        const snapshot = await apiRequest<DashboardSnapshot>("/api/dashboard", operatorKey);
        if (active) setData(snapshot);
      } catch {
        // Keep the last trusted snapshot. Manual refresh still surfaces an error.
      } finally {
        inFlight = false;
      }
    };
    const interval = window.setInterval(() => void refresh(), 5_000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [demo, operatorKey]);

  const setOperatorId = (value: string) => {
    setOperatorIdState(value);
    sessionStorage.setItem(OPERATOR_ID_KEY, value);
  };

  const toggleSidebar = () => {
    setSidebarCollapsed((current) => {
      const next = !current;
      try {
        window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(next));
      } catch {
        // The sidebar still works when browser preference storage is unavailable.
      }
      return next;
    });
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
    setScopeIntelligenceOpen(false);
  };

  const refreshDashboard = async () => {
    if (demo || !operatorKey) return;
    setBusy(true);
    setError(null);
    try {
      await load(operatorKey);
      setNotice("Dashboard refreshed.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The dashboard could not be refreshed.");
    } finally {
      setBusy(false);
    }
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
    return ["Workspace overview", "Keep every commercial decision in view."];
  }, [view]);

  return (
    <div className={`operator-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
      <AppHeader
        view={view}
        sidebarCollapsed={sidebarCollapsed}
        connected={Boolean(data)}
        demo={demo}
        busy={busy}
        onToggleSidebar={toggleSidebar}
        onRefresh={() => void refreshDashboard()}
        onScopeIntelligence={() => setScopeIntelligenceOpen(true)}
        onDisconnect={disconnect}
      />
      {!data ? <ConnectPanel busy={busy} error={error} onConnect={connect} /> : (
        <main id="main-content" className={`mx-auto max-w-[1600px] px-4 sm:px-7 lg:px-10 ${view === "overview" ? "overview-main pt-2 pb-0 lg:pt-2" : "py-8 lg:py-10"}`}>
          {demo ? (
            <div className="overview-demo-banner mb-6 flex flex-col gap-3 rounded-lg border border-[var(--line-strong)] bg-[var(--surface-soft)] px-4 py-3 text-sm font-bold text-[var(--ink)] sm:flex-row sm:items-center sm:justify-between">
              <span className="flex min-w-0 items-center gap-2 break-words"><TriangleAlert size={17} className="shrink-0" /> Reviewed demo fixture—no live Gmail data or external actions.</span>
              <a href={view === "overview" ? "/" : `/${view}/`} className="underline underline-offset-4">Leave demo</a>
            </div>
          ) : null}
          {view !== "overview" ? (
            <header className="mb-7 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="eyebrow">{title[0]}</p>
                <h1 className="mt-2 text-balance text-3xl font-black tracking-[-0.045em] sm:text-4xl">{title[1]}</h1>
                <p className="mt-3 text-sm font-semibold text-[var(--muted)]">Last refreshed {time(data.generated_at)}</p>
              </div>
            </header>
          ) : null}
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
          {view === "overview" ? <Overview data={data} demo={demo} operatorKey={operatorKey} operatorId={operatorId} setOperatorId={setOperatorId} busy={busy} onCommand={onCommand} /> : null}
          {view === "projects" ? <Projects data={data} demo={demo} operatorKey={operatorKey} operatorId={operatorId} setOperatorId={setOperatorId} busy={busy} onCommand={onCommand} /> : null}
          {view === "evals" ? <Evals data={data} /> : null}
          <footer className="mt-10 flex flex-col gap-2 border-t border-[var(--line)] py-6 text-xs font-semibold text-[var(--muted)] sm:flex-row sm:items-center sm:justify-between">
            <span>ScopeLock · approval-gated commercial automation</span>
            <span className="inline-flex items-center gap-2"><Clock3 size={14} /> Every action is correlation-ID logged</span>
          </footer>
        </main>
      )}
      <ScopeIntelligenceModal data={data} open={scopeIntelligenceOpen} onClose={() => setScopeIntelligenceOpen(false)} />
    </div>
  );
}

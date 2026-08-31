import {
  Activity,
  ArrowRight,
  CheckCircle2,
  CircleAlert,
  Clock3,
  FileCheck2,
  Inbox,
  KeyRound,
  LogOut,
  Mail,
  Paperclip,
  PanelLeftClose,
  PanelLeftOpen,
  RefreshCw,
  Save,
  Settings2,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  X,
  type LucideIcon,
} from "lucide-react";
import { type FormEvent, type MouseEvent, useEffect, useRef, useState } from "react";

import { ApiError, apiRequest, correlationId, type ApiCredential } from "@/lib/api";
import {
  readStoredJson,
  readStoredValue,
  writeStoredJson,
  writeStoredValue,
} from "@/lib/browser-storage";
import { demoDashboard, demoInboxMessageDetails } from "@/lib/demo-data";
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
  ScopeBuffer,
  ScopeEvent,
} from "@/lib/types";

type View = "overview" | "settings";
const OPERATOR_ID_KEY = "scopelock.operatorId";
const SIDEBAR_COLLAPSED_KEY = "scopelock.sidebarCollapsed";
const SOP_DRAFT_KEY_PREFIX = "scopelock.sopDraft.";
const REVIEW_STATUSES = new Set([
  "AWAITING_USER_REVIEW",
  "NEEDS_REVIEW",
  "APPROVED",
  "SENT",
  "SEND_FAILED",
]);

type NavigationItem = {
  view: View;
  label: string;
  mobileLabel?: string;
  href: string;
  icon: LucideIcon;
};

const PRIMARY_NAVIGATION: NavigationItem[] = [
  { view: "overview", label: "Overview", href: "/", icon: Inbox },
];

const SYSTEM_NAVIGATION: NavigationItem[] = [
  { view: "settings", label: "Settings", href: "/settings/", icon: Settings2 },
];

const VIEW_TITLES: Record<View, readonly [string, string]> = {
  overview: ["Workspace overview", "Keep every commercial decision in view."],
  settings: ["Settings", "Manage the connected workspace and business rules"],
};

function latestWorkspaceArtifact(data: DashboardSnapshot): Artifact | undefined {
  const currentArtifacts = data.artifacts.filter((artifact) => {
    const project = data.projects.find((candidate) => candidate.id === artifact.project_id);
    return !project?.active_proposal_id || project.active_proposal_id === artifact.id;
  });
  const reviewArtifacts = currentArtifacts.filter((artifact) => REVIEW_STATUSES.has(artifact.status));
  const candidates = reviewArtifacts.length ? reviewArtifacts : currentArtifacts.length ? currentArtifacts : data.artifacts;

  return [...candidates].sort((left, right) => {
    const leftActive = data.projects.some((project) => project.active_proposal_id === left.id);
    const rightActive = data.projects.some((project) => project.active_proposal_id === right.id);
    return Number(rightActive) - Number(leftActive)
      || new Date(right.created_at).getTime() - new Date(left.created_at).getTime()
      || right.version_number - left.version_number;
  })[0];
}

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

function SidebarLink({
  item,
  activeView,
  demo,
  collapsed,
}: {
  item: NavigationItem;
  activeView: View;
  demo: boolean;
  collapsed: boolean;
}) {
  const Icon = item.icon;
  return (
    <a
      href={dashboardHref(item.href, demo)}
      onClick={navigateWithinDashboard}
      aria-label={item.label}
      title={collapsed ? item.label : undefined}
      aria-current={activeView === item.view ? "page" : undefined}
      className={`sidebar-link ${activeView === item.view ? "is-active" : ""}`}
    >
      <Icon size={17} aria-hidden="true" />
      <span className="sidebar-link-label sidebar-link-label-full">{item.label}</span>
      <span className="sidebar-link-label sidebar-link-label-mobile">{item.mobileLabel ?? item.label}</span>
    </a>
  );
}

function AppHeader({
  view,
  reviewer = false,
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
  reviewer?: boolean;
  sidebarCollapsed: boolean;
  connected: boolean;
  demo: boolean;
  busy: boolean;
  onToggleSidebar: () => void;
  onRefresh: () => void;
  onScopeIntelligence: () => void;
  onDisconnect: () => void;
}) {
  return (
    <>
      <aside id="workspace-navigation" className="operator-sidebar" aria-label="Workspace navigation">
        <div className="sidebar-top-row">
          <a href={reviewer ? "/review/" : dashboardHref("/", demo)} onClick={reviewer ? undefined : navigateWithinDashboard} className="sidebar-brand rounded-lg" aria-label="ScopeLock home">
            <span className="sidebar-brand-mark grid size-10 shrink-0 place-items-center overflow-hidden rounded-lg bg-white">
              <img src="/scopelock-logo.jpeg" alt="" className="size-full object-cover" />
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
          </button>
        </div>
        <p className="sidebar-section-label">Workspace</p>
        <nav aria-label="Primary" className="sidebar-nav">
          {PRIMARY_NAVIGATION.map((item) => <SidebarLink key={item.view} item={item} activeView={view} demo={demo} collapsed={sidebarCollapsed} />)}
        </nav>
        <nav aria-label="System" className="sidebar-nav sidebar-nav-settings">
          {!reviewer ? SYSTEM_NAVIGATION.map((item) => <SidebarLink key={item.view} item={item} activeView={view} demo={demo} collapsed={sidebarCollapsed} />) : null}
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
              {VIEW_TITLES[view][0]}
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
        <div className="min-w-0 flex-1">
          <p className="metric-card-label text-left font-extrabold uppercase text-[var(--muted)]">{label}</p>
          <p className={`tabular text-right ${compact ? "mt-2 text-2xl" : "mt-3 text-3xl"} font-black tracking-[-0.045em]`}>{value}</p>
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
  const openBuffer = data?.scope_buffers.find((item) => item.status !== "FINALIZED");
  const openBufferPrice = openBuffer?.net_price_delta_usd ?? (openBuffer ? data?.scope_events.filter((event) => openBuffer.event_ids.includes(event.id)).reduce((sum, event) => sum + event.price_delta_usd, 0) : 0);
  const openBufferDays = openBuffer?.net_timeline_delta_days ?? (openBuffer ? data?.scope_events.filter((event) => openBuffer.event_ids.includes(event.id)).reduce((sum, event) => sum + event.timeline_delta_days, 0) : 0);

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
          {openBuffer ? (
            <section className="mt-5 rounded-xl border border-[var(--line-strong)] bg-[var(--surface-soft)] p-4">
              <p className="eyebrow">Current signal</p>
              <h3 className="mt-1 text-base font-black">Scope change buffered for review</h3>
              <p className="mt-1 text-xs font-semibold text-[var(--muted)]">The latest client changes are calculated but not yet sent.</p>
              <div className="mt-4 grid gap-3 sm:grid-cols-2"><div className="rounded-lg border border-[var(--line)] bg-white p-3"><p className="text-[10px] font-extrabold uppercase tracking-[0.1em] text-[var(--muted)]">Pending price impact</p><p className="tabular mt-1 text-xl font-black">{money(openBufferPrice ?? 0, true)}</p></div><div className="rounded-lg border border-[var(--line)] bg-white p-3"><p className="text-[10px] font-extrabold uppercase tracking-[0.1em] text-[var(--muted)]">Pending timeline</p><p className="tabular mt-1 text-xl font-black">{(openBufferDays ?? 0) > 0 ? "+" : ""}{openBufferDays ?? 0} days</p></div></div>
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
  apiPrefix = "/api",
  reviewer = false,
  busy,
  onCommand,
  compact = false,
}: {
  data: DashboardSnapshot;
  demo: boolean;
  operatorKey: ApiCredential;
  apiPrefix?: string;
  reviewer?: boolean;
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
        `${apiPrefix}/messages/${encodeURIComponent(message.id)}`,
        operatorKey,
      );
      setMessageDetail(detail);
    } catch (caught) {
      // Older hosted API revisions may expose the dashboard metadata route but
      // not the bounded detail route. Keep the review usable with the trusted
      // metadata already on screen instead of surfacing a raw 404 modal.
      if (caught instanceof ApiError && caught.status === 404) {
        setMessageDetail({ ...message, body: "Message content is unavailable from this API revision.", body_format: "PLAIN", attachments: [] });
      } else {
        setMessageError(caught instanceof Error ? caught.message : "The selected message could not be loaded.");
      }
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
    <section className={`panel gmail-review-panel flex min-w-0 flex-col overflow-hidden ${compact ? "overview-inbox-panel" : "min-h-[31rem]"}`}>
      <div className="overview-panel-header flex flex-wrap items-start justify-between gap-4 px-5 py-4 sm:px-6">
        <div className="min-w-0">
          <p className="eyebrow">{reviewer ? "ScopeLock demo inbox" : "Gmail review"}</p>
          {reviewer ? <p className="mt-1 text-xs font-semibold text-[var(--muted)]">Shared test inbox · not your personal Gmail</p> : null}
        </div>
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
        <div className="mt-4 min-h-0 flex-1 overflow-y-auto px-5 pb-5 pr-4 sm:px-6 sm:pb-6 sm:pr-5">
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
        <div className="flex flex-1 flex-col items-center justify-center px-5 py-8 text-center sm:px-6">
          <span className="grid size-12 place-items-center rounded-full bg-[var(--surface-muted)] text-[var(--ink)]"><Mail size={21} /></span>
          <h3 className="mt-4 text-base font-black">{watch ? "Waiting for a project email" : reviewer ? "Demo inbox is ready" : "Gmail monitoring is not active"}</h3>
          <p className="mt-2 max-w-sm text-sm leading-6 text-[var(--muted)]">{watch ? reviewer ? "Send a project email to the shared ScopeLock demo inbox from this signed-in address. The agent will analyze it in the background." : "Project-linked messages will appear here after the Gmail event workflow records them." : reviewer ? "The owner manages Gmail monitoring. Your reviewer session only exposes messages linked to this signed-in email." : "Register Gmail notifications only after the OAuth and Pub/Sub checks are complete."}</p>
          {!watch ? (
            <div className="mt-5 w-full max-w-sm">
              {confirmWatch ? (
                <div className="rounded-lg border border-[var(--line-strong)] bg-[var(--surface-soft)] p-4 text-left">
                  <p className="text-sm font-extrabold">Start Gmail notifications?</p>
                  <p className="mt-2 text-xs leading-5 text-[var(--muted)]">This registers Gmail <code>users.watch</code> for the configured dedicated mailbox. It does not send email, but it begins Pub/Sub delivery.</p>
                  <div className="mt-4 grid grid-cols-2 gap-3">
                    <button type="button" onClick={() => setConfirmWatch(false)} className="min-h-10 rounded-lg border border-[var(--line-strong)] bg-white px-3 text-sm font-extrabold">Cancel</button>
                    <button type="button" disabled={busy || demo || reviewer} onClick={registerWatch} className="min-h-10 rounded-lg bg-[var(--ink)] px-3 text-sm font-extrabold text-white disabled:opacity-45">Confirm watch</button>
                  </div>
                </div>
              ) : (
                <button type="button" disabled={busy || demo || reviewer} onClick={() => setConfirmWatch(true)} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-[var(--ink)] px-4 text-sm font-extrabold text-white disabled:opacity-45"><Mail size={17} /> {demo ? "Demo fixture" : reviewer ? "Demo inbox is managed" : "Connect Gmail"}</button>
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
  apiPrefix = "/api",
  reviewer = false,
  operatorId,
  setOperatorId,
  busy,
  onCommand,
}: {
  data: DashboardSnapshot;
  demo: boolean;
  operatorKey: ApiCredential;
  apiPrefix?: string;
  reviewer?: boolean;
  operatorId: string;
  setOperatorId: (value: string) => void;
  busy: boolean;
  onCommand: (path: string, payload: Record<string, string>) => Promise<void>;
}) {
  const artifact = latestWorkspaceArtifact(data);
  const project = artifact ? data.projects.find((item) => item.id === artifact.project_id) : undefined;
  const actionCount = data.artifacts.filter((item) => REVIEW_STATUSES.has(item.status)).length + data.scope_buffers.filter((item) => item.status === "READY_TO_FINALIZE").length;
  const bufferedDelta = data.scope_buffers
    .filter((item) => item.status !== "FINALIZED")
    .reduce((sum, item) => sum + (item.net_price_delta_usd ?? data.scope_events.filter((event) => item.event_ids.includes(event.id)).reduce((delta, event) => delta + event.price_delta_usd, 0)), 0);
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

      <section className="overview-board mt-2 min-w-0">
        <div className="overview-inbox min-w-0">
          <GmailReviewPanel data={data} demo={demo} operatorKey={operatorKey} apiPrefix={apiPrefix} reviewer={reviewer} busy={busy} onCommand={onCommand} compact />
        </div>

        <section className="panel overview-review priority-review-panel min-w-0 overflow-hidden">
          <div className="overview-panel-header priority-review-header flex items-center justify-between gap-3 px-5 py-4 sm:px-6">
            <p className="eyebrow">Priority queue</p>
            <span className="text-xs font-extrabold text-[var(--muted)]">Current project</span>
          </div>
          {data.scope_buffers.filter((item) => item.status !== "FINALIZED").map((buffer) => (
            <div key={buffer.id} className="px-5 pt-4 sm:px-6">
              <BufferCard buffer={buffer} demo={demo} busy={busy} onCommand={onCommand} />
            </div>
          ))}
          {artifact ? <ArtifactReview artifact={artifact} project={project} inboxMessages={data.inbox_messages} demo={demo} operatorKey={operatorKey} apiPrefix={apiPrefix} compact operatorId={operatorId} setOperatorId={setOperatorId} busy={busy} onCommand={onCommand} /> : <div className="flex flex-1 items-center justify-center p-6"><EmptyState>No commercial artifact needs review.</EmptyState></div>}
        </section>
      </section>
    </div>
  );
}

function Settings({
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
  const artifact = latestWorkspaceArtifact(data);
  const defaultSopDraft = {
    version: artifact?.sop_version ?? "jvl-demo-v1",
    businessName: "JVL",
    proposalValidDays: "14",
    quietWindowMinutes: "60",
  };
  const sopDraftStorageKey = `${SOP_DRAFT_KEY_PREFIX}${defaultSopDraft.version}`;
  const [sopDraft, setSopDraft] = useState(() => {
    const parsed = readStoredJson<Partial<typeof defaultSopDraft>>(
      "session",
      sopDraftStorageKey,
    );
    const fields: Array<keyof typeof defaultSopDraft> = [
      "version",
      "businessName",
      "proposalValidDays",
      "quietWindowMinutes",
    ];
    if (parsed && fields.every((field) => typeof parsed[field] === "string")) {
      return { ...defaultSopDraft, ...parsed };
    }
    return defaultSopDraft;
  });
  const [sopSaved, setSopSaved] = useState(false);
  const [confirmWatch, setConfirmWatch] = useState(false);
  const watch = data.gmail_watch;
  const lineItems = artifact?.pricing_result.line_items ?? [];

  const updateSop = (field: keyof typeof sopDraft, value: string) => {
    setSopSaved(false);
    setSopDraft((current) => ({ ...current, [field]: value }));
  };

  const saveSopDraft = (event: FormEvent) => {
    event.preventDefault();
    writeStoredJson("session", sopDraftStorageKey, sopDraft);
    setSopSaved(true);
  };

  const registerWatch = () => {
    setConfirmWatch(false);
    void onCommand("/gmail/watch", {});
  };

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
      <section className="panel p-5 sm:p-6">
        <p className="max-w-2xl text-sm font-semibold leading-6 text-[var(--muted)]">SOP setting</p>

        <form onSubmit={saveSopDraft} className="mt-6 grid gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="grid gap-1.5 text-sm font-extrabold" htmlFor="sop-business-name">Business name<input id="sop-business-name" value={sopDraft.businessName} onChange={(event) => updateSop("businessName", event.target.value)} className="min-h-11 rounded-lg border border-[var(--line-strong)] bg-white px-3 text-sm font-normal" required /></label>
            <label className="grid gap-1.5 text-sm font-extrabold" htmlFor="sop-version">Catalog version<input id="sop-version" value={sopDraft.version} onChange={(event) => updateSop("version", event.target.value)} className="min-h-11 rounded-lg border border-[var(--line-strong)] bg-white px-3 text-sm font-normal" required /></label>
            <label className="grid gap-1.5 text-sm font-extrabold" htmlFor="sop-valid-days">Proposal validity (days)<input id="sop-valid-days" type="number" min="1" value={sopDraft.proposalValidDays} onChange={(event) => updateSop("proposalValidDays", event.target.value)} className="min-h-11 rounded-lg border border-[var(--line-strong)] bg-white px-3 text-sm font-normal" required /></label>
            <label className="grid gap-1.5 text-sm font-extrabold" htmlFor="sop-quiet-window">Quiet window (minutes)<input id="sop-quiet-window" type="number" min="1" value={sopDraft.quietWindowMinutes} onChange={(event) => updateSop("quietWindowMinutes", event.target.value)} className="min-h-11 rounded-lg border border-[var(--line-strong)] bg-white px-3 text-sm font-normal" required /></label>
          </div>

          <div className="rounded-lg border border-[var(--line)] bg-[var(--surface-soft)] p-4">
            <div className="flex items-center justify-between gap-3"><p className="text-xs font-extrabold uppercase tracking-[0.1em] text-[var(--muted)]">Active source</p><StatusPill status={artifact?.sop_version ? "CONFIGURED" : "NOT_CONFIGURED"} /></div>
            <p className="mt-2 text-sm font-black">config/jvl_sop.example.yaml</p>
            <p className="mt-1 text-xs leading-5 text-[var(--muted)]">The active catalog is versioned and validated at service startup. Saving here creates a reviewable draft; deployment is required before it becomes canonical.</p>
          </div>

          {lineItems.length ? (
            <div>
              <p className="text-xs font-extrabold uppercase tracking-[0.1em] text-[var(--muted)]">Current priced modules</p>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {lineItems.map((item) => <div key={item.module_key} className="flex items-center justify-between gap-3 rounded-lg border border-[var(--line)] bg-white px-3 py-3"><span className="min-w-0 truncate text-xs font-extrabold">{humanize(item.module_key)}</span><span className="tabular shrink-0 text-xs font-black">{money(item.subtotal_usd)}</span></div>)}
              </div>
            </div>
          ) : null}

          <div className="flex flex-col gap-3 border-t border-[var(--line)] pt-5 sm:flex-row sm:items-center sm:justify-between">
            <p role="status" className="text-xs leading-5 text-[var(--muted)]">{sopSaved ? "SOP draft saved for this session. Validate and deploy it to make it active." : "Draft changes do not alter accepted project baselines."}</p>
            <button type="submit" className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-[var(--ink)] px-4 text-sm font-extrabold text-white hover:bg-[var(--ink-strong)]"><Save size={16} aria-hidden="true" /> Save SOP draft</button>
          </div>
        </form>
      </section>

      <div className="grid content-start gap-4">
        <section className="panel p-5 sm:p-6">
          <div className="rounded-lg border border-[var(--line)] bg-[var(--surface-soft)] p-4">
            <div className="flex items-center justify-between gap-3"><p className="text-xs font-extrabold uppercase tracking-[0.1em] text-[var(--muted)]">Connection status</p><StatusPill status={watch ? "MONITORING" : "NOT_CONNECTED"} /></div>
            <p className="mt-3 text-sm font-black">{watch ? watch.mailbox : "No mailbox watch registered"}</p>
            <p className="mt-1 text-xs leading-5 text-[var(--muted)]">{watch ? `Watch expires ${time(watch.expiration)}.` : "Register the dedicated Gmail mailbox after OAuth and Pub/Sub configuration are verified."}</p>
          </div>
          {confirmWatch ? (
            <div className="mt-4 rounded-lg border border-[var(--line-strong)] bg-white p-4">
              <p className="text-sm font-extrabold">Register Gmail notifications?</p>
              <p className="mt-2 text-xs leading-5 text-[var(--muted)]">This starts Gmail <code>users.watch</code> for the configured mailbox. It does not send client email.</p>
              <div className="mt-4 grid grid-cols-2 gap-3"><button type="button" onClick={() => setConfirmWatch(false)} className="min-h-11 rounded-lg border border-[var(--line-strong)] bg-white px-3 text-sm font-extrabold">Cancel</button><button type="button" disabled={busy || demo} onClick={registerWatch} className="min-h-11 rounded-lg bg-[var(--ink)] px-3 text-sm font-extrabold text-white disabled:opacity-45">Confirm connection</button></div>
            </div>
          ) : <button type="button" disabled={busy || demo} onClick={() => setConfirmWatch(true)} className="mt-4 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-[var(--ink)] px-4 text-sm font-extrabold text-white disabled:opacity-45"><Mail size={16} aria-hidden="true" /> {watch ? "Renew Gmail watch" : demo ? "Demo fixture" : "Connect Gmail"}</button>}
          <p className="mt-4 flex items-start gap-2 text-xs leading-5 text-[var(--muted)]"><ShieldCheck size={15} className="mt-0.5 shrink-0 text-[var(--ink)]" /> Read-only and compose/send scopes are kept separate; commercial sends still require explicit approval.</p>
        </section>

      </div>
    </div>
  );
}

export type ReviewerSession = {
  token: string;
  email: string;
};

export function OperatorApp({
  view,
  reviewerSession,
  onReviewerSignOut,
}: {
  view: View;
  reviewerSession?: ReviewerSession;
  onReviewerSignOut?: () => void;
}) {
  const reviewer = Boolean(reviewerSession);
  const apiPrefix = reviewer ? "/api/reviewer" : "/api";
  const credential: ApiCredential = reviewerSession
    ? { kind: "reviewer", token: reviewerSession.token }
    : "";
  const [operatorKey, setOperatorKey] = useState("");
  const [operatorId, setOperatorIdState] = useState("");
  const [data, setData] = useState<DashboardSnapshot | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [demo, setDemo] = useState(false);
  const [scopeIntelligenceOpen, setScopeIntelligenceOpen] = useState(false);
  const previousSnapshotRef = useRef<DashboardSnapshot | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    return readStoredValue("local", SIDEBAR_COLLAPSED_KEY) === "true";
  });

  useEffect(() => {
    if (!notice && !error) return;
    const timer = window.setTimeout(() => {
      setNotice(null);
      setError(null);
    }, 5_000);
    return () => window.clearTimeout(timer);
  }, [notice, error]);

  const load = async (key: ApiCredential) => {
    const snapshot = await apiRequest<DashboardSnapshot>(
      `${apiPrefix}/dashboard`,
      key,
    );
    previousSnapshotRef.current = snapshot;
    setData(snapshot);
  };

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("demo") === "1") {
      setDemo(true);
      setData(demoDashboard);
      return;
    }
    if (reviewerSession) {
      setOperatorIdState(reviewerSession.email);
      void load({ kind: "reviewer", token: reviewerSession.token }).catch((caught) => {
        setError(caught instanceof Error ? caught.message : "The reviewer workspace could not be loaded.");
      });
      return;
    }
    const storedId = readStoredValue("session", OPERATOR_ID_KEY) ?? "";
    setOperatorIdState(storedId);
  }, [reviewerSession]);

  useEffect(() => {
    if (demo || (!reviewerSession && !operatorKey)) return;
    let active = true;
    let inFlight = false;
    const refresh = async () => {
      if (!active || inFlight || document.visibilityState === "hidden") return;
      inFlight = true;
      try {
        const snapshot = await apiRequest<DashboardSnapshot>(
          `${apiPrefix}/dashboard`,
          reviewerSession
            ? { kind: "reviewer", token: reviewerSession.token }
            : operatorKey,
        );
        if (active) {
          const previous = previousSnapshotRef.current;
          if (previous) {
            if (snapshot.inbox_messages.length > previous.inbox_messages.length) {
              setNotice("New client email received. Open Gmail review to read the message.");
            } else {
              const previousArtifactIds = new Set(previous.artifacts.map((artifact) => artifact.id));
              const newChangeOrder = snapshot.artifacts.find((artifact) => artifact.artifact_type === "CHANGE_ORDER" && !previousArtifactIds.has(artifact.id));
              if (newChangeOrder) setNotice("Updated proposal ready. Open the review packet to check the new price and timeline.");
            }
          }
          previousSnapshotRef.current = snapshot;
          setData(snapshot);
        }
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
  }, [apiPrefix, demo, operatorKey, reviewerSession]);

  const setOperatorId = (value: string) => {
    setOperatorIdState(value);
    writeStoredValue("session", OPERATOR_ID_KEY, value);
  };

  const toggleSidebar = () => {
    setSidebarCollapsed((current) => {
      const next = !current;
      writeStoredValue("local", SIDEBAR_COLLAPSED_KEY, String(next));
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
    if (reviewer) {
      onReviewerSignOut?.();
      return;
    }
    setOperatorKey("");
    setData(null);
    setNotice(null);
    setScopeIntelligenceOpen(false);
  };

  const refreshDashboard = async () => {
    if (demo || (!reviewerSession && !operatorKey)) return;
    setBusy(true);
    setError(null);
    try {
      await load(
        reviewerSession
          ? { kind: "reviewer", token: reviewerSession.token }
          : operatorKey,
      );
      setNotice("Dashboard refreshed.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The dashboard could not be refreshed.");
    } finally {
      setBusy(false);
    }
  };

  const onCommand = async (path: string, payload: Record<string, string>) => {
    if (demo || (!reviewerSession && !operatorKey)) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const requestPath = reviewer
        ? `${apiPrefix}${path}`
        : path;
      await apiRequest(requestPath, reviewer ? credential : operatorKey, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      await load(reviewer ? credential : operatorKey);
      setNotice("Action completed and the dashboard has been refreshed.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The action could not be completed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={`operator-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
      <AppHeader
        view={view}
        reviewer={reviewer}
        sidebarCollapsed={sidebarCollapsed}
        connected={Boolean(data)}
        demo={demo}
        busy={busy}
        onToggleSidebar={toggleSidebar}
        onRefresh={() => void refreshDashboard()}
        onScopeIntelligence={() => setScopeIntelligenceOpen(true)}
        onDisconnect={disconnect}
      />
      {!data ? reviewer ? (
        <main id="main-content" className="mx-auto flex min-h-[60vh] max-w-[760px] items-center justify-center px-6 py-16">
          <section className="panel w-full p-8 text-center">
            <span className="mx-auto grid size-12 place-items-center rounded-full bg-[var(--surface-muted)]"><Inbox size={22} /></span>
            <h1 className="mt-5 text-2xl font-black tracking-[-0.035em]">Loading your reviewer workspace</h1>
            <p className="mt-3 text-sm leading-6 text-[var(--muted)]">ScopeLock is checking the shared demo inbox for messages sent from {reviewerSession?.email}.</p>
            {error ? <p role="alert" className="mt-5 rounded-lg border border-[var(--line-dark)] bg-[var(--surface-muted)] px-4 py-3 text-left text-sm font-bold text-[var(--ink)]">{error}</p> : null}
          </section>
        </main>
      ) : <ConnectPanel busy={busy} error={error} onConnect={connect} /> : (
        <main id="main-content" className={`workspace-main mx-auto max-w-[1600px] px-4 py-6 sm:px-8 lg:px-8 lg:py-8 ${view === "overview" ? "overview-main" : ""}`}>
          {demo ? (
            <div className="overview-demo-banner mb-6 flex flex-col gap-3 rounded-lg border border-[var(--line-strong)] bg-[var(--surface-soft)] px-4 py-3 text-sm font-bold text-[var(--ink)] sm:flex-row sm:items-center sm:justify-between">
              <span className="flex min-w-0 items-center gap-2 break-words"><TriangleAlert size={17} className="shrink-0" /> Reviewed demo fixture—no live Gmail data or external actions.</span>
              <a href={view === "overview" ? "/" : `/${view}/`} className="underline underline-offset-4">Leave demo</a>
            </div>
          ) : null}
          {reviewer && !demo ? (
            <div className="mb-6 flex items-start gap-2 rounded-lg border border-[var(--line)] bg-[var(--surface-soft)] px-4 py-3 text-sm font-semibold text-[var(--ink)]">
              <Inbox size={17} className="mt-0.5 shrink-0" />
              <span><strong>ScopeLock demo inbox.</strong> This shared test workspace is not your personal Gmail inbox.</span>
            </div>
          ) : null}
          {notice || error ? (
            <div className="toast-stack" aria-live="polite" aria-atomic="true">
              {notice ? <div role="status" className="toast toast-success"><CheckCircle2 size={17} />{notice}</div> : null}
              {error ? <div role="alert" className="toast toast-error"><CircleAlert size={17} />{error}</div> : null}
            </div>
          ) : null}
          {data.warnings.length ? (
            <div className="mb-6 rounded-lg border border-[var(--line-strong)] bg-[var(--surface-soft)] px-4 py-3 text-sm text-[var(--ink)]">
              <p className="font-extrabold">Data warnings</p>
              <ul className="mt-2 list-disc pl-5">{data.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
            </div>
          ) : null}
          {view === "overview" ? <Overview data={data} demo={demo} operatorKey={reviewer ? credential : operatorKey} apiPrefix={apiPrefix} reviewer={reviewer} operatorId={operatorId} setOperatorId={setOperatorId} busy={busy} onCommand={onCommand} /> : null}
          {view === "settings" ? <Settings data={data} demo={demo} busy={busy} onCommand={onCommand} /> : null}
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

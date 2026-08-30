# ScopeLock — System Architecture

## 1. Architecture objective

Use the smallest architecture that demonstrates:

- autonomous event-driven execution;
- meaningful Gemini reasoning;
- explicit workflow state;
- deterministic commercial logic;
- safe tool use;
- observable execution;
- Google Cloud deployment.

---

## 2. High-level architecture

```text
CLIENT GMAIL
    |
    | incoming email
    v
Gmail users.watch
    |
    v
Cloud Pub/Sub
    |
    | push notification (historyId)
    v
Cloud Run — ScopeLock Backend
    |
    +--> Gmail History API / Messages API
    |
    +--> Deterministic inbound router
    |       |
    |       +--> IGNORE
    |       +--> ADK Requirement Analyzer (direct)
    |       +--> ADK Scope Analyzer (direct)
    |               |
    |               +--> typed semantic output
    |               +--> authoritative evidence references
    |
    +--> Deterministic SOP / Pricing Engine
    |
    +--> Proposal / Change Order Generator
    |
    +--> Firestore
    |       |
    |       +--> project state
    |       +--> canonical scope
    |       +--> scope events
    |       +--> pending ScopeBuffer
    |       +--> audit log
    |       +--> eval results
    |
    +--> Gmail Draft / Send Tool (approval-gated)
    |
    +--> Cloud Storage (optional artifact storage)
    |
    v
Vite React Review Dashboard
    |
    +--> approve / reject / edit
    +--> view evidence
    +--> finalize buffer
    +--> view eval / agent health
```

---

## 3. Cloud services

### Required / P0

#### Cloud Run
Two deployable services are acceptable:

1. `scopelock-api`
   - Python / ADK / Gmail webhook / application API.
2. `scopelock-web`
   - Vite-built React dashboard.

A single combined deployment is allowed if it materially reduces risk, but keep backend and UI code logically separated.

#### Firestore
Canonical application state.

#### Pub/Sub
Receives Gmail push notifications.

#### Vertex AI
Access Gemini `gemini-3.5-flash`.

### Optional
- Cloud Storage for generated proposal PDFs.
- Cloud Scheduler only to renew Gmail `watch` before expiration if needed.
- Cloud Trace / Logging for demo observability.

---

## 4. Gmail event flow

Important: Gmail push notifications do not contain the full message. They identify mailbox changes using a `historyId`.

P0 flow:

1. Configure `users.watch` on the authorized mailbox.
2. Gmail publishes to Pub/Sub.
3. Pub/Sub pushes to `/webhooks/gmail`.
4. Decode notification.
5. Compare notification history against stored `last_history_id`.
6. Call Gmail History API.
7. Resolve new message IDs.
8. Fetch message/thread.
9. Apply idempotency check (`gmail_message_id` unique).
10. Process only new inbound messages.
11. Persist the new checkpoint/history ID.

For hackathon reliability, use a dedicated Gmail demo account so unrelated inbox traffic cannot trigger workflows.

Production extension: label/filter-based routing.

---

## 5. Gmail OAuth

Prefer least-privilege scopes.

Desired capabilities:

- read inbound message/thread;
- create/update draft;
- send approved draft.

Avoid the broad `https://mail.google.com/` scope unless technically required.

For the single-user hackathon build:
- authorize one Gmail account;
- store refresh credentials securely (e.g. Secret Manager) rather than plaintext in source control.

Never commit tokens or client secrets.

### Pre-activation hold

The pre-Gmail flexibility gate and the Days 11–13 code gate passed on
2026-08-29. `scopelock.http_api` now exposes the authenticated Pub/Sub endpoint
and operator commands; application services own watch/history checkpoints,
approval-bound drafts/sends, and scope revision acceptance. Keep continuous
mailbox delivery disabled until the Day 11 real read, history-resolution,
duplicate-delivery, and same-thread checks pass. The agent gate passed on
2026-08-30 and the user explicitly unlocked the thin operator frontend; this
does not unlock automatic Gmail delivery.

OAuth files are ignored for local development. Hosted refresh-token JSON must
come from Secret Manager through `SCOPELOCK_GMAIL_TOKEN_JSON`; it must never be
placed in an image, agent session state, log, or source file. Operator commands
require a separate `X-ScopeLock-Operator-Key`, while Pub/Sub push requires a
verified Google OIDC token with the configured audience and exact push service
account.

The production runtime has no OIDC-disable setting. HTTP request bodies are
bounded, API documentation is disabled, external errors are redacted, and
operator secrets are checked using fixed-length constant-time digests. Cloud Run
must remain IAM-authenticated, with separate runtime and Pub/Sub push service
accounts and Secret Manager access limited to the runtime identity.

Pub/Sub processing records carry an atomic expiring worker lease. Active leases
block duplicate work, expired leases can be reclaimed after a crash, and Gmail
history checkpoints advance through monotonic compare-and-set updates so
concurrent events cannot roll the mailbox backward. Page/message/MIME/thread
limits fail closed to durable recovery instead of sending unbounded content to
ADK.

Commercial reply composition validates RFC headers and binds the recipient and
source message to the project's client and Gmail thread. Scope acceptance is a
separate human command, but it must cite a persisted inbound Gmail message from
that same client/thread; operator free text cannot create acceptance evidence.
The complete activation and incident controls are in
`docs/GMAIL_SECURITY_GATE.md`.

The Cloud Run container starts through `scopelock.cloud_run`, validates hosted
configuration without retaining secret values, runs as a non-root user, and
accepts only Secret Manager-injected token JSON and operator credentials.
Diagnostic proposal renders use `/tmp/scopelock-artifacts`; approved attachment
bytes come from the immutable Firestore-owned commercial record rather than an
ephemeral path. Deployment and IAM steps are in
`docs/CLOUD_RUN_DEPLOYMENT.md`.

The selected P0 packaging is one Cloud Run container with logically separated
applications. A pinned Node build stage exports the Vite React UI, the Python
runtime serves it through FastAPI, and browser requests use same-origin API
paths. The dashboard receives bounded, redacted projections; it never receives
raw email bodies, agent outputs, input hashes, credentials, or tool payloads.
The operator key is held only in page memory. Frontend controls call the same
approval-gated application endpoints used without the UI and contain no pricing,
timeline, transition, or send policy.

---

## 6. ADK role

ADK owns the agentic reasoning boundary, not the entire application.

Use Gemini for:
- requirement extraction from natural language;
- semantic mapping of requirements to SOP modules;
- scope-event classification;
- semantic comparison of new client request vs canonical scope;
- evidence-grounded rationale;
- ambiguity detection.

Use deterministic code for:
- price arithmetic;
- timeline arithmetic;
- state transitions;
- quiet-window / consolidation timing;
- approval gating;
- artifact versioning;
- Gmail idempotency;
- send authorization;
- buffer aggregation.

### Inbound normalization and routing

Application code normalizes Gmail before ADK sees a message. It prefers decoded
`text/plain`, falls back to sanitized HTML text, preserves Unicode/Thai, removes
obvious quoted history and signatures, records attachment metadata without
attachment contents, and keeps a hash of the unmodified Gmail resource. Model
context is bounded to 20,000 current-message characters and five prior messages
of 4,000 characters each.

`AgentRoute` is deterministic:

- duplicate, outbound, automated, or empty input → `IGNORE`;
- no project or no active scope → `REQUIREMENT_ANALYSIS`;
- active proposed/accepted ScopeVersion → `SCOPE_ANALYSIS`.

The production path selects the Requirement Analyzer or Scope Analyzer as the
ADK application root directly. The development root agent and its
`EXISTING_PROJECT` convention exist only for `adk web`, `adk run`, and native
eval interaction; they do not make production routing decisions.

---

## 7. ADK app and deterministic application boundaries

Suggested Python package shape:

```text
app/
  agent.py                   # ADK root_agent: ScopeLock
  sub_agents/
    requirement_analyzer.py  # P0 first agent
    scope_analyzer.py        # active after Requirement Analyzer passed evals
    reviewer.py              # optional, risk-triggered only
  tools/
    sop_tools.py
    context_tools.py

scopelock/
  domain/
    models.py
    enums.py
    state_machines.py
  services/
      gmail_service.py
      gmail_history_service.py
      sop_service.py
      pricing_engine.py
      timeline_engine.py
      scope_diff_service.py
      proposal_service.py
      scope_buffer_service.py
      approval_policy.py
      gmail_message_normalizer.py
      inbound_router.py
      inbound_processing_workflow.py
      adk_agent_gateway.py
      workflow_trajectory.py
      scope_run_boundary.py
      audit_service.py
  repositories/
      firestore_projects.py
      firestore_events.py
      firestore_runs.py

tests/
  unit/
  integration/
  eval/
```

Use `adk web .` and `adk run app` while developing agents. Do not create agents
when a service/function is enough, and never put pricing, approval, state
transitions, or Gmail send capabilities inside `app/` tools.

For production calls, `AdkAgentGateway` loads one immutable `AnalysisContext`
before invocation and places it in ADK session state. Tools may read only that
state. The context contains the normalized current message, bounded prior
messages, authoritative ScopeVersion when present, semantic SOP projection, and
SOP version. The semantic SOP contains only module keys, aliases, inclusions,
exclusions, dependencies, materiality, and quantity policy; prices and timeline
rules never cross the agent boundary.

ToolAction audit records retain operation name, IDs/hashes, catalog version,
duration, status, and error. They exclude credentials, complete email bodies,
catalog amounts, and timeline rules.

---

## 8. Frontend pages

P0 pages only:

### `/`
Project inbox / current projects
- project
- client
- lifecycle status
- current value
- pending scope delta
- action required

### `/projects/`
- current canonical scope
- proposal version
- price/timeline
- client thread events
- pending changes
- evidence
- approve / reject / finalize

P0 uses an interactive project selector on the static `/projects/` export
rather than generating an unbounded static route for every Firestore ID.

### `/evals`
- classification metrics
- false-negative count
- tool/trajectory success
- approval-gate violations (must be zero)
- recent eval runs

No marketing site is required before the core workflow is stable.

---

## 9. Proposal artifact

P0:
- deterministic HTML/data template rendered into a clean PDF;
- ReportLab is acceptable for reliability;
- attach to Gmail;
- store artifact metadata and checksum.

Every artifact has:
- `artifact_id`
- `project_id`
- `version`
- `type`
- `status`
- `created_at`
- `approved_at`
- `sent_at`
- `sha256`
- `gmail_message_id` when sent

---

## 10. Reliability / production discipline

### Idempotency
Unique keys:
- Gmail message ID;
- Pub/Sub event/message ID where available;
- artifact version;
- Gmail send action.

### Retry
Retry:
- Gmail reads;
- Vertex/Gemini transient failures;
- Firestore transient failures.

Do not blindly retry sends unless idempotency confirms the email was not already sent.

### Timeouts
Agent call and external API calls must have explicit timeouts.

### Audit
Every risky action must record:
- actor (`agent` / `user`);
- timestamp;
- input references;
- decision;
- tool/action;
- result;
- correlation ID.

### Failure behavior
If agent reasoning fails:
- do not send;
- persist failure;
- surface `NEEDS_REVIEW`.

---

## 11. Security boundary

Tools should be narrowly scoped.

The Scope Analyzer must not directly own Gmail send credentials.

Preferred pattern:

```text
Gemini / Agent
  -> proposes typed action
  -> policy engine validates state/approval
  -> Gmail service executes
```

This prevents prompt content from directly triggering a send.

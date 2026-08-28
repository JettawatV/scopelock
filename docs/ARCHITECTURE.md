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
Next.js Review Dashboard
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
   - Next.js dashboard.

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

The pre-Gmail flexibility gate passed on 2026-08-28, so OAuth client setup,
credential verification, History API integration, Pub/Sub delivery, and
`users.watch` implementation may proceed during Day 11. Keep continuous
mailbox delivery disabled until the Day 11 read, history-resolution,
duplicate-delivery, and same-thread checks pass. The frontend remains locked
until the Gmail agent path is reliable.

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

### `/projects/[id]`
- current canonical scope
- proposal version
- price/timeline
- client thread events
- pending changes
- evidence
- approve / reject / finalize

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

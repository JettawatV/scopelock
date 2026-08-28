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
    +--> ADK Scope Analyzer (Gemini 3.5 Flash)
    |       |
    |       +--> typed RequirementExtraction
    |       +--> typed ScopeDecision
    |       +--> evidence references
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

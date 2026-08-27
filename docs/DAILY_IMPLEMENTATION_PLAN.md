# ScopeLock — Daily Implementation Plan

## Purpose and sequencing

This plan turns the product, architecture, domain, agent, SOP, evaluation, and hackathon documents into a sequence of small, verifiable tasks.

The first stage is deliberately ADK-first: prove typed agent behavior, narrow tools, deterministic pricing/timeline, and evaluation locally before building a frontend. A day is complete only when its success criteria and evidence are recorded. If a pass gate fails, fix that day before moving forward.

The frozen P0 loop is the priority: inbound Gmail event → requirement analysis → deterministic proposal → user approval → same-thread send → scope monitoring → buffered revision/change order → approval → send. Do not add integrations or UI polish until the relevant gate below passes.

## Working rules

- Gemini/ADK interprets language; application code owns money, time, state, approvals, idempotency, and sends.
- Every commercial decision needs evidence from the client message, baseline scope, and applicable SOP rule.
- No agent tool may send email or directly mutate commercial state.
- Accepted scope versions are immutable. Before acceptance use proposal revisions; after acceptance use change orders.
- Use the ADK development toolkit and local fixtures for the early loop. Gmail, Firestore, Pub/Sub, Cloud Run, and UI come later.
- Use confirmed demo SOP values before recording. Values in the example SOP are placeholders.

## Daily plan

### Day 0 — Baseline and scope freeze

Tasks:

- Confirm the repository and Python/Node versions.
- Read the nine source documents and record this plan as the working execution checklist.
- Inspect existing `config/` and `evals/` assets; do not overwrite existing user work.
- Write a short P0/P1/post-hackathon boundary and a risk register.

Success criteria / evidence:

- Repository opens from a clean checkout.
- All required source documents are accounted for.
- `python --version`, package manager version, and required environment variables are documented.
- A decision log states: ADK first, no frontend before the backend gate, no autonomous commercial sends.

Pass gate: the team can explain the golden path and the forbidden behaviors in under two minutes.

### Day 1 — ADK development harness and typed contracts

Tasks:

- Scaffold the Python backend package and test runner.
- Configure Vertex AI/Gemini access through environment variables; keep secrets out of source control.
- Define Pydantic v2 models for `EvidenceRef`, normalized requirements, SOP selections, `RequirementAnalysis`, `ScopeEventProposal`, and `ScopeAnalysis`.
- Add one local ADK runner that accepts an email-like string and prints validated structured output.
- Store `agent_name`, model, prompt version, correlation ID, input hash, status, and error metadata for each run.

Success criteria / evidence:

- The golden initial email produces valid `RequirementAnalysis` output.
- Missing credentials fail clearly and never trigger a send.
- Invalid model output is rejected and recorded as `NEEDS_REVIEW`.
- A run fixture or test output proves prompt versioning and typed validation.

Pass gate: local ADK Requirement Analyzer test passes repeatedly with no untyped business-critical output.

### Day 2 — Narrow ADK tools and Requirement Analyzer

Tasks:

- Implement read-only tools for `get_sop_catalog()` and, using fixtures, recent thread context/current scope.
- Implement Requirement Analyzer instructions: select only existing module keys, cite evidence, identify assumptions/exclusions/missing information, and never calculate price.
- Add tool schemas and tool-call logging.
- Add prompt-injection and irrelevant-email fixtures.

Success criteria / evidence:

- Golden email maps only to valid SOP keys.
- Output includes source quotes for requirements and SOP references for selections.
- A request outside the catalog is rejected or marked ambiguous; no invented module or price appears.
- Tool trajectory is visible in the ADK development output.

Pass gate: 5 repeated runs preserve schema, valid module keys, evidence, and the no-price boundary.

### Day 3 — SOP validation and deterministic pricing

Tasks:

- Validate the SOP YAML/JSON at load time, including fixed and per-unit pricing, dependencies, inclusions, exclusions, aliases, and materiality rules.
- Implement `SOPService` and `PricingEngine`.
- Support fixed and per-unit rules only for P0.
- Reject unknown modules, invalid quantities, malformed rules, and LLM-provided totals.

Success criteria / evidence:

- Pricing is reproducible from the same SOP and selected modules.
- Unit tests cover fixed price, per-unit price, minimum units, invalid module, and duplicate module behavior.
- Every price-bearing line item points to an SOP module/rule.

Pass gate: zero pricing values originate from model prose; all pricing tests pass.

### Day 4 — Deterministic timeline, scope versions, and state machines

Tasks:

- Implement the documented timeline algorithm: base project duration plus non-parallel incremental module days, honoring dependencies and `parallelizable`.
- Define domain enums and explicit transitions for project, artifact, and scope-event states.
- Implement immutable `ScopeVersion` snapshots and proposal version numbering.
- Add tests for expansion, reduction, replacement, dependencies, and illegal transitions.

Success criteria / evidence:

- The same inputs always produce the same timeline and totals.
- No path goes from draft directly to sent.
- Accepted baselines cannot be mutated by ordinary update functions.
- Tests demonstrate correct pre-acceptance revision versus post-acceptance change-order behavior.

Pass gate: deterministic commerce and state-machine tests pass with an immutable-baseline test.

### Day 5 — Scope Analyzer and semantic classification evals

Tasks:

- Implement the second ADK agent with typed `ScopeAnalysis` output.
- Add fixtures for no-change, clarification, ambiguous, expansion, reduction, replacement, closure, and multiple changes.
- Require evidence for baseline comparison and SOP mapping.
- Add configurable confidence thresholds: ≥0.85, 0.60–0.84, and <0.60.

Success criteria / evidence:

- The dashboard-title rename is `NO_CHANGE` or `CLARIFICATION` with zero commercial delta.
- LINE/manager approval additions are material expansions with valid module keys.
- Low-confidence commercial cases become `NEEDS_REVIEW`.
- ADK output and application decisions remain separate and traceable.

Pass gate: the initial 20–30-case corpus runs locally and produces a baseline for accuracy, per-class precision/recall, expansion recall, invalid-module rate, and evidence coverage.

### Day 6 — ADK trajectory tests and safety suite

Tasks:

- Add ADK trajectory tests for initial proposal and scope expansion.
- Assert required tool ordering and forbidden pre-approval send behavior.
- Add deterministic tests for approval policy, failed agent runs, stale artifacts, and low-confidence changes.
- Add an explicit send stub that fails unless approval state is valid.

Success criteria / evidence:

- Initial trajectory ends at `AWAITING_USER_REVIEW`.
- Expansion trajectory ends at a buffered/consolidated artifact awaiting review.
- Approval-gate violations equal zero.
- Failed, ambiguous, or unapproved paths cannot call the send stub.

Pass gate: any safety invariant failure blocks all later integration work.

### Day 7 — Local vertical golden path without Gmail or UI

Tasks:

- Compose a local workflow using the golden email fixture and in-memory repositories.
- Run: analyze → validate SOP → calculate price/timeline → create proposal data → await approval.
- Add audit records for agent runs, decisions, tool actions, and artifacts.
- Render a basic proposal artifact using a deterministic template; include checksum metadata.

Success criteria / evidence:

- One command produces a complete, reviewable proposal from the fixture.
- Requirements, modules, line items, total, timeline, assumptions, exclusions, and evidence are visible.
- Audit output proves Gemini selected meaning while code calculated commerce.
- Re-running the workflow does not create conflicting versions.

Pass gate: the local vertical path passes repeatedly and is suitable for a screen recording.

### Day 8 — Scope buffer and revision logic

Tasks:

- Implement `ScopeBufferService` with event aggregation, net deltas, baseline reference, and 20-minute quiet-window metadata.
- Implement semantic closure and manual-finalize paths.
- Recalculate rather than duplicate an unapproved draft when a new message arrives.
- Implement proposal revision before acceptance and change order after acceptance.

Success criteria / evidence:

- Harmless clarification is recorded without a buffer.
- Two rapid material changes become one consolidated revision.
- Closure finalizes immediately for the demo scenario.
- New input invalidates a stale unapproved artifact while preserving history.

Pass gate: buffer/revision unit and integration tests pass, including reduction and replacement deltas.

### Day 9 — Local end-to-end demo scenario

Tasks:

- Run all golden scenes with local event fixtures: initial request, approval, same-thread reply stub, harmless clarification, LINE expansion, closure, revision approval.
- Decide and document whether the demo shows proposal revision before acceptance or change order after acceptance.
- Verify demo SOP values and expected deltas.
- Capture a short runbook with exact commands and expected state changes.

Success criteria / evidence:

- The scenario demonstrates event → reasoning → artifact → approval gate → scope drift → consolidated commercial impact.
- Expected price/timeline deltas match the confirmed SOP.
- Evidence distinguishes the clarification from the expansion.
- No UI is required yet; CLI/log output is sufficient for this gate.

Pass gate: local golden path is repeatable enough to proceed to external services.

### Day 10 — Firestore persistence and idempotent application workflow

Tasks:

- Add Firestore repositories for projects, scope versions, events, buffers, artifacts, agent runs, tool actions, and eval results.
- Add correlation IDs and unique keys for Gmail message IDs, Pub/Sub events, artifact versions, and send actions.
- Add retry/timeout boundaries for model and persistence operations.
- Replay the same event multiple times.

Success criteria / evidence:

- Firestore state matches the domain state machine after each step.
- Replay produces no duplicate project, scope event, artifact, or send action.
- Failed writes and model calls are visible and recoverable without sending.
- Accepted baseline remains immutable in stored data.

Pass gate: emulator or controlled project tests pass the replay and failure tests.

### Day 11 — Gmail OAuth, watch, Pub/Sub, and history resolution

Tasks:

- Configure a dedicated demo Gmail account with least-privilege scopes.
- Implement `users.watch`, Pub/Sub push endpoint, notification decoding, stored history checkpoint, History API resolution, and message parsing.
- Process only new inbound messages and associate continuation messages by thread.
- Keep token/secret handling outside source control.

Success criteria / evidence:

- Sending a real email to the demo mailbox creates a Firestore project/event without opening ScopeLock.
- History notifications resolve the correct message/thread.
- Duplicate notification/message delivery is idempotent.
- OAuth scopes and secret storage are documented.

Pass gate: real mailbox-to-backend trigger works twice, including a replay.

### Day 12 — Approval API and Gmail draft/send integration

Tasks:

- Implement review/approve/reject/edit endpoints or a temporary operator command.
- Create a Gmail draft in the original thread, then send only through an approval-validated deterministic service.
- Attach or link the deterministic proposal artifact.
- Record approval, draft, send, message ID, checksum, and audit events.

Success criteria / evidence:

- Initial inbound email → generated artifact → explicit approval → same-thread Gmail reply.
- Calling send without approval is rejected and logged.
- Repeating the send request does not duplicate the email.
- Sent artifact and message metadata are traceable.

Pass gate: approval-gated external send passes integration and replay tests.

### Day 13 — Real Gmail scope monitoring and revision send

Tasks:

- Run the clarification, expansion, and closure messages through the live thread.
- Persist ScopeEvents and ScopeBuffer updates.
- Generate the revision/change order and expose an operator approval path.
- Apply accepted commercial changes to a new canonical scope version only after approval/client acceptance rules are satisfied.

Success criteria / evidence:

- Clarification causes no commercial artifact.
- Expansion shows immediate deterministic price/timeline delta and waits for approval.
- Closure consolidates related changes into one artifact.
- Revision is sent in the same Gmail thread only after approval.

Pass gate: the full non-UI Gmail golden path passes end to end.

### Day 14 — Cloud Run deployment and observability

Tasks:

- Deploy the backend to Cloud Run.
- Configure Pub/Sub push, Firestore, Vertex AI, IAM, environment configuration, and logging.
- Add structured logs for correlation ID, agent, tool, project, state transition, and external action.
- Confirm Cloud Logging/Trace evidence is easy to show in the demo.

Success criteria / evidence:

- A real Gmail event reaches Cloud Run and completes the workflow.
- Cloud logs show ADK/tool execution and deterministic pricing steps.
- IAM is scoped to required services; secrets are not logged.
- Cloud Run retry behavior does not cause duplicate sends.

Pass gate: hosted backend golden path passes and cloud evidence is captured.

### Day 15 — Minimal review UI (only after all prior gates)

Tasks:

- Build only `/`, `/projects/[id]`, and `/evals`.
- Show action-required status, scope, price/timeline, deltas, evidence, artifacts, event history, audit trail, and approve/reject/finalize actions.
- Keep the UI thin; call backend policy-checked endpoints.
- Test the golden path at the target viewport and capture clean screenshots.

Success criteria / evidence:

- A reviewer can understand why a classification and price were chosen.
- Approval actions are explicit and cannot bypass backend policy.
- Scope history visibly distinguishes no-change from expansion.
- The UI adds no new business logic or unrestricted tool access.

Pass gate: a fresh reviewer can complete the approval flow without explanation.

### Day 16 — Final eval, hardening, and release candidate

Tasks:

- Run the full semantic corpus, deterministic suite, ADK trajectories, replay tests, and hosted golden path.
- Record measured metrics; do not use illustrative numbers.
- Test timeouts, transient failures, invalid SOP keys, stale drafts, low confidence, and rejected approvals.
- Freeze features and fix only release-blocking defects.

Success criteria / evidence:

- Golden path passes repeatedly.
- Expansion false negatives are reviewed; invalid module hallucination is zero for the release corpus.
- Unsupported commercial claims are zero in the golden path.
- Approval-gate violations are zero, duplicate sends are zero, and accepted baselines are never silently mutated.
- Eval results are persisted and visible.

Pass gate: all safety invariants and release criteria pass. Any failure returns work to the responsible day.

### Day 17 — Submission and four-minute demo polish

Tasks:

- Feature freeze.
- Update README with setup, architecture, data sources, limitations, and third-party/pre-existing disclosure.
- Finalize architecture diagram and demo runbook.
- Record a sub-four-minute demo whose first 10–15 seconds show the event starting the workflow.
- Show Cloud Run evidence, state changes, evidence-backed decisions, deterministic price, approval, and scope revision.

Success criteria / evidence:

- A clean checkout can follow the documented setup.
- The demo is one coherent scenario, not a feature tour.
- Judges can see autonomous execution, Gemini reasoning, deterministic commerce, human approval, persistent state, evaluation, and Google Cloud.
- No P1 feature or extra integration is included unless it is already stable and submission-critical.

Pass gate: submission package is reproducible and the demo communicates the value proposition without narration-heavy setup.

## Global release checklist

- [ ] Gemini 3.5 or newer and Google ADK are used for semantic reasoning.
- [ ] Cloud Run, Firestore, and Pub/Sub execution is visible.
- [ ] Initial proposal and revision/change-order sends require explicit approval.
- [ ] Pricing and timeline are deterministic and SOP-traceable.
- [ ] Accepted scope versions are immutable.
- [ ] Gmail/Pub/Sub/artifact/send idempotency is tested.
- [ ] Low-confidence and failed-agent paths become reviewable failures.
- [ ] 20–30 labeled cases and measured metrics are available.
- [ ] ADK trajectory tests cover required and forbidden actions.
- [ ] Golden demo passes repeatedly in under four minutes when presented.
- [ ] No Slack, Teams, WhatsApp, Drive, CRM, billing, multi-tenant, RAG, client portal, or unrelated analytics work has displaced P0.

## Definition of “move to the next task”

Move forward only when the current day has:

1. working implementation or fixture;
2. automated test where the behavior is deterministic;
3. ADK eval or labeled-case evidence where the behavior is semantic;
4. recorded logs/artifact/state evidence;
5. no open release-blocking safety failure.

If a criterion fails, mark the day `BLOCKED`, write the failing case, and keep the next day on hold until the evidence passes.

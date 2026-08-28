# ScopeLock — Daily Implementation Plan

## Purpose and sequencing

This plan turns the product, architecture, domain, agent, SOP, evaluation, and hackathon documents into a sequence of small, verifiable tasks.

The first stage is deliberately ADK-first: use the native ADK development toolkit (`adk web .`, `adk run app`, and `adk eval`) as the main development loop. Develop the visible `scopelock` root agent and its Requirement Analyzer sub-agent first, then prove typed agent behavior, narrow tools, deterministic pricing/timeline, and evaluation locally before building a frontend. A day is complete only when its success criteria and evidence are recorded. If a pass gate fails, fix that day before moving forward.

The frozen P0 loop is the priority: inbound Gmail event → requirement analysis → deterministic proposal → user approval → same-thread send → scope monitoring → buffered revision/change order → approval → send. Do not add integrations or UI polish until the relevant gate below passes.

## Working rules

- Gemini/ADK interprets language; application code owns money, time, state, approvals, idempotency, and sends.
- Every commercial decision needs evidence from the client message, baseline scope, and applicable SOP rule.
- No agent tool may send email or directly mutate commercial state.
- Accepted scope versions are immutable. Before acceptance use proposal revisions; after acceptance use change orders.
- Use the ADK development toolkit and local fixtures for the early loop. Gmail, Firestore, Pub/Sub, Cloud Run, and UI come later.
- Frontend/UI/UX is blocked until agents pass the local golden-path and safety gates through ADK.
- Use confirmed demo SOP values before recording. Values in the example SOP are placeholders.

## Current progress checklist

Last reviewed: **2026-08-28**

Current active day: **Day 11 — Gmail OAuth, watch, Pub/Sub, and History API**

Immediate next evidence: configure the dedicated Gmail demo account and least-privilege OAuth, then prove one real Pub/Sub notification resolves exactly one inbound Gmail message through the History API.

Next unlock: **Day 12 remains locked until the Day 11 live Gmail event gate is checked.**

### Completed implementation

- [x] Product, architecture, domain, agent, SOP, evaluation, implementation, hackathon, and golden-path documents reviewed.
- [x] Git repository initialized with secret-safe `.gitignore` rules.
- [x] ADK-standard root `app/`, `root_agent`, sub-agent, tool, deterministic application, test, and eval layout created.
- [x] ScopeLock root agent and Requirement Analyzer sub-agent load in ADK Web.
- [x] ADK loads the project ID and Vertex configuration from the root `.env`.
- [x] One-command `.env`-driven Google Cloud setup and verification script added.
- [x] Pydantic `RequirementAnalysis` structured output enforced.
- [x] Validated USD SOP catalog and read-only `get_sop_catalog()` tool implemented.
- [x] Fixture-only read-only project scope and Gmail thread tools implemented.
- [x] First golden-path run returned valid structured output, four valid SOP modules, Gmail/SOP evidence, and no model-generated pricing.
- [x] Requirement Analyzer v2 readiness policy implemented for the golden path.
- [x] Requirement mapping instruction updated to require ID plus human-readable description.
- [x] Day 0 risk register added with blocking risks and exit evidence.
- [x] Python 3.13.14 environment, 144-package lockfile, clean install, ADK discovery, and current 117-test suite verified.
- [x] Day 3 strict SOP validation, deterministic USD PricingEngine, immutable pricing records, and golden pricing fixture verified.
- [x] Day 4 deterministic timeline, explicit state transitions, immutable ScopeVersion records, and proposal/change-order numbering verified.
- [x] Day 5 typed Scope Analyzer and 25-case native ADK corpus verified with measured 100% exact classification, 100% evidence coverage, and 0% invalid modules in the recorded run.
- [x] Day 6 native ADK trajectories, approval/checksum policy, reviewable failure paths, and idempotent non-sending intent stub verified.
- [x] Day 7 complete local initial-proposal path, deterministic proposal artifact, checksum, audit trail, and idempotent replay verified.
- [x] Day 8 scope buffering, consolidation, stale-artifact preservation, revisions, change orders, reductions, and replacements verified.
- [x] Day 9 complete local post-acceptance change-order rehearsal verified in under four minutes without frontend or Gmail dependencies.
- [x] Day 10 repository contracts, Firestore 2.29.0 adapter, unique keys, CAS transactions, replay, concurrency, recovery, and immutable storage verified.
- [x] Frontend/UI work explicitly held until the ADK agent gates pass.

### Evidence gates

- [x] ADK Web v2 golden-path run returned `proposal_ready: true` on 2026-08-27.
- [x] Vertex AI API access is confirmed for the configured project by the successful v2 ADK run.
- [x] Every `mapped_requirement` in the v2 golden-path run includes both requirement ID and description.
- [x] Add the Day 0 risk register and record clean-install evidence.
- [x] Add application-owned `AgentRun` metadata and safe invalid-output/missing-credential tests.
- [x] Confirm `get_sop_catalog()` appears in the ADK trace before module selection.
- [x] Run the golden email five times with stable schema, valid module keys, evidence, and no pricing.
- [x] Test an irrelevant email, an ambiguous request, an out-of-catalog request, and a prompt-injection attempt.
- [x] Record the Requirement Analyzer baseline with native ADK evals.
- [x] Resolve the Python 3.13 environment requirement and pass the reproducible-install gate.
- [ ] Remove the preserved legacy `backend/` scaffold only after explicit approval.
- [x] Pass the Requirement Analyzer gate before starting deterministic pricing or any frontend work.
- [x] Pass the deterministic pricing gate with no model-controlled commercial values.

## How to use the daily checklists

- Status values are COMPLETE, ACTIVE, IN PROGRESS, LOCKED, or BLOCKED.
- Mark implementation complete only after the corresponding verification passes.
- Put the command, test output, trace screenshot, artifact path, or log link beside the evidence item.
- A later day stays LOCKED until the current move-on gate is checked.
- If a check fails, add the failure under that day, mark the day BLOCKED, and do not hide or delete the evidence.
- Current execution focus is Day 11. Days 0–10 are complete.

## Delivery phase gates

| Phase | Days | Outcome | Current state |
| --- | --- | --- | --- |
| A — ADK semantic foundation | 0–2 | Requirement Analyzer is typed, bounded, repeatable, and evaluated | COMPLETE |
| B — Local deterministic workflow | 3–9 | Pricing, timeline, approval policy, scope drift, and local golden path pass | COMPLETE |
| C — Google integrations | 10–14 | Firestore, Gmail, Pub/Sub, approval-gated sends, and Cloud Run pass | ACTIVE |
| D — UI and submission | 15–17 | Thin review UI, release evals, and four-minute demo are ready | LOCKED |

## Daily plan

### Day 0 — Baseline, environment, and scope freeze

Status: COMPLETE — reproducibility and risk evidence recorded on 2026-08-27.

Daily outcome: a secret-safe repository with a documented P0 boundary and reproducible Python environment.

Implementation checklist:

- [x] Confirm the working repository root.
- [x] Read the nine required product and architecture documents in AGENTS.md order.
- [x] Initialize Git and preserve existing user work.
- [x] Add secret-safe ignore rules for .env, credentials, virtual environments, ADK runtime files, and generated caches.
- [x] Record ADK-first development and the frontend hold in project documentation.
- [x] Record the prohibition on autonomous commercial sends.
- [x] Confirm the P0, P1, and post-hackathon boundaries from the source documents.
- [x] Add a concise risk register covering credentials, model variability, duplicate events/sends, scope creep, and demo reliability.
- [x] Create or rebuild the project virtual environment with Python 3.13.
- [x] Install the project from a clean environment and record the exact setup commands.
- [x] Defer Node/frontend setup explicitly until the Day 15 unlock gate.

Verification and success checklist:

- [x] python --version reports Python 3.13.x inside the project environment.
- [x] A clean dependency install completes without undeclared packages.
- [x] Git ignores the local .env and credential artifacts.
- [x] The team can describe the frozen Gmail-to-proposal-to-revision loop.
- [x] The team can name the forbidden P0 behaviors in under two minutes.

Evidence to record:

- [x] Source documents and execution rules are linked from the repository.
- [x] Git repository and ignore rules exist.
- [x] Python 3.13.14, ADK 2.8.0, clean-install commands, and 14 passing tests are recorded in the README.
- [x] Risk register: `docs/RISK_REGISTER.md`.

Move-on gate:

- [x] DAY 0 PASS — repository, scope boundary, risk register, Python 3.13, and clean-install evidence are all confirmed.

### Day 1 — ADK development harness and typed RequirementAnalysis contract

Status: COMPLETE — native invocation, audit records, and safe failure evidence passed on 2026-08-27.

Daily outcome: ADK can discover ScopeLock, invoke Gemini through Vertex AI, and validate the response as a typed RequirementAnalysis.

Implementation checklist:

- [x] Create the ADK-standard project-root app package.
- [x] Export an App whose name matches the discoverable app directory.
- [x] Create the visible scopelock root agent.
- [x] Create and register the requirement_analyzer sub-agent.
- [x] Create the separate scopelock package for deterministic application code.
- [x] Create unit, integration, and native ADK eval directories.
- [x] Load the root .env without committing secrets.
- [x] Configure Vertex AI project, location, and model through environment variables.
- [x] Add an environment-driven Google Cloud setup and verification script.
- [x] Define typed EvidenceRef, NormalizedRequirement, SOPModuleSelection, and RequirementAnalysis models.
- [x] Attach RequirementAnalysis as the sub-agent output schema.
- [x] Prove ADK Web can discover and invoke the app.
- [x] Prove `adk run app` can discover and invoke the app from the repository root.
- [x] Add an application-owned AgentRun record containing correlation ID, agent name, model, prompt version, input hash, status, validated output, error, and timestamps.
- [x] Add application-owned ToolAction records and a documented native ADK trace.
- [x] Add a controlled invalid-output path that becomes NEEDS_REVIEW.

Verification and success checklist:

- [x] The golden email returns a schema-valid RequirementAnalysis.
- [x] The Vertex configuration is loaded from the project .env.
- [x] Secrets are absent from tracked files.
- [x] Missing project configuration fails clearly, persists a FAILED run with zero tool actions, and cannot invoke any send path.
- [x] Invalid model output is rejected rather than silently accepted.
- [x] A test proves prompt version and input hash are attached to the run record.
- [x] A test proves business-critical model output cannot bypass Pydantic validation.

Evidence to record:

- [x] ADK discovery test exists.
- [x] Typed contract unit test exists.
- [x] Successful ADK Web golden response captured on 2026-08-27.
- [x] AgentRun and ToolAction evidence: `docs/evidence/DAY_1_ADK_RUN_EVIDENCE.md`.
- [x] Invalid-output and missing-configuration evidence: `docs/evidence/DAY_1_ADK_RUN_EVIDENCE.md`; 14 tests passed.

Move-on gate:

- [x] DAY 1 PASS — typed output, configuration, run metadata, and safe failure behavior are all proven.

### Day 2 — Narrow ADK tools and Requirement Analyzer evaluation

Status: COMPLETE — reviewed fixtures, native ADK eval, and edge-case evidence passed on 2026-08-27.

Daily outcome: Requirement Analyzer repeatedly selects only valid SOP modules, cites evidence, resists unsafe instructions, and never calculates commerce.

Implementation checklist:

- [x] Implement read-only get_sop_catalog.
- [x] Implement fixture-only get_current_scope.
- [x] Implement fixture-only get_recent_thread_context.
- [x] Validate the USD SOP catalog before exposing it to the agent.
- [x] Require get_sop_catalog before module selection in the v2 prompt.
- [x] Require current-email and SOP evidence.
- [x] Require mapped_requirement to include requirement ID and description.
- [x] Define the golden-path proposal-readiness policy.
- [x] Prohibit price, total cost, timeline, state mutation, and email sends in the agent instruction.
- [x] Add a native ADK eval-set scaffold.
- [x] Confirm the actual ADK trace calls get_sop_catalog before the model selects modules.
- [x] Add reviewed fixtures for irrelevant email, ambiguous request, out-of-catalog request, and prompt injection.
- [x] Define expected assertions for every edge-case fixture.
- [x] Promote reviewed cases into the native ADK eval set.

Verification and success checklist:

Golden-path repeatability:

- [x] Run 1 returns proposal_ready true.
- [x] Run 1 returns the four expected valid SOP module keys.
- [x] Run 1 includes requirement ID plus description in every mapping.
- [x] Run 1 includes Gmail evidence and SOP evidence.
- [x] Run 1 contains no model-generated price or timeline.
- [x] Run 2 passes the same assertions through native `adk run app`.
- [x] Run 3 passes the same assertions through the application-owned audited runner.
- [x] Run 4 passes the same assertions through native `adk run app` after strict-schema hardening.
- [x] Run 5 passes the same assertions.

Edge-case behavior:

- [x] Irrelevant email is classified as not a project request or routed to review.
- [x] Ambiguous request does not invent quantities, modules, price, or timeline.
- [x] Out-of-catalog request is surfaced as unsupported or missing critical information.
- [x] Prompt injection cannot override the SOP-only, no-commerce, or no-send boundaries.
- [x] Every selected module key exists in the loaded SOP.
- [x] Every selected module contains both message and SOP evidence.
- [x] Native ADK eval completes and detailed results are reviewed.

Evidence to record:

- [x] V2 golden response captured on 2026-08-27.
- [x] ADK trace evidence: `docs/evidence/DAY_1_ADK_RUN_EVIDENCE.md`.
- [x] Five-run results table or artifact: `docs/evidence/DAY_1_ADK_RUN_EVIDENCE.md` (runs 1–4) and `docs/evidence/DAY_2_REQUIREMENT_EVAL_EVIDENCE.md` (run 5).
- [x] Edge-case eval output: `docs/evidence/DAY_2_REQUIREMENT_EVAL_EVIDENCE.md`.
- [x] Native ADK eval command and result: `docs/evidence/DAY_2_REQUIREMENT_EVAL_EVIDENCE.md`.

Move-on gate:

- [x] DAY 2 PASS — all five golden runs, all four edge cases, valid tool ordering, native eval, evidence coverage, and the no-commerce boundary pass.

### Day 3 — SOP validation and deterministic pricing

Status: COMPLETE — strict SOP validation and all deterministic pricing tests passed on 2026-08-27.

Daily outcome: application code converts validated SOP selections into reproducible USD line items and totals.

Implementation checklist:

- [x] Load the SOP catalog through typed Pydantic models.
- [x] Support fixed and per-unit pricing schemas only.
- [x] Reject unsupported pricing-rule types.
- [x] Validate unique SOP module keys.
- [x] Validate non-negative USD amounts and minimum units.
- [x] Validate dependency keys, aliases, inclusions, exclusions, and materiality settings.
- [x] Implement a PricingEngine separate from all agents.
- [x] Accept only module keys and quantities, never model totals.
- [x] Normalize duplicate module selections according to one documented policy.
- [x] Produce immutable price line items with module key, quantity, unit rule, unit amount, subtotal, and SOP version.
- [x] Reject unknown modules, zero/negative quantities, malformed rules, and currency mismatches.
- [x] Add an explicit USD currency field to pricing results.

Verification and success checklist:

- [x] Fixed-price module test passes.
- [x] Per-unit module test passes.
- [x] Minimum-unit test passes.
- [x] Duplicate-module policy test passes.
- [x] Unknown-module and invalid-quantity tests fail safely.
- [x] Same SOP version and selections always produce the same total.
- [x] Every price line can be traced to one SOP rule.
- [x] No model output field can override a calculated amount.

Evidence to record:

- [x] Pricing test command and passing output: `docs/evidence/DAY_3_PRICING_EVIDENCE.md` — 32 focused tests and 51 full-suite tests passed.
- [x] Golden-path expected line items and total fixture: `tests/fixtures/pricing_golden_path.json` — USD 5,650 from four SOP modules.
- [x] Example trace from module selection to SOP rule to subtotal: `docs/evidence/DAY_3_PRICING_EVIDENCE.md`.

Move-on gate:

- [x] DAY 3 PASS — all pricing tests pass and zero commercial values originate from model prose.

### Day 4 — Deterministic timeline, immutable scope versions, and state machines

Status: COMPLETE — deterministic timeline, state, and immutable-version gates passed on 2026-08-28.

Daily outcome: duration and workflow transitions are deterministic, legal, and unable to mutate an accepted baseline.

Implementation checklist:

- [x] Implement the documented base-duration plus non-parallel incremental-days algorithm.
- [x] Resolve and validate module dependencies before calculating duration.
- [x] Honor each module parallelizable rule.
- [x] Define project, artifact, proposal, change-order, and scope-event enums.
- [x] Define allowed state transitions in code.
- [x] Reject illegal transitions with a typed domain error.
- [x] Implement immutable ScopeVersion snapshots.
- [x] Implement proposal and change-order version numbering.
- [x] Separate pre-acceptance proposal revision from post-acceptance change order.
- [x] Include SOP version and calculation inputs in every commercial artifact.

Verification and success checklist:

- [x] Same inputs always produce the same duration.
- [x] Dependency-order and parallelizable-module tests pass.
- [x] Draft cannot transition directly to sent.
- [x] Rejected or stale artifacts cannot be approved or sent.
- [x] Accepted ScopeVersion cannot be edited in place.
- [x] Pre-acceptance change creates a proposal revision.
- [x] Post-acceptance change creates a change order.

Evidence to record:

- [x] Timeline test output: `docs/evidence/DAY_4_TIMELINE_AND_STATE_EVIDENCE.md`.
- [x] State-transition matrix and test output: `scopelock/domain/state_machines.py` and `docs/evidence/DAY_4_TIMELINE_AND_STATE_EVIDENCE.md`.
- [x] Immutable-baseline test output: `docs/evidence/DAY_4_TIMELINE_AND_STATE_EVIDENCE.md`.

Move-on gate:

- [x] DAY 4 PASS — deterministic timeline, legal transitions, and immutable-baseline tests all pass.

### Day 5 — Scope Analyzer and semantic classification corpus

Status: COMPLETE — reviewed 25-case native ADK corpus and measured semantic metrics passed on 2026-08-28.

Daily outcome: a second typed ADK agent compares new messages with accepted scope and proposes evidence-backed scope events.

Implementation checklist:

- [x] Define typed ScopeEventProposal and ScopeAnalysis contracts.
- [x] Implement the scope_analyzer ADK sub-agent.
- [x] Expose only read-only baseline, thread-context, and SOP tools.
- [x] Require evidence from the current message, accepted baseline, and SOP when applicable.
- [x] Add labels for NO_CHANGE, CLARIFICATION, AMBIGUOUS, EXPANSION, REDUCTION, REPLACEMENT, and CLOSURE.
- [x] Add configurable high, medium, and low confidence thresholds.
- [x] Route low-confidence commercial cases to NEEDS_REVIEW.
- [x] Prevent the agent from calculating commercial deltas.
- [x] Create 20–30 reviewed labeled cases covering all classes and multiple-change messages.

Verification and success checklist:

- [x] Dashboard-title rename produces NO_CHANGE or CLARIFICATION and zero proposed commercial change.
- [x] LINE integration request produces EXPANSION with a valid module key.
- [x] Manager-approval request produces the expected material classification.
- [x] Reduction and replacement cases reference the affected baseline requirements.
- [x] Ambiguous and low-confidence cases require human review.
- [x] Invalid-module rate and evidence coverage are calculated from the corpus.
- [x] Accuracy, per-class precision/recall, and expansion recall are recorded without invented metrics.

Evidence to record:

- [x] Labeled corpus path and reviewer: `tests/fixtures/scope_analyzer_cases.json`; specification review recorded in the fixture metadata.
- [x] Native ADK eval output: `docs/evidence/DAY_5_SCOPE_ANALYZER_EVIDENCE.md` — 25 passed, 0 failed.
- [x] Baseline metrics report: `docs/evidence/DAY_5_SCOPE_METRICS.json` and `docs/evidence/DAY_5_SCOPE_ANALYZER_EVIDENCE.md`.

Move-on gate:

- [x] DAY 5 PASS — the reviewed corpus runs and measured semantic metrics are recorded with no unreviewed commercial action.

### Day 6 — ADK trajectories and approval safety suite

Status: COMPLETE — native ADK trajectory and deterministic approval safety gates passed on 2026-08-28.

Daily outcome: tests prove required tool order and make all unapproved commercial sends impossible.

Implementation checklist:

- [x] Add the initial-proposal ADK trajectory case.
- [x] Add the scope-expansion ADK trajectory case.
- [x] Assert required read-only tool ordering.
- [x] Assert forbidden tools/actions before approval.
- [x] Implement a deterministic approval policy service.
- [x] Implement a send stub that rejects missing, stale, rejected, or mismatched approval.
- [x] Add tests for failed model runs, malformed outputs, low confidence, stale artifacts, and repeated send requests.
- [x] Add correlation and idempotency keys to external-action intents.

Verification and success checklist:

- [x] Initial trajectory stops at AWAITING_USER_REVIEW.
- [x] Expansion trajectory stops at a buffered or consolidated artifact awaiting review.
- [x] Missing approval cannot call the send stub.
- [x] Approval for an old checksum cannot send a newer artifact.
- [x] Repeated send requests result in one send intent.
- [x] Failed or ambiguous agent runs produce reviewable failures.
- [x] Approval-gate violations equal zero.

Evidence to record:

- [x] ADK trajectory report: `docs/evidence/DAY_6_TRAJECTORY_AND_APPROVAL_EVIDENCE.md` — 2 passed, 0 failed.
- [x] Approval-policy test output: `docs/evidence/DAY_6_TRAJECTORY_AND_APPROVAL_EVIDENCE.md`.
- [x] Forbidden-action test output: `docs/evidence/DAY_6_TRAJECTORY_AND_APPROVAL_EVIDENCE.md`.

Move-on gate:

- [x] DAY 6 PASS — every safety invariant passes; any failure blocks all integrations and UI work.

### Day 7 — Local initial-proposal vertical path

Status: COMPLETE — local deterministic proposal, audit, artifact, and replay gates passed on 2026-08-28.

Daily outcome: one local command turns the golden email into a complete deterministic proposal awaiting approval.

Implementation checklist:

- [x] Implement in-memory repositories for the local workflow.
- [x] Compose analyze → validate SOP → price → timeline → proposal artifact → await approval.
- [x] Record AgentRun, ScopeDecision, ToolAction, state transition, and artifact events.
- [x] Generate a deterministic proposal data model.
- [x] Render a basic proposal artifact from a fixed template.
- [x] Add artifact checksum and source-version metadata.
- [x] Ensure reruns use an idempotency key and do not create conflicting versions.
- [x] Add a single documented local command for the workflow.

Verification and success checklist:

- [x] Proposal contains requirements, modules, line items, USD total, timeline, assumptions, exclusions, and evidence.
- [x] Model output contains semantic selections but no calculated commercial fields.
- [x] Application logs show deterministic pricing and timeline steps.
- [x] Artifact checksum matches the approved proposal data.
- [x] A rerun produces the same result without a conflicting proposal version.
- [x] Workflow ends at AWAITING_USER_REVIEW.

Evidence to record:

- [x] Local command and console output: `docs/evidence/DAY_7_LOCAL_PROPOSAL_EVIDENCE.md`.
- [x] Generated proposal artifact: `artifacts/local_workflow/project-2d8777f70cf0f48f33b51922/proposal-v1.md` (generated/ignored) and Day 7 evidence.
- [x] Audit record sample: `tests/integration/test_initial_proposal_workflow.py` and Day 7 evidence.

Move-on gate:

- [x] DAY 7 PASS — the local initial-proposal path passes repeatedly and is screen-recording ready.

### Day 8 — Scope buffer, revision, and change-order logic

Status: COMPLETE — deterministic buffering and immutable-history gates passed on 2026-08-28.

Daily outcome: related material changes consolidate without losing history or mutating the accepted baseline.

Implementation checklist:

- [x] Implement ScopeBufferService.
- [x] Store baseline scope-version reference on every buffered event.
- [x] Aggregate additions, reductions, replacements, and net deltas.
- [x] Implement configurable quiet-window metadata.
- [x] Implement explicit semantic closure.
- [x] Implement manual finalize.
- [x] Recalculate an existing unapproved draft when new input arrives.
- [x] Preserve invalidated artifact history and checksums.
- [x] Generate proposal revisions before acceptance.
- [x] Generate change orders after acceptance.

Verification and success checklist:

- [x] Harmless clarification creates an event but no commercial buffer.
- [x] Two rapid material changes produce one consolidated artifact.
- [x] Closure finalizes immediately in the demo fixture.
- [x] Manual finalize produces the same deterministic result.
- [x] New input invalidates the stale draft without deleting it.
- [x] Reduction and replacement deltas are correct.
- [x] Accepted baseline remains unchanged until the approved change is accepted.

Evidence to record:

- [x] Buffer unit-test output: `docs/evidence/DAY_8_SCOPE_BUFFER_EVIDENCE.md` — 5 focused tests passed.
- [x] Consolidation integration-test output: `docs/evidence/DAY_8_SCOPE_BUFFER_EVIDENCE.md` and `tests/integration/test_local_golden_path.py`.
- [x] Before/after scope-version evidence: accepted USD 5,650 / 5 days; proposed USD 7,150 / 10 days in Day 8 evidence.

Move-on gate:

- [x] DAY 8 PASS — buffer, consolidation, reduction, replacement, and immutable-history tests pass.

### Day 9 — Complete local golden-path rehearsal

Status: COMPLETE — full fixture-driven rehearsal and four-minute gate passed on 2026-08-28.

Daily outcome: the entire judging story works locally with fixtures and no frontend dependency.

Implementation checklist:

- [x] Run the initial client email fixture.
- [x] Generate and approve the initial proposal through a deterministic operator command.
- [x] Simulate the same-thread client reply.
- [x] Run the harmless clarification fixture.
- [x] Run the material expansion fixture.
- [x] Run the closure fixture.
- [x] Generate and approve the consolidated revision or change order.
- [x] Choose and document whether the demo uses a pre-acceptance revision or post-acceptance change order.
- [x] Confirm the demo SOP values and expected USD/timeline deltas.
- [x] Write the exact local demo runbook and expected state after each action.

Verification and success checklist:

- [x] The story shows event, reasoning, deterministic artifact, approval, scope drift, consolidation, and second approval.
- [x] Clarification and expansion produce different evidence-backed classifications.
- [x] Price and timeline deltas match the confirmed SOP fixture.
- [x] No commercial send/action occurs without approval.
- [x] The workflow can be repeated from a clean local state.
- [x] The non-UI rehearsal fits comfortably within the four-minute demo budget.

Evidence to record:

- [x] Passing end-to-end local test output: `docs/evidence/DAY_9_LOCAL_GOLDEN_PATH_EVIDENCE.md` — 3 integration tests passed.
- [x] Timed rehearsal result: 0.010972 seconds in the recorded fixture run.
- [x] Demo runbook path: `docs/LOCAL_DEMO_RUNBOOK.md`.

Move-on gate:

- [x] DAY 9 PASS — the complete local golden path is repeatable enough to start Google service integrations.

### Day 10 — Firestore persistence and idempotent application workflow

Status: COMPLETE — repository, Firestore adapter, replay, concurrency, recovery, and immutability gates passed on 2026-08-28.

Daily outcome: persistent state matches the domain model and duplicate events cannot duplicate business actions.

Implementation checklist:

- [x] Define Firestore collections and document ownership for projects, scope versions, events, buffers, artifacts, agent runs, tool actions, approvals, sends, and eval results.
- [x] Implement repository interfaces before cloud-specific adapters.
- [x] Implement Firestore adapters.
- [x] Add correlation IDs to every workflow.
- [x] Add unique keys for Gmail message, Gmail thread, history record, Pub/Sub event, artifact version, approval, and send action.
- [x] Add transaction or compare-and-set protection where races are possible.
- [x] Add model, persistence, and external-service retry/timeout boundaries.
- [x] Add emulator or controlled-project fixtures.

Verification and success checklist:

- [x] Stored state matches the explicit state machine after every step.
- [x] Replaying one event creates no duplicate project, scope event, artifact, approval, or send intent.
- [x] Failed writes remain recoverable and cannot trigger a send.
- [x] Accepted scope versions remain immutable in storage.
- [x] Concurrent duplicate handling resolves to one canonical result.

Evidence to record:

- [x] Firestore schema/reference path: `docs/FIRESTORE_SCHEMA.md`.
- [x] Replay and concurrency test output: `docs/evidence/DAY_10_FIRESTORE_AND_REPLAY_EVIDENCE.md`.
- [x] Failure-recovery test output: `docs/evidence/DAY_10_FIRESTORE_AND_REPLAY_EVIDENCE.md`.

Move-on gate:

- [x] DAY 10 PASS — persistence, replay, concurrency, and immutable-baseline tests pass.

### Day 11 — Gmail OAuth, watch, Pub/Sub, and History API

Status: ACTIVE — unlocked after the Day 10 persistence gate passed on 2026-08-28.

Daily outcome: a real inbound Gmail message wakes ScopeLock and resolves exactly one new thread message.

Implementation checklist:

- [ ] Create or confirm the dedicated demo Gmail account.
- [ ] Configure the least-privilege Gmail OAuth scopes.
- [ ] Store OAuth client configuration and tokens outside source control.
- [ ] Configure the Pub/Sub topic and push subscription.
- [ ] Implement Gmail users.watch setup and renewal tracking.
- [ ] Implement the Pub/Sub push endpoint and notification decoding.
- [ ] Persist the last processed Gmail history checkpoint.
- [ ] Resolve notifications through the Gmail History API.
- [ ] Parse sender, recipients, subject, body, message ID, thread ID, and timestamps.
- [ ] Ignore sent mail and unrelated mailbox changes.
- [ ] Associate continuation messages with the correct project/thread.

Verification and success checklist:

- [ ] A real inbound email creates one Firestore project/event without opening ScopeLock.
- [ ] The history ID resolves the expected message and thread.
- [ ] Replayed Pub/Sub delivery creates no duplicate record or artifact.
- [ ] A second real message in the same thread attaches to the same project.
- [ ] OAuth scopes and secret handling are documented.
- [ ] Watch expiration and renewal behavior are visible.

Evidence to record:

- [ ] Sanitized Gmail/Pub/Sub configuration record: ____________________.
- [ ] First real inbound-event logs: ____________________.
- [ ] Replay and same-thread test output: ____________________.

Move-on gate:

- [ ] DAY 11 PASS — mailbox-to-backend triggering works twice, including duplicate delivery and same-thread continuation.

### Day 12 — Approval API and Gmail draft/send integration

Status: LOCKED.

Daily outcome: an operator can review an artifact and send it in the original Gmail thread only after explicit approval.

Implementation checklist:

- [ ] Implement read, approve, reject, and edit/revise application commands or endpoints.
- [ ] Bind approval to artifact ID, version, checksum, approver, and timestamp.
- [ ] Implement Gmail draft creation in the original thread.
- [ ] Implement a deterministic send service behind approval policy.
- [ ] Attach or link the deterministic proposal artifact.
- [ ] Add send idempotency keys.
- [ ] Record approval, draft, send attempt, Gmail message ID, thread ID, checksum, result, and error.
- [ ] Prevent agent tools from calling Gmail send directly.

Verification and success checklist:

- [ ] Initial inbound email can reach generated artifact and explicit approval.
- [ ] Approved artifact sends in the original Gmail thread.
- [ ] Missing, rejected, stale, or checksum-mismatched approval is rejected and logged.
- [ ] Repeating the send request does not duplicate the email.
- [ ] Editing an artifact invalidates the previous approval.
- [ ] Sent message and artifact are traceable to the exact approved bytes/data.

Evidence to record:

- [ ] Approval-policy integration test: ____________________.
- [ ] Same-thread Gmail send evidence: ____________________.
- [ ] Duplicate-send prevention output: ____________________.

Move-on gate:

- [ ] DAY 12 PASS — external sends are same-thread, traceable, idempotent, and impossible without current explicit approval.

### Day 13 — Live Gmail scope monitoring and revision send

Status: LOCKED.

Daily outcome: real follow-up messages become scope events, consolidate correctly, and produce an approval-gated revision.

Implementation checklist:

- [ ] Send the harmless clarification through the live Gmail thread.
- [ ] Send the material expansion through the same thread.
- [ ] Send the closure message through the same thread.
- [ ] Persist every ScopeEvent and ScopeBuffer update.
- [ ] Recalculate deterministic commercial impact immediately after material input.
- [ ] Consolidate related changes on closure or finalize.
- [ ] Expose operator review and approval for the revision/change order.
- [ ] Send the approved artifact in the original thread.
- [ ] Create a new canonical ScopeVersion only after the documented acceptance rule.

Verification and success checklist:

- [ ] Clarification creates no commercial artifact.
- [ ] Expansion displays the correct immediate price/timeline delta.
- [ ] Closure creates one consolidated artifact.
- [ ] The artifact remains unsent until approval.
- [ ] Approved revision/change order sends once in the same Gmail thread.
- [ ] Accepted baseline history remains intact.

Evidence to record:

- [ ] Live thread message IDs and sanitized event log: ____________________.
- [ ] Scope buffer and delta evidence: ____________________.
- [ ] Approved revision/send evidence: ____________________.

Move-on gate:

- [ ] DAY 13 PASS — the full non-UI Gmail proposal and scope-change loop passes end to end.

### Day 14 — Cloud Run deployment, IAM, and observability

Status: LOCKED.

Daily outcome: the hosted Google Cloud workflow is reliable, visible, and safe under retries.

Implementation checklist:

- [ ] Build a production container for the ADK/FastAPI-compatible service.
- [ ] Deploy the backend to Cloud Run.
- [ ] Configure Vertex AI, Firestore, Pub/Sub push, Gmail credentials, and environment settings.
- [ ] Scope service-account IAM to required services only.
- [ ] Configure secrets through approved secret storage, not source or logs.
- [ ] Add structured logs for correlation ID, project, agent run, tool action, state transition, artifact, approval, and send action.
- [ ] Add health/readiness behavior.
- [ ] Add timeout, retry, and dead-letter handling where appropriate.
- [ ] Prepare a short Cloud Logging/Trace view for the demo.

Verification and success checklist:

- [ ] A real Gmail event reaches Cloud Run and completes the hosted workflow.
- [ ] Logs show semantic analysis separately from deterministic commerce.
- [ ] Pub/Sub or Cloud Run retries do not duplicate artifacts or sends.
- [ ] No secret or raw credential appears in logs.
- [ ] IAM review shows no unnecessarily broad role.
- [ ] Hosted failure paths remain reviewable and recoverable.

Evidence to record:

- [ ] Cloud Run revision and deployment command: ____________________.
- [ ] Sanitized IAM review: ____________________.
- [ ] Hosted golden-path trace/log link: ____________________.
- [ ] Retry/idempotency test output: ____________________.

Move-on gate:

- [ ] DAY 14 PASS — hosted golden path, observability, IAM, secret safety, and retry tests pass.

### Day 15 — Minimal review UI

Status: LOCKED — frontend/UI/UX work is forbidden until Days 0–14 pass.

Daily outcome: a thin interface lets a reviewer understand evidence and take approval actions without duplicating backend policy.

Implementation checklist:

- [ ] Confirm the frontend unlock gate in this document.
- [ ] Create the patched Next.js 16.3.3+ application with TypeScript and Tailwind.
- [ ] Build only the home/action-required route.
- [ ] Build only the project review route.
- [ ] Build only the eval evidence route.
- [ ] Show canonical scope, current artifact, USD price, timeline, delta, assumptions, exclusions, and evidence.
- [ ] Show ScopeEvents, versions, approvals, sends, and audit history.
- [ ] Add explicit approve, reject, and finalize controls.
- [ ] Call policy-checked backend endpoints for every mutation.
- [ ] Keep all pricing, timeline, transition, and send rules out of frontend code.
- [ ] Add loading, empty, error, stale-artifact, and low-confidence states.

Verification and success checklist:

- [ ] A fresh reviewer can identify why action is required.
- [ ] A reviewer can trace each selected module and price line to evidence/SOP.
- [ ] Approval cannot bypass backend policy.
- [ ] Scope history clearly distinguishes clarification from expansion.
- [ ] Keyboard navigation, labels, focus states, contrast, and responsive layouts pass review.
- [ ] Golden path works at the target desktop viewport.

Evidence to record:

- [ ] Frontend build/test output: ____________________.
- [ ] Desktop and narrow-viewport screenshots: ____________________.
- [ ] Fresh-reviewer usability notes: ____________________.

Move-on gate:

- [ ] DAY 15 PASS — a fresh reviewer completes the approval flow without explanation or policy bypass.

### Day 16 — Final evaluation, hardening, and release candidate

Status: LOCKED.

Daily outcome: measured evals and failure tests prove the release candidate meets every safety invariant.

Implementation checklist:

- [ ] Freeze features.
- [ ] Run the complete Requirement Analyzer corpus.
- [ ] Run the complete Scope Analyzer corpus.
- [ ] Run deterministic pricing, timeline, state, buffer, and approval suites.
- [ ] Run ADK trajectory tests.
- [ ] Run persistence and external-event replay tests.
- [ ] Run the hosted Gmail golden path repeatedly.
- [ ] Test model timeout, malformed output, invalid SOP key, stale artifact, low confidence, rejected approval, transient persistence failure, and repeated send.
- [ ] Persist EvalResult records and expose them in the eval UI.
- [ ] Fix only release-blocking defects and rerun the owning day.

Verification and success checklist:

- [ ] Golden path passes repeatedly.
- [ ] Invalid SOP module hallucination is zero for the reviewed release corpus.
- [ ] Unsupported commercial claims are zero in the golden path.
- [ ] Approval-gate violations are zero.
- [ ] Duplicate external sends are zero.
- [ ] Accepted baseline mutation is zero.
- [ ] Expansion false negatives are individually reviewed.
- [ ] All reported metrics are measured and linked to the evaluated corpus.

Evidence to record:

- [ ] Release eval report: ____________________.
- [ ] Full automated test output: ____________________.
- [ ] Hosted repeated-run evidence: ____________________.
- [ ] Known limitations and accepted risks: ____________________.

Move-on gate:

- [ ] DAY 16 PASS — all release metrics and safety invariants pass; any failure returns work to the responsible day.

### Day 17 — Submission and four-minute demo polish

Status: LOCKED.

Daily outcome: a reproducible submission and one coherent sub-four-minute demo communicate the product clearly.

Implementation checklist:

- [ ] Keep the feature freeze in effect.
- [ ] Update README setup, architecture, environment, commands, limitations, and troubleshooting.
- [ ] Document third-party and pre-existing work disclosure.
- [ ] Finalize the architecture diagram.
- [ ] Finalize the exact demo script and fallback plan.
- [ ] Make the event-driven trigger visible in the first 10–15 seconds.
- [ ] Show ADK/Gemini reasoning and tool trace.
- [ ] Show deterministic price/timeline evidence.
- [ ] Show explicit approval before each commercial send.
- [ ] Show clarification versus expansion and the consolidated revision.
- [ ] Show Firestore/state history and Cloud Run execution.
- [ ] Record and review the final demo.
- [ ] Complete the official submission checklist.

Verification and success checklist:

- [ ] Clean-checkout setup succeeds using only documented instructions.
- [ ] Demo duration is under four minutes with contingency time.
- [ ] Demo is one end-to-end story, not a feature tour.
- [ ] Judges can see autonomous triggering, bounded agents, deterministic commerce, approval, persistence, eval evidence, and Google Cloud.
- [ ] No unverified metric, unsupported claim, secret, P1 distraction, or unstable integration appears.
- [ ] Backup recording and sanitized demo data are ready.

Evidence to record:

- [ ] Clean-checkout verification output: ____________________.
- [ ] Final demo duration and recording path: ____________________.
- [ ] Official submission checklist path: ____________________.
- [ ] Final commit/tag or release reference: ____________________.

Move-on gate:

- [ ] DAY 17 PASS — the submission is reproducible, compliant, safe, and clearly demonstrates ScopeLock’s value.

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

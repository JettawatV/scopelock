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

Last reviewed: **2026-08-30**

Current active day: **Day 11 — hosted Gmail event gate**

Immediate next evidence: complete the owner-only IAM, Secret Manager, Pub/Sub
push, logging, and first-mailbox replay checks. The combined Vite/Python image
is deployed to private Cloud Run and an authenticated owner received `200` from
`/health`, `/`, `/projects`, and `/evals` on 2026-08-30. Live external Gmail
activation remains intentionally off.

Next unlock: **Days 11–13 remain locked until the hosted Gmail event, duplicate
delivery, same-thread continuation, approval-gated send, and revision checks
pass. Day 14 deployment and Day 15 hosted-route packaging are evidenced;
IAM/security, observability, fresh-reviewer, and real-mailbox evidence remain
open.**

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
- [x] Python 3.13.14 environment, 152-package lockfile, clean install, ADK discovery, and the pre-Gmail 203-test agent gate verified.
- [x] Day 3 strict SOP validation, deterministic USD PricingEngine, immutable pricing records, and golden pricing fixture verified.
- [x] Day 4 deterministic timeline, explicit state transitions, immutable ScopeVersion records, and proposal/change-order numbering verified.
- [x] Day 5 typed Scope Analyzer and 25-case native ADK corpus verified with measured 100% exact classification, 100% evidence coverage, and 0% invalid modules in the recorded run.
- [x] Day 6 native ADK trajectories, approval/checksum policy, reviewable failure paths, and idempotent non-sending intent stub verified.
- [x] Day 7 complete local initial-proposal path, deterministic proposal artifact, checksum, audit trail, and idempotent replay verified.
- [x] Day 8 scope buffering, consolidation, stale-artifact preservation, revisions, change orders, reductions, and replacements verified.
- [x] Day 9 complete local post-acceptance change-order rehearsal verified in under four minutes without frontend or Gmail dependencies.
- [x] Day 10 repository contracts, Firestore 2.29.0 adapter, unique keys, CAS transactions, replay, concurrency, recovery, and immutable storage verified.
- [x] Midpoint behavior-preserving refactor centralized typed persistence, deterministic identity, transition helpers, and readable workflow stages before Day 11.
- [x] Pre-Day 11 hardening added least-privilege tool contracts, semantic fail-closed validation, failure-isolation tests, approval/evidence invariants, and a one-command 133-test gate.
- [x] Live Scope Analyzer rerun passed 25/25 and live workflow trajectories passed 2/2 on 2026-08-28.
- [x] Requirement Analyzer v3 focused live rerun passed 5/5 on 2026-08-28; this narrow result is preserved as superseded evidence.
- [x] Pre-Gmail flexibility/runtime patch implemented with deterministic routing, direct sub-agent invocation, realistic Gmail normalization, Thai/mixed-scope handling, and source-bound evidence.
- [x] Requirement Analyzer v5 passed 12/12, Scope Analyzer v4 passed 35/35, workflow trajectories passed 2/2, and the final repeatability gate passed 18/18 on 2026-08-29.
- [x] Days 11–13 application code added for OAuth loading, users.watch, authenticated Pub/Sub push, History API checkpoints, approval-bound same-thread draft/send, scope revision finalization, and explicit acceptance.
- [x] Pre-OAuth security/refactor gate added exact-scope token validation, mandatory OIDC, bounded HTTP/Gmail input, atomic event leases, monotonic checkpoints, recipient/thread binding, evidence-bound acceptance, and redacted errors.
- [x] Python 3.13 deterministic suite expanded to 191 passing tests, including 25 Gmail/security/approval/revision integration tests.
- [x] Bandit and final dependency audit pass with zero findings; pytest was upgraded to 9.1.1 to remove `PYSEC-2026-1845`.
- [x] ADK agent gates passed; the user explicitly unlocked the thin operator UI on 2026-08-30 while automatic Gmail activation remains held.
- [x] Vite 7.3.6 operator UI builds as a static SPA beside the Python service; local type/build/audit and responsive checks pass.
- [x] The combined Vite/Python image is deployed as a private Cloud Run service; authenticated owner checks returned `200` for `/health`, `/`, `/projects`, and `/evals` on 2026-08-30.
- [x] Cloud Run health endpoint uses `/health`, not `/healthz`, because Cloud Run reserves some URL paths ending in `z`.

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
- Current execution focus is Day 15. Days 0–10 are complete; hosted Days 11–14 evidence remains open.

## Delivery phase gates

| Phase | Days | Outcome | Current state |
| --- | --- | --- | --- |
| A — ADK semantic foundation | 0–2 | Requirement Analyzer is typed, bounded, repeatable, and evaluated | COMPLETE |
| B — Local deterministic workflow | 3–9 | Pricing, timeline, approval policy, scope drift, and local golden path pass | COMPLETE |
| C — Google integrations | 10–14 | Firestore, Gmail, Pub/Sub, approval-gated sends, and Cloud Run pass | ACTIVE |
| D — UI and submission | 15–17 | Thin review UI, release evals, and four-minute demo are ready | UI DEPLOYED; REVIEW GATE OPEN |

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

Status: CODE COMPLETE / LIVE GATE ACTIVE — continuous mailbox delivery stays
disabled until the project owner completes OAuth/Pub/Sub configuration and the
Day 11 real integration checks pass.

Daily outcome: a real inbound Gmail message wakes ScopeLock and resolves exactly one new thread message.

Implementation checklist:

- [x] Run the deterministic pre-Gmail agent readiness gate: 133 passed.
- [x] Confirm exact agent roster, typed outputs, and least-privilege read-only tool allowlists.
- [x] Confirm unsafe semantic output and model exceptions create zero commercial artifacts, approvals, or sends.
- [x] Rerun Scope Analyzer live eval: 25 passed, 0 failed.
- [x] Rerun live workflow trajectories: 2 passed, 0 failed.
- [x] Rerun Requirement Analyzer v3 live eval: 5 passed, 0 failed.
- [x] Remove the pre-start hold after the v3 result JSON records 5/5.

Pre-Gmail flexibility/runtime hardening checklist:

- [x] Add deterministic `AgentRoute` and terminal `InboundProcessingResult` contracts.
- [x] Normalize plain/HTML Gmail bodies, Thai Unicode, quotes, signatures, long content, and attachment metadata without model access to attachments.
- [x] Route duplicate/outbound/automated/empty, incomplete intake, proposed scope, and accepted scope deterministically.
- [x] Invoke the selected production sub-agent directly with immutable `AnalysisContext` session state.
- [x] Expose only semantic SOP keys, aliases, inclusions, exclusions, dependencies, materiality, and quantity policy to agents.
- [x] Retain supported mappings while unsupported work blocks all commercial artifacts.
- [x] Keep deadline and budget constraints typed and isolated from deterministic commerce.
- [x] Support 0–10 atomic scope events, compound changes, and closure plus material events; fail 11+ closed.
- [x] Bind Gmail, baseline, quote, module, quantity, and SOP-version evidence to authoritative application records.
- [x] Persist application-owned inbound results, AgentRuns, redacted ToolActions, decisions, events, and replay outcomes.
- [x] Pass the expanded deterministic gate: 191 passed, 0 failed under Python 3.13.14.
- [x] Pass Requirement Analyzer v5 native ADK eval: 12/12.
- [x] Pass Scope Analyzer v4 native ADK eval: 35/35.
- [x] Pass workflow trajectory native ADK eval: 2/2.
- [x] Pass focused live repeatability: 18/18 across golden, mixed, Thai, deadline, prompt-injection, and multi-change cases.
- [x] Prove `adk run app` and `adk web` remain discoverable with the current package.
- [x] Record result filenames and final decision in `docs/evidence/PRE_GMAIL_FLEXIBILITY_PATCH.md`.

Pre-OAuth security/refactor checklist:

- [x] Threat-model Gmail OAuth, Pub/Sub push, untrusted email, operator commands, Firestore state, commercial sends, and hosted logs.
- [x] Remove the production OIDC-disable switch and verify audience, exact service-account email, and verified-email claim.
- [x] Limit HTTP bodies, Pub/Sub data, Gmail batches/pages, MIME parts/depth, headers, body text, attachments, and thread context.
- [x] Add atomic expiring Pub/Sub processing leases and monotonic CAS history checkpoints.
- [x] Reject OAuth tokens with missing or extra scopes and harden local credential reads/writes.
- [x] Bind same-thread commercial drafts to the project client as sender/recipient and reject RFC header injection.
- [x] Require persisted same-client/same-thread Gmail evidence before canonical scope acceptance.
- [x] Redact external/runtime error messages and disable production API docs/OpenAPI.
- [x] Run secret/credential filename scans, Bandit, package compatibility, and `pip-audit`.
- [x] Upgrade pytest to 9.1.1 and pass the final vulnerability audit with no known findings.
- [ ] Complete the owner-only IAM, Secret Manager, dedicated-mailbox, logging, quota, retry/dead-letter, and token-revocation controls in `docs/GMAIL_SECURITY_GATE.md`.
- [ ] Record sanitized hosted attack/recovery checks before activating `users.watch` and real Pub/Sub delivery.

- [X] Create or confirm the dedicated demo Gmail account.
- [x] Enforce exactly `gmail.readonly` plus `gmail.compose` in application code; reject broad mailbox scope.
- [X] Complete the OAuth consent screen and authorize the dedicated demo account.
- [x] Ignore local OAuth files and support Secret Manager-injected token JSON for Cloud Run.
- [x] Store the real OAuth client/token through the documented protected local path.
- [ ] Copy the token and operator key into separate pinned Secret Manager versions.
- [ ] Configure the Pub/Sub topic and authenticated push subscription.
- [x] Implement Gmail users.watch setup, project/topic validation, expiration, and checkpoint-preserving renewal.
- [x] Implement the Pub/Sub push endpoint, OIDC verification, and notification decoding.
- [x] Persist the last processed Gmail history checkpoint.
- [x] Resolve notifications through paginated Gmail History API `messagesAdded` records.
- [x] Parse sender, recipients, subject, body, message ID, thread ID, timestamps, and attachment metadata.
- [x] Ignore sent/automated/empty mail before model invocation and ignore irrelevant project mail without artifact creation.
- [x] Associate continuation messages with the project through the unique Gmail thread key.

Verification and success checklist:

- [x] Pre-Gmail flexibility/runtime hardening gate is fully checked.
- [ ] A real inbound email creates one Firestore project/event without opening ScopeLock.
- [ ] The history ID resolves the expected message and thread.
- [x] Automated replay, active/stale lease, concurrent checkpoint, and out-of-order Pub/Sub tests create no second workflow call or checkpoint regression.
- [ ] A second real message in the same thread attaches to the same project.
- [x] OAuth scopes and secret handling are documented in `docs/GMAIL_OAUTH_AND_PUBSUB_SETUP.md`.
- [x] Pre-connection threat model, code controls, owner controls, attack checks, and incident stop conditions are documented in `docs/GMAIL_SECURITY_GATE.md`.
- [x] Watch expiration and renewal behavior are persisted and covered by automated tests.

Evidence to record:

- [x] Sanitized local OAuth configuration record: `docs/evidence/DAY_11_LOCAL_OAUTH_EVIDENCE.md`.
- [ ] Sanitized hosted Gmail/Pub/Sub configuration record: ____________________.
- [ ] First real inbound-event logs: ____________________.
- [x] Automated replay and same-thread test output: `tests/integration/test_gmail_days_11_13.py`.
- [x] Code and agent evidence: `docs/evidence/DAY_11_13_CODE_EVIDENCE.md`.
- [x] Automated security evidence: `docs/evidence/PRE_GMAIL_SECURITY_EVIDENCE.md`.

Move-on gate:

- [ ] DAY 11 PASS — mailbox-to-backend triggering works twice, including duplicate delivery and same-thread continuation.

### Day 12 — Approval API and Gmail draft/send integration

Status: CODE COMPLETE / LIVE GATE LOCKED BY DAY 11.

Daily outcome: an operator can review an artifact and send it in the original Gmail thread only after explicit approval.

Implementation checklist:

- [x] Implement operator-key-protected read, approve, reject, revise, draft, and send endpoints.
- [x] Bind approval to artifact ID, version, checksum, approver, correlation ID, and timestamp.
- [x] Implement Gmail draft creation with thread ID, matching subject, `In-Reply-To`, and `References`.
- [x] Implement deterministic send execution behind `ApprovalPolicy` with no blind external retry.
- [x] Attach the exact canonical reviewed commercial bytes.
- [x] Add draft/send idempotency keys and durable pending/result records.
- [x] Record approval, draft, send attempt, Gmail message ID, thread ID, checksum, result, and error.
- [x] Keep Gmail send absent from every ADK tool allowlist.

Verification and success checklist:

- [ ] Initial inbound email can reach generated artifact and explicit approval.
- [ ] Approved artifact sends in the original Gmail thread.
- [x] Automated policy tests reject missing, rejected, stale, or checksum-mismatched approval.
- [x] Automated replay returns the existing send result and invokes the Gmail gateway once.
- [x] Revision requests make the reviewed artifact stale and invalidate its approval for draft/send.
- [x] Draft/send records trace the intent, approval, artifact checksum, Gmail IDs, and exact attached bytes.

Evidence to record:

- [x] Approval-policy integration test: `tests/integration/test_gmail_days_11_13.py`.
- [ ] Same-thread Gmail send evidence: ____________________.
- [x] Automated duplicate-send prevention: `test_approval_creates_same_thread_draft_and_replay_sends_once`.

Move-on gate:

- [ ] DAY 12 PASS — external sends are same-thread, traceable, idempotent, and impossible without current explicit approval.

### Day 13 — Live Gmail scope monitoring and revision send

Status: CODE COMPLETE / LIVE GATE LOCKED BY DAY 11.

Daily outcome: real follow-up messages become scope events, consolidate correctly, and produce an approval-gated revision.

Implementation checklist:

- [ ] Send the harmless clarification through the live Gmail thread.
- [ ] Send the material expansion through the same thread.
- [ ] Send the closure message through the same thread.
- [x] Persist every ScopeEvent and ScopeBuffer update through the application repository.
- [x] Recalculate deterministic commercial impact immediately after material input.
- [x] Consolidate related changes on semantic closure, quiet-window expiry, or manual finalize.
- [x] Expose protected finalize, review, approval, draft, send, and acceptance commands.
- [x] Route an approved revision through the same original-thread send service.
- [x] Create and activate the canonical ScopeVersion only after a sent artifact is explicitly accepted with persisted same-client/same-thread Gmail evidence.

Verification and success checklist:

- [x] Automated workflow tests prove clarification creates no commercial artifact.
- [x] Automated buffer tests prove expansion immediately records deterministic price/timeline delta.
- [x] Automated closure/finalize tests create one consolidated review artifact.
- [x] Approval-policy tests prove the artifact remains unsent until approval.
- [ ] Approved revision/change order sends once in the same Gmail thread.
- [ ] Accepted baseline history remains intact.

Evidence to record:

- [ ] Live thread message IDs and sanitized event log: ____________________.
- [x] Automated scope buffer, delta, and canonical acceptance evidence: `tests/integration/test_gmail_days_11_13.py`.
- [ ] Approved revision/send evidence: ____________________.

Move-on gate:

- [ ] DAY 13 PASS — the full non-UI Gmail proposal and scope-change loop passes end to end.

### Day 14 — Cloud Run deployment, IAM, and observability

Status: HOSTED DEPLOYMENT ACTIVE / LIVE GMAIL GATE LOCKED BY DAY 11.

Daily outcome: the hosted Google Cloud workflow is reliable, visible, and safe under retries.

Implementation checklist:

- [x] Build a production container definition for the ADK/FastAPI-compatible service.
- [x] Deploy the combined backend and Vite operator UI to private Cloud Run.
- [ ] Configure Vertex AI, Firestore, Pub/Sub push, Gmail credentials, and environment settings.
- [ ] Scope service-account IAM to required services only.
- [x] Add Secret Manager-only hosted configuration contracts and build-context exclusions.
- [x] Add redacted structured logs for correlation ID, project, agent run, tool action, state transition, artifact, approval, and send action.
- [x] Add a no-runtime-initialization health endpoint and fail-closed hosted startup preflight.
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

- [x] Container/IAM/deployment runbook: `docs/CLOUD_RUN_DEPLOYMENT.md`.
- [x] Local container-readiness evidence: `docs/evidence/DAY_14_CONTAINER_READINESS_EVIDENCE.md`.
- [x] Authorized private route check: `docs/evidence/DAY_14_HOSTED_ROUTE_EVIDENCE.md`.
- [x] Structured-log implementation and redaction tests: `docs/evidence/DAY_14_OBSERVABILITY_EVIDENCE.md`.
- [ ] Cloud Run revision and executed deployment command: ____________________.
- [ ] Sanitized IAM review: ____________________.
- [ ] Hosted golden-path trace/log link: ____________________.
- [ ] Retry/idempotency test output: ____________________.

Move-on gate:

- [ ] DAY 14 PASS — hosted golden path, observability, IAM, secret safety, and retry tests pass.

### Day 15 — Minimal review UI

Status: HOSTED ROUTES VERIFIED / FRESH-REVIEWER GATE OPEN — user explicitly unlocked the thin UI after the full agent gate passed; hosted Gmail activation remains blocked by Day 11.

Daily outcome: a thin interface lets a reviewer understand evidence and take approval actions without duplicating backend policy.

Implementation checklist:

- [x] Confirm the frontend unlock gate in this document.
- [x] Create the Vite 7.3.6 application with TypeScript, React, and Tailwind.
- [x] Build only the home/action-required route.
- [x] Build only the project review route.
- [x] Build only the eval evidence route.
- [x] Show canonical scope, current artifact, USD price, timeline, delta, assumptions, exclusions, and evidence.
- [x] Show ScopeEvents, immutable versions, approval/send artifact status, and redacted agent-run audit history.
- [x] Add explicit approve, reject, and finalize controls.
- [x] Call policy-checked backend endpoints for every mutation.
- [x] Keep all pricing, timeline, transition, and send rules out of frontend code.
- [x] Add loading, empty, error, stale-artifact, and fail-closed needs-review states.

Verification and success checklist:

- [ ] A fresh reviewer can identify why action is required.
- [ ] A reviewer can trace each selected module and price line to evidence/SOP.
- [x] Approval cannot bypass backend policy.
- [x] Scope history clearly distinguishes clarification from expansion.
- [x] Keyboard navigation, labels, focus states, contrast, and responsive layouts pass local review.
- [ ] Golden path works at the target desktop viewport.

Evidence to record:

- [x] Frontend build/test and hosted-route output: `docs/evidence/DAY_15_FRONTEND_EVIDENCE.md`.
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

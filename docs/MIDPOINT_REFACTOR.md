# ScopeLock — Midpoint Refactor

Recorded: 2026-08-28

## Goal

Reduce maintenance risk before Gmail, Pub/Sub, and live Google-service work
begins. This refactor is deliberately behavior-preserving: it adds no product
features, changes no SOP commerce, and does not unlock frontend work.

## New shared boundaries

### Typed persistence

`scopelock/repositories/model_store.py` is now the workflow-facing persistence
facade. It owns:

- collection names through `CollectionName`;
- Pydantic serialization and validation;
- required-document errors;
- compare-and-set revision lookup;
- immutable-write requests.

Workflow services no longer repeat raw `create_or_get`, `compare_and_set`, or
`model_dump(mode="json")` calls. The in-memory and Firestore adapters remain
behind the existing `ApplicationRepository` protocol.

### Deterministic identity

`scopelock/services/identity.py` owns deterministic hashes and readable IDs.
External/business unique keys continue through
`scopelock/services/idempotency_service.py`.

### State transitions

`scopelock/services/workflow_state.py` owns immutable project, artifact, and
scope-event transition copies. It delegates legality to the explicit state
machines and returns audit-ready transition records.

### Workflow stages

The initial proposal and local golden-path entry points now read as named
stages:

```text
InitialProposalWorkflow.run
  -> create project
  -> semantic stage
  -> deterministic commercial stage
  -> record review boundary

GoldenPathRehearsal.run
  -> initial proposal
  -> approve and accept initial scope
  -> process typed follow-up events
  -> create and approve change order
```

Reviewed fixture-to-event construction moved to
`scopelock/services/golden_path_scenario.py`, so orchestration no longer embeds
large fixture records.

## Invariants preserved

- Agents select semantics only; deterministic code owns money and time.
- Accepted scope records remain immutable.
- No commercial send intent exists without a current approval.
- Replays do not duplicate projects, events, artifacts, approvals, or sends.
- Proposal and change-order checksums remain stable.
- Day 11 remains the active gate; frontend work remains locked.

## Verification

Direct refactor-foundation tests cover typed model persistence, CAS updates,
missing-record errors, deterministic IDs, immutable project transitions, and
pure typed golden-scenario construction. The complete repository test suite is
the final behavior-equivalence gate: **121 tests passed** on 2026-08-28. The
single warning is the existing ADK `BaseAgentConfig` deprecation notice.

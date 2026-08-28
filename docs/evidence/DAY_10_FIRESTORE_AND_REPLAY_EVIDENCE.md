# Day 10 — Firestore, Replay, and Recovery Evidence

Recorded: 2026-08-28

## Persistence contract

- Schema and collection ownership: `docs/FIRESTORE_SCHEMA.md`
- Cloud-independent protocol: `scopelock/repositories/contracts.py`
- Atomic local adapter: `scopelock/repositories/in_memory.py`
- Transactional cloud adapter: `scopelock/repositories/firestore.py`
- Controlled replay fixture: `tests/fixtures/firestore_replay_cases.json`
- Firestore client locked and installed: `google-cloud-firestore==2.29.0`.

The Firestore adapter writes business records and unique-key index documents
inside one transaction. Mutable records use compare-and-set revisions; accepted
scope versions are marked immutable.

## Focused tests

```powershell
.\.venv313\Scripts\python.exe -m pytest tests/unit/test_firestore_repository.py tests/unit/test_idempotency_and_boundaries.py tests/integration/test_persistent_workflow_replay.py -q
```

Result: `10 passed in 0.57s`.

Verified:

- a complete event replay preserves one project, two scope versions, three
  scope events, one buffer, two artifacts, two approvals, and two sends;
- 32 concurrent creates using one Gmail-message key resolve to one canonical
  event;
- a failed approval write creates zero send intents and a later retry recovers;
- accepted scope storage rejects a later mutation;
- Firestore transaction/CAS behavior matches the repository contract;
- model, persistence, external-read, and external-send boundaries have explicit
  timeouts and attempts; send attempts are not blindly retried.

## Full regression

```powershell
.\.venv313\Scripts\python.exe -m pytest -q
```

Result: `117 passed, 1 warning in 7.14s`. The warning is the existing ADK
`BaseAgentConfig` deprecation warning; it is not a test failure.

Day 10 gate: PASS.

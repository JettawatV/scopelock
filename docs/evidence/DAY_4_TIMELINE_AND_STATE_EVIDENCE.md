# Day 4 — Timeline, immutable scope, and state evidence

Recorded: **2026-08-28**

## Deterministic timeline

Implementation: `scopelock/services/timeline_engine.py`

The tested P0 algorithm validates explicitly selected dependencies, uses a deterministic topological order, chooses the greatest-duration module as the base, adds each other non-parallel module's full base days, and adds zero days for other parallel modules. Equal base durations are resolved by module key. Quantity is recorded but does not multiply duration in P0.

Focused command:

```powershell
.\.venv313\Scripts\python.exe -m pytest tests\unit\test_timeline_engine.py tests\unit\test_state_and_commercial_versions.py tests\unit\test_pricing_engine.py -q
```

Result: **33 passed in 0.52s** on 2026-08-27.

## Explicit state transitions

Implementation: `scopelock/domain/state_machines.py`

The project, generic artifact, proposal, change-order, and scope-event transition maps are explicit. Invalid transitions raise `IllegalStateTransition`. Tests reject draft-to-sent, rejected-to-approved, and stale-to-sending transitions.

## Immutable scope and artifact numbering

Implementation: `scopelock/services/commercial_artifact_service.py`

`ScopeVersion`, its requirements, normalized calculation inputs, pricing result, and timeline result are frozen Pydantic records. Acceptance and supersession create validated copies rather than editing the original. Before acceptance, changes create Proposal v1 then Proposal Revision v2; after acceptance, changes create Change Order #001, #002, and so on. Every scope and commercial artifact records calculation inputs and one SOP version.

Final regression command:

```powershell
.\.venv313\Scripts\python.exe -m pytest -q
```

Result: **96 passed in 7.10s** on 2026-08-28.

## Gate conclusion

DAY 4 PASS — deterministic duration, dependency/parallel behavior, typed transition rejection, immutable baselines, and proposal/change-order numbering all pass.

# Day 7 — Local Initial-Proposal Evidence

Recorded: 2026-08-28

## Command

```powershell
.\.venv313\Scripts\python.exe -m scopelock.cli initial-proposal --repeat 2
```

Observed result:

```text
project_status: AWAITING_USER_REVIEW
artifact_status: AWAITING_USER_REVIEW
currency: USD
total_usd: 5650
timeline_days: 5
repeat_count: 2
replayed: true
projects/artifacts/scope versions created: 1/1/1
```

The replay returned the same project, scope-version, artifact, and proposal
checksum rather than creating another version.

## Artifact and checksum

- Proposal data: `artifacts/local_workflow/project-2d8777f70cf0f48f33b51922/proposal-v1.json`
- Fixed-template proposal: `artifacts/local_workflow/project-2d8777f70cf0f48f33b51922/proposal-v1.md`
- Proposal-data SHA-256:
  `a035aa717f1a86358d9b9ce6c7f4b7f7a8ceb620d06a894f8c55ae621e31d336`
- PowerShell `Get-FileHash` returned the same digest.
- Source scope version: `scope-060c2f887f6a76b81f2bd510`, version 1.
- SOP version: `jvl-demo-v1`.

The rendered proposal contains four requirements, four SOP modules, immutable
USD line items, USD 5,650 total, five-day timeline, assumptions, exclusions,
Gmail evidence, SOP evidence, validity, and change-control language.

## Audit and tests

The in-memory repository recorded one `AgentRun`, two `ToolAction` records, one
`ScopeDecision`, two project state transitions, one artifact event, and
separate deterministic pricing, timeline, and rendering audit records.

```powershell
.\.venv313\Scripts\python.exe -m pytest tests/integration/test_initial_proposal_workflow.py -q
```

Result: `3 passed in 1.50s`.

Day 7 gate: PASS.

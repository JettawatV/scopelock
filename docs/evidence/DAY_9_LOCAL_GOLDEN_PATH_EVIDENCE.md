# Day 9 — Complete Local Golden-Path Evidence

Recorded: 2026-08-28

## Demo choice

The frozen rehearsal uses the **post-acceptance change-order** path. See
`docs/LOCAL_DEMO_RUNBOOK.md` for the exact operator story and expected state.

## One-command result

```powershell
.\.venv313\Scripts\python.exe -m scopelock.cli golden-path
```

Observed result:

```text
demo_mode: post_acceptance_change_order
final_project_status: ACTIVE_PROJECT
baseline: USD 5650 / 5 days
scope events: NO_CHANGE, EXPANSION, CLOSURE
consolidated delta: +USD 1500 / +5 days
proposed change: USD 7150 / 10 days
artifact types: PROPOSAL, CHANGE_ORDER
approvals/send intents: 2/2
elapsed_seconds: 0.010972
```

Both send records are local non-sending intents, use the original Gmail thread
ID, and reference current explicit approvals. No Gmail API call is made.

## Integration tests

```powershell
.\.venv313\Scripts\python.exe -m pytest tests/integration/test_local_golden_path.py -q
```

Result: `3 passed in 0.90s`.

The suite also repeats the workflow from two clean repositories and compares
the pricing, timeline, and delta results.

Day 9 gate: PASS.

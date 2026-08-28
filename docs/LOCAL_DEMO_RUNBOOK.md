# ScopeLock — Local Golden-Path Runbook

## Frozen demo choice

The local and hackathon rehearsal uses the **post-acceptance change-order** path.
The initial proposal is explicitly approved, a send intent is created for the
same Gmail thread, and the fixture then marks it accepted. The later LINE scope
expansion therefore creates **Change Order #001**, not Proposal Revision v2.

No command in this runbook calls Gmail. Local sends are policy-checked,
idempotent `SendIntent` records only.

## One-command rehearsal

From the repository root with the Python 3.13 environment active:

```powershell
python -m scopelock.cli golden-path
```

To prove initial-proposal replay behavior independently:

```powershell
python -m scopelock.cli initial-proposal --repeat 2
```

## Expected story and state

1. Golden email is analyzed against `jvl-demo-v1`.
   - Project: `AWAITING_USER_REVIEW`
   - Initial proposal: USD 5,650 / 5 days
   - Artifact: `PROPOSAL`, awaiting review
2. Operator approval is bound to artifact ID, version, and checksum.
   - One same-thread local send intent is created.
   - Fixture marks the proposal and scope accepted.
3. Dashboard-title follow-up is recorded as `NO_CHANGE`.
   - Commercial delta: USD 0 / 0 days
   - No buffer and no artifact are created.
4. LINE alerts plus LINE manager approval are recorded as `EXPANSION`.
   - Buffer delta: +USD 1,500 / +5 days
   - Accepted baseline remains USD 5,650 / 5 days.
5. “That’s everything” is recorded as `CLOSURE`.
   - Buffer finalizes immediately; no 20-minute wait is needed.
   - Change Order #001 is USD 7,150 / 10 days.
6. Operator approves the change order.
   - A second same-thread local send intent is created.
   - The proposed changed scope does not replace the accepted baseline until a
     separate client-acceptance action exists.

## Pass criteria

- CLI exits successfully in under four minutes.
- Exactly one project, one accepted baseline, three follow-up `ScopeEvent`
  records, one finalized buffer, two commercial artifacts, two approvals, and
  two approval-bound send intents exist.
- Every price and timeline number matches the validated SOP.
- There is no send intent without a matching explicit approval.

# Day 8 — Scope Buffer and Commercial Revision Evidence

Recorded: 2026-08-28

## Deterministic verification

```powershell
.\.venv313\Scripts\python.exe -m pytest tests/unit/test_scope_buffer_service.py -q
```

Result: `5 passed in 0.34s`.

Covered behavior:

- harmless clarification is recorded with zero commercial buffer;
- two rapid LINE changes consolidate into +USD 1,500 / +5 days;
- quiet-window expiry metadata is reset from the newest client message;
- semantic closure and manual finalize produce identical commercial inputs;
- new input creates a recalculated artifact and preserves the stale artifact's
  checksum and history;
- pre-acceptance changes create proposal revisions;
- post-acceptance changes create Change Order #001;
- dashboard reduction is -USD 750 / 0 days;
- email-to-LINE replacement is +USD 350 / +3 days.

## Immutable baseline evidence

The accepted fixture remains `ACCEPTED` at USD 5,650 / 5 days. Its finalized
LINE buffer proposes USD 7,150 / 10 days and references the accepted baseline
ID. No method mutates the baseline object.

Day 8 gate: PASS.

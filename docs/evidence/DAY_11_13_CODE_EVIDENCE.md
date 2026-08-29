# Days 11–13 code evidence

Recorded: 2026-08-29

## Automated implementation gate

Command:

```powershell
.\.venv313\Scripts\python.exe -m pytest -q
```

Result after the Gmail runtime and pre-connection security additions:
`191 passed` under Python 3.13.14 and pytest 9.1.1.

The dedicated Gmail integration corpus covers:

- exact least-privilege OAuth scope allowlist;
- watch registration, expiration, and checkpoint-preserving renewal;
- Pub/Sub notification decoding, History API resolution, replay, out-of-order
  delivery, and expired-history fail-closed behavior;
- same-thread RFC headers and deterministic artifact attachment;
- explicit approval binding and missing/stale approval rejection;
- draft and send idempotency;
- uncertain send outcome with no blind retry;
- revision request invalidating prior approval;
- operator API authentication;
- scope-buffer finalization, approval-gated send, immutable old baseline, and
  canonical scope update only after acceptance.

The security extension adds mandatory OIDC, bounded HTTP/Gmail input, atomic
processing leases, monotonic checkpoints, safe commercial RFC headers,
same-client/thread recipient and acceptance binding, error redaction, exact
OAuth token scopes, and current static/dependency/secret scans. Detailed results
are recorded in `docs/evidence/PRE_GMAIL_SECURITY_EVIDENCE.md`.

## Final agent gate

Command:

```powershell
.\scripts\test-agent-plan.ps1 -LiveAdk
.\scripts\test-pre-gmail-live-gate.ps1
```

Results:

- Requirement Analyzer `requirement_analyzer_v5`: 12/12;
- Scope Analyzer `scope_analyzer_v4`: 35/35;
- workflow trajectory safety: 2/2;
- focused three-iteration repeatability: 18/18.

Final ADK result filenames:

- `app_scopelock_requirement_analyzer_v5_1787964451.260818.evalset_result.json`;
- `app_scopelock_scope_analyzer_v4_1787964513.0259292.evalset_result.json`;
- `app_scopelock_workflow_trajectories_v1_1787964535.7997952.evalset_result.json`;
- repeatability summary: `artifacts/evals/pre-gmail-live-gate.json`.

## Gate decision

The code and model gates are green. Days 11–13 remain **live-gate pending**,
because no real Gmail OAuth credential, Pub/Sub subscription, Firestore event,
or external Gmail send was created during this automated pass. Continuous
mailbox activation and frontend work remain held until the project owner
completes the setup and records the live checks in the daily plan.

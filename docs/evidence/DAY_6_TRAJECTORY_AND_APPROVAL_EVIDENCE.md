# Day 6 — ADK trajectory and approval safety evidence

Recorded: **2026-08-28**

## Native ADK trajectory evaluation

Cases: `tests/eval/workflow_trajectories.evalset.json`

- `initial_proposal`: root transfer to Requirement Analyzer, then `get_sop_catalog`.
- `scope_expansion`: root transfer to Scope Analyzer, then `get_current_scope`, `get_recent_thread_context`, and `get_sop_catalog` in order.

Both trajectories are joined to application-owned deterministic steps in `scopelock/services/workflow_trajectory.py`. They contain no approval or send action and terminate at `AWAITING_USER_REVIEW`.

Command:

```powershell
.\.venv313\Scripts\adk.exe eval app tests\eval\workflow_trajectories.evalset.json --config_file_path tests\eval\workflow_trajectories.config.json
```

Result: **2 passed, 0 failed**. Local ADK result: `app/.adk/eval_history/app_scopelock_workflow_trajectories_v1_1787875244.2575443.evalset_result.json` (runtime evidence ignored by Git).

## Approval and send-intent boundary

Implementation: `scopelock/services/approval_policy.py`

- Review artifacts are sealed with a SHA-256 content checksum.
- Approvals bind artifact ID, version, checksum, approver, decision timestamp, and correlation ID.
- Missing, rejected, stale, version-mismatched, and checksum-mismatched approvals are rejected with typed `ApprovalPolicyViolation` errors.
- `InMemorySendStub` creates an intent only; it has no Gmail client and cannot send externally.
- The idempotency key binds artifact ID, version, checksum, and Gmail thread ID. Repeating the request returns the same single intent.

Focused command:

```powershell
.\.venv313\Scripts\python.exe -m pytest tests\unit\test_approval_policy.py tests\unit\test_workflow_trajectory.py tests\unit\test_scope_run_boundary.py -q
```

Result: **10 passed in 0.39s** on 2026-08-27.

The failure suite proves model timeout, malformed typed output, ambiguous/low confidence, stale artifact, rejected approval, missing approval, old checksum, and repeated request paths. Unsafe attempts create zero send intents; approval-gate violations are therefore **0** in the tested suite.

Final regression result: **96 passed in 7.10s** on 2026-08-28.

## Gate conclusion

DAY 6 PASS — required ADK tool order, pre-approval stopping, approval binding, reviewable failures, correlation IDs, and idempotent intent creation all pass. Real Gmail sending remains intentionally locked until Day 12.

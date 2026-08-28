# Pre-Gmail Flexibility and Runtime Patch Evidence

Date: 2026-08-28

Status: **PASS — the agent/runtime hardening gate is complete. Real Gmail OAuth
implementation may begin.**

## Implemented boundary

- deterministic `AgentRoute` and terminal `InboundProcessingResult` contracts;
- Gmail payload normalization, Unicode/Thai preservation, bounded context,
  attachment metadata, and non-LLM ignore/duplicate checks;
- direct Requirement Analyzer v4 and Scope Analyzer v2 production gateway;
- immutable session-state tools and semantic SOP projection with no prices or
  timeline rules;
- mixed supported/unsupported intake behavior with no commercial artifact;
- typed deadline/budget constraints that cannot affect commerce;
- 0–10 atomic scope events, compound changes, closure coexistence, and invalid
  11-event review behavior;
- authoritative Gmail, ScopeVersion, quote, SOP-version, and quantity binding;
- application-owned inbound result, AgentRun, redacted ToolAction, decision,
  event, and replay records;
- persistence/model timeout and retry boundaries plus UTF-8 Windows CLI output.

## Deterministic evidence

Command:

```powershell
.\.venv313\Scripts\python.exe -m pytest -q
```

Result: **166 passed, 0 failed** in 7.02 seconds under Python 3.13.14. One
Google ADK `BaseAgentConfig` deprecation warning remains and does not affect
this gate.

## Live ADK evidence

- [x] Requirement Analyzer v4 native ADK corpus: 12/12.
  - `app_scopelock_requirement_analyzer_v4_1787898664.8533242.evalset_result.json`
- [x] Scope Analyzer v2 native ADK corpus: 35/35.
  - `app_scopelock_scope_analyzer_v2_1787900017.2164075.evalset_result.json`
- [x] Workflow trajectory native ADK corpus: 2/2.
  - `app_scopelock_workflow_trajectories_v1_1787900062.7294443.evalset_result.json`
- [x] Focused production-shaped repeatability gate: 18/18.
  - `artifacts/evals/pre-gmail-live-gate.json`
  - Iteration 1: `requirement_app_scopelock_requirement_analyzer_v4_1787900653.2594786.evalset_result.json`
    and `scope_app_scopelock_scope_analyzer_v2_1787900678.6587188.evalset_result.json`
  - Iteration 2: `requirement_app_scopelock_requirement_analyzer_v4_1787900703.4465191.evalset_result.json`
    and `scope_app_scopelock_scope_analyzer_v2_1787900724.0671234.evalset_result.json`
  - Iteration 3: `requirement_app_scopelock_requirement_analyzer_v4_1787900750.9025507.evalset_result.json`
    and `scope_app_scopelock_scope_analyzer_v2_1787900775.277234.evalset_result.json`
- [x] `adk run app` live smoke check completed against Vertex AI with the root
  agent transferring to `requirement_analyzer` and returning typed output.
- [x] `adk web` discovery smoke returned `app`, `backend.app`, and the two
  test-only direct-agent eval packages.

## Compatibility finding

Vertex AI rejected the nested response schema while it contained JSON Schema
`maxItems`. The contract now omits that unsupported keyword and enforces the
0–10 event boundary in Pydantic validation. A regression test protects this
provider-compatibility requirement; an 11-event result still fails closed to
`NEEDS_REVIEW`.

## Promotion decision

The pre-Gmail agent/runtime hold is cleared. ScopeLock is ready to start the
real Gmail OAuth, History API, Pub/Sub, and `users.watch` implementation work
for Day 11.

This does not mean the external Gmail path is already complete. OAuth client
configuration and tokens are not present in the local environment yet, and no
application-owned Gmail/History/Pub/Sub adapter exists. Keep automatic mailbox
events disabled until the Day 11 OAuth read smoke test, history resolution,
duplicate delivery, and same-thread continuation checks pass.

## Day 11 cloud preflight snapshot

The read-only Google Cloud check on 2026-08-28 found:

- active `gcloud` authentication: yes;
- configured project matches ScopeLock: yes;
- Vertex AI API: enabled and independently proven by the live ADK run;
- Firestore API: enabled;
- Gmail API: not enabled yet;
- Pub/Sub API: not enabled yet;
- Gmail OAuth client keys/tokens in the local environment: not configured;
- root `.env`: ignored by Git; no credential file is tracked.

These are Day 11 setup tasks, not failures of the agent hardening gate. The
project is ready to move into real Gmail OAuth configuration, but it is not yet
ready to receive automatic Gmail events.

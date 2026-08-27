# Day 1 — ADK Invocation and Audit Evidence

Recorded: **2026-08-27**

Environment:

- Python 3.13.14
- Google ADK 2.8.0
- Model: gemini-3.5-flash through Vertex AI
- Prompt: requirement_analyzer_v2
- Working directory: repository root

## Native ADK CLI proof

Command shape:

```powershell
adk run --in_memory --jsonl --timeout 120s app "<golden requirement email>"
```

Result:

- Exit code: 0
- ADK session: eafdadb5-706d-4eb8-be34-4c98a7d3d30b
- App discovery: passed
- Root-agent invocation: passed
- Root delegated to requirement_analyzer.
- requirement_analyzer called get_sop_catalog before selecting modules.
- Final RequirementAnalysis was schema-valid, proposal-ready, and contained the four expected SOP modules.
- No price or timeline was returned by the model.

Observed ordered trajectory:

1. transfer_to_agent call
2. transfer_to_agent result
3. get_sop_catalog call
4. get_sop_catalog result
5. typed final RequirementAnalysis

Post-hardening verification repeated the native command after strict
`extra="forbid"` output validation was enabled:

- Exit code: 0
- ADK events: 5
- proposal_ready: true
- Modules: email_intake, core_workflow_automation, operations_dashboard, email_notifications
- Unexpected price field: absent
- Final strict schema validation: passed

## Application-owned AgentRun proof

Live run:

- AgentRun ID: 8120837e-81e6-44a4-bc72-80c9ecedeead
- Correlation ID: ba98f0e2-f584-41e7-bc73-1ccc95744557
- Input SHA-256: 21e1d5d87a5a62344f409f735d91232e3095c838b19cc6f0052dc64d64acee29
- Status: COMPLETED
- Validated output present: yes
- proposal_ready: true
- ToolAction count: 4
- Local record: artifacts/agent_runs/8120837e-81e6-44a4-bc72-80c9ecedeead/agent_run.json
- Local trajectory: artifacts/agent_runs/8120837e-81e6-44a4-bc72-80c9ecedeead/tool_actions.jsonl

The persisted AgentRun contains all required fields: correlation ID, agent name,
model, prompt version, input hash, status, validated output, error metadata,
started_at, and completed_at.

Together with the original user-run v2 result, the native CLI run, the
application-owned live run, and the post-hardening native run provide four
passing golden-path samples. One additional run remains for the five-run Day 2
repeatability gate.

## Controlled failure proof

Malformed RequirementAnalysis fixture:

- AgentRun ID: ae7140a8-bf3a-49ea-9e0d-ead3c894dc94
- Status: NEEDS_REVIEW
- Output: none
- Error category: INVALID_REQUIREMENT_OUTPUT
- Local record: artifacts/agent_runs/ae7140a8-bf3a-49ea-9e0d-ead3c894dc94/agent_run.json

An additional test removes GOOGLE_CLOUD_PROJECT before execution. The runner
persists a FAILED AgentRun with zero tool actions and never reaches a model or
send path.

## Automated verification

```text
14 passed, 1 upstream ADK deprecation warning
```

Covered behavior:

- required AgentRun metadata and input hashing;
- RequirementAnalysis validation;
- unexpected fields such as model-generated price_usd are rejected;
- malformed output becomes NEEDS_REVIEW;
- unknown SOP module becomes NEEDS_REVIEW;
- tool calls/results persist as application-owned ToolAction records;
- missing project configuration fails and persists safely;
- the active agent hierarchy exposes only the three approved read-only tools.

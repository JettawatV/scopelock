# Pre-Gmail Flexibility and Runtime Patch Evidence

Date: 2026-08-28

Status: **IN PROGRESS — deterministic gate passed; live ADK promotion evidence pending.**

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

Result: **165 passed, 0 failed** in 13.66 seconds. One Google ADK
`BaseAgentConfig` deprecation warning remains and does not affect this gate.

## Pending live evidence

- [ ] Requirement Analyzer v4 native ADK corpus: 12/12.
- [ ] Scope Analyzer v2 native ADK corpus: 35/35.
- [ ] Workflow trajectory native ADK corpus: 2/2.
- [ ] Focused repeatability gate: 18/18.
- [ ] `adk run app` and `adk web` discovery smoke checks.

Automatic Gmail event activation remains held until every pending item is
checked and its generated ADK result filename is recorded here.

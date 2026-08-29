# ScopeLock — Agent Design

## 1. Philosophy

Use the model only where semantic reasoning is required.

Avoid a "one giant agent with every tool" architecture.

P0 may be implemented with **two primary LLM agents and one optional reviewer**.

## ADK development structure

Use one ADK-native root agent named `scopelock` in `app/agent.py`. It delegates
to the active P0 sub-agent in `app/sub_agents/`. Start with only
`requirement_analyzer`; the `scope_analyzer` is added only after the Requirement
Analyzer passes typed-output, evidence, tool-trajectory, and safety evaluations.
Both agents now exist, and both expose read-only tools only.

Develop through `adk web .` and `adk run app`. Keep deterministic commerce in
the separate `scopelock/` package. Frontend work is blocked until this ADK gate
passes.

The root agent is a development/eval convenience only. Production applies a
deterministic `AgentRoute` and invokes the selected sub-agent directly through
`AdkAgentGateway`; the model never decides whether a message is initial intake
or an existing-project change.

---

## 2. Agent A — Requirement Analyzer

### Trigger
New project-like inbound Gmail thread.

### Goal
Convert the client request into a typed, evidence-backed project requirement model and map it to valid SOP service modules.

### Input
- new Gmail message/thread text;
- current business SOP/service catalog;
- optional user business preferences.

### Output (typed)

```python
RequirementAnalysis:
    is_project_request: bool
    project_title: str
    objective: str
    requirements: list[NormalizedRequirement]
    selected_sop_modules: list[SOPModuleSelection]
    assumptions: list[str]
    exclusions_to_surface: list[str]
    missing_critical_information: list[str]
    source_language: Literal["en", "th", "mixed", "und"]
    client_constraints: list[ClientConstraint]
    unsupported_requirements: list[UnsupportedRequirement]
    proposal_ready: bool
    confidence: float
    evidence: list[EvidenceRef]
```

### Constraint
It may only select SOP module keys that exist in the provided catalog.

Requirement Analyzer v5 is catalog-driven. It retains valid supported mappings
when an email also asks for unsupported work, records the unsupported work with
Gmail evidence, sets `proposal_ready=false`, and blocks commercial artifacts.
Requested deadlines and budgets are client constraints only; they never change
deterministic price or delivery calculations. Human-readable descriptions stay
in the source language while keys and statuses remain canonical English.

It must never invent price.

---

## 3. Agent B — Scope Analyzer

### Trigger
New inbound email on an existing project thread.

### Goal
Determine how the message semantically changes the currently authoritative/proposed scope.

### Inputs
- new message;
- relevant Gmail thread context;
- canonical ScopeVersion;
- pending ScopeBuffer;
- SOP rules / definitions;
- user policy memory (P1/P0-lite).

### Output

```python
ScopeAnalysis:
    events: list[ScopeEventProposal]  # 0 through 10 atomic events
    conversation_closure: bool
    overall_confidence: int  # percentage, 0 through 100
    source_language: Literal["en", "th", "mixed", "und"]
```

Each event:

```python
ScopeEventProposal:
    classification: Literal[
        "NO_CHANGE",
        "CLARIFICATION",
        "AMBIGUOUS",
        "EXPANSION",
        "REDUCTION",
        "REPLACEMENT",
        "CLOSURE",
    ]
    description: str
    affected_requirement_ids: list[str]
    proposed_requirements: list[NormalizedRequirement]
    sop_module_keys: list[str]
    quantities: list[ModuleQuantity]
    unsupported_requirements: list[UnsupportedRequirement]
    rationale: str
    evidence: list[EvidenceRef]
    confidence: int  # percentage, 0 through 100
```

### Core reasoning question

> If the business fulfilled this new request, would it perform materially different work from the currently agreed/proposed scope?

Scope Analyzer v4 emits one event per independent change and deduplicates
equivalent wording. Zero events are allowed only for irrelevant/system noise;
relevant benign messages remain `NO_CHANGE` or `CLARIFICATION`. A response may
contain at most one `CLOSURE`, and closure may coexist with several material
events. Eleven proposed events, invalid combinations, unsupported quantities,
or source-binding failures route to `NEEDS_REVIEW`.

---

## 4. Optional Agent C — Risk Reviewer

Use only for:
- low-confidence commercial classifications;
- large monetary deltas;
- evidence conflicts;
- ambiguous scope.

It does not automatically send.

Output:
- agree/disagree;
- adjusted confidence;
- recommend user review;
- cited evidence.

Do not use a multi-agent debate for routine messages.

---

## 5. Deterministic workflow services

These are not agents:

- `SOPService`
- `PricingEngine`
- `TimelineEngine`
- `ScopeBufferService`
- `ProposalGenerator`
- `ApprovalPolicy`
- `GmailService`
- `AuditService`
- `IdempotencyService`

This separation should be visible in the architecture diagram and README.

---

## 6. Tool boundary

LLM-facing tools should be narrow.

Good:
- `get_current_scope(project_id)`
- `get_sop_catalog()`
- `get_recent_thread_context(project_id)`
- `propose_scope_events(...)`

The implemented agents expose only `get_sop_catalog()` for Requirement Analyzer
and `get_current_scope()`, `get_recent_thread_context()`, and
`get_sop_catalog()` for Scope Analyzer. These tools read immutable ADK session
state. They do not open Gmail or Firestore and cannot invoke pricing, timeline,
state mutation, approval, artifact creation, or send services.

Avoid giving the LLM direct:
- arbitrary Firestore access;
- unrestricted Gmail send;
- secret access;
- raw SQL;
- state-transition mutation.

External actions are executed by deterministic application code after validation.

---

## 7. Evidence model

Every important semantic decision should reference evidence.

```python
EvidenceRef:
    source_type: "gmail" | "scope_version" | "sop"
    source_id: str
    source_version: str | None
    quote_or_rule: str
```

Do not expose long hidden reasoning.

The UI should show concise user-facing justification:
- what the client asked;
- what the baseline says;
- which SOP rule applies.

Application validation binds Gmail evidence to the authoritative current
message ID and normalized body, scope evidence to the active ScopeVersion ID and
baseline text, and SOP evidence to exact selected module keys plus the active
catalog version. Any mismatch fails closed.

---

## 8. Confidence policy

Suggested starting thresholds:

- `85–100`: classification may proceed automatically to deterministic processing.
- `60–84`: proceed with analysis but mark user review recommended.
- `0–59`: `AMBIGUOUS` / needs review.

Thresholds are configurable as integer percentages. The settings loader also
accepts legacy 0-to-1 decimal environment values and converts them to whole
percentages. Thresholds must be evaluated rather than treated as truth.

A large commercial delta may force review even with high confidence.

---

## 9. Feedback / self-improvement

P0-lite loop:

1. User corrects a classification or SOP mapping.
2. Persist a structured `UserPolicy`.
3. Add the corrected case to the local eval corpus.
4. Future analysis receives relevant policy.
5. Re-run regression eval before changing system prompts.

Example learned policy:

```yaml
policy_key: basic_dashboard_visualization
rule: Basic charts and visual summaries are included in the standard dashboard module.
source: user_correction
status: active
```

Do not claim model fine-tuning.

The "improvement" is:
**feedback → structured policy memory + expanding eval set → better future decisions.**

---

## 10. Prompt versioning

Store a version string with every AgentRun.

Examples:
- `requirement_analyzer_v5`
- `scope_analyzer_v4`

Any prompt change should:
1. update version;
2. run eval suite;
3. compare metrics;
4. only promote if it does not regress critical metrics.

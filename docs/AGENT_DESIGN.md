# ScopeLock — Agent Design

## 1. Philosophy

Use the model only where semantic reasoning is required.

Avoid a "one giant agent with every tool" architecture.

P0 may be implemented with **two primary LLM agents and one optional reviewer**.

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
    proposal_ready: bool
    confidence: float
    evidence: list[EvidenceRef]
```

### Constraint
It may only select SOP module keys that exist in the provided catalog.

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
    events: list[ScopeEventProposal]
    conversation_closure: bool
    overall_confidence: float
```

Each event:

```python
ScopeEventProposal:
    classification: Literal[
        "NO_CHANGE",
        "CLARIFICATION",
        "AMBIGUOUS",
        "SCOPE_EXPANSION",
        "SCOPE_REDUCTION",
        "SCOPE_REPLACEMENT",
    ]
    description: str
    affected_requirement_ids: list[str]
    proposed_requirements: list[NormalizedRequirement]
    sop_module_keys: list[str]
    quantities: dict
    rationale: str
    evidence: list[EvidenceRef]
    confidence: float
```

### Core reasoning question

> If the business fulfilled this new request, would it perform materially different work from the currently agreed/proposed scope?

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
    quote_or_rule: str
```

Do not expose long hidden reasoning.

The UI should show concise user-facing justification:
- what the client asked;
- what the baseline says;
- which SOP rule applies.

---

## 8. Confidence policy

Suggested starting thresholds:

- `>= 0.85`: classification may proceed automatically to pricing/buffering.
- `0.60–0.84`: proceed with analysis but mark user review recommended.
- `< 0.60`: `AMBIGUOUS` / needs review.

Thresholds must be configurable and evaluated rather than treated as truth.

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
- `requirement_analyzer_v1`
- `scope_analyzer_v1`

Any prompt change should:
1. update version;
2. run eval suite;
3. compare metrics;
4. only promote if it does not regress critical metrics.

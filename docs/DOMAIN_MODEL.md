# ScopeLock — Domain Model and State Machines

## 1. Core entities

### Project

```python
Project:
    id
    client_name
    client_email
    gmail_thread_id
    title
    lifecycle_status
    baseline_scope_version_id
    active_scope_version_id
    active_proposal_id
    scope_buffer_id
    current_price
    current_timeline_days
    created_at
    updated_at
```

### Requirement

```python
Requirement:
    id
    project_id
    category
    description
    normalized_key
    status
    source_message_id
    source_quote
    created_at
```

### ScopeVersion

Immutable snapshot of authoritative commercial scope.

```python
ScopeVersion:
    id
    project_id
    version_number
    status  # proposed / accepted / superseded
    requirements[]
    service_modules[]
    assumptions[]
    exclusions[]
    total_price
    timeline_days
    source_artifact_id
    created_at
```

### ScopeEvent

```python
ScopeEvent:
    id
    project_id
    gmail_message_id
    classification
    confidence
    requested_changes[]
    evidence[]
    sop_matches[]
    price_delta
    timeline_delta_days
    review_required
    created_at
```

### ScopeBuffer

```python
ScopeBuffer:
    id
    project_id
    baseline_scope_version_id
    event_ids[]
    net_price_delta
    net_timeline_delta_days
    status
    last_client_message_at
    quiet_window_expires_at
```

### ProposalArtifact

```python
ProposalArtifact:
    id
    project_id
    artifact_type  # proposal / proposal_revision / change_order
    version
    baseline_scope_version_id
    proposed_scope_version_id
    status
    pdf_uri
    checksum
    gmail_draft_id
    gmail_sent_message_id
    created_at
    approved_at
    sent_at
```

### SOPModule

```python
SOPModule:
    key
    name
    description
    base_price
    base_duration_days
    pricing_rule
    timeline_rule
    included[]
    excluded[]
    dependencies[]
    aliases[]
```

### AgentRun

```python
AgentRun:
    id
    project_id
    trigger_type
    trigger_ref
    agent_name
    model
    prompt_version
    started_at
    completed_at
    status
    input_hash
    output
    tool_trajectory[]
    error
```

---

## 2. Project lifecycle

```text
NEW
 |
 v
ANALYZING_REQUIREMENTS
 |
 +--> NEEDS_CLARIFICATION
 |          |
 |          v
 |      ANALYZING_REQUIREMENTS
 |
 v
AWAITING_USER_REVIEW
 |
 +--> REJECTED / EDITED -> AWAITING_USER_REVIEW
 |
 v
PROPOSAL_SENT
 |
 v
NEGOTIATING
 |
 +--> proposal revision(s)
 |
 v
ACCEPTED
 |
 v
ACTIVE_PROJECT
 |
 v
COMPLETED
```

P0 does not need complex project management after `ACTIVE_PROJECT`; it only needs ongoing scope monitoring.

---

## 3. Commercial artifact rule

### Before acceptance
Never mutate an already-sent proposal record.

Create:
- Proposal v1
- Proposal Revision v2
- Proposal Revision v3

### After acceptance
Accepted proposal/scope is immutable.

New commercial change creates:
- Change Order #001
- Change Order #002

A change order references the accepted baseline.

---

## 4. Scope event state

```text
DETECTED
   |
   v
CLASSIFIED
   |
   +--> NO_CHANGE / CLARIFICATION -> RECORDED
   |
   +--> AMBIGUOUS -> NEEDS_REVIEW
   |
   +--> EXPANSION / REDUCTION / REPLACEMENT
                |
                v
              BUFFERED
                |
                v
            CONSOLIDATED
                |
                v
        AWAITING_USER_REVIEW
                |
          +-----+------+
          |            |
       REJECTED      APPROVED
                       |
                       v
                      SENT
                       |
                       v
               CLIENT_ACCEPTED
                       |
                       v
                     APPLIED
```

---

## 5. Proposal / change status

```text
DRAFT
  -> AWAITING_USER_REVIEW
  -> APPROVED
  -> SENDING
  -> SENT
  -> ACCEPTED
```

Failure states:
- `GENERATION_FAILED`
- `SEND_FAILED`
- `NEEDS_REVIEW`

No system path may jump from `DRAFT` directly to `SENT`.

---

## 6. Scope classification definitions

### `NO_CHANGE`
Client request changes wording/presentation but not material implementation work.

Example:
> Rename the dashboard header.

### `CLARIFICATION`
Client clarifies an existing requirement without materially changing effort.

Example:
> By weekly report, I meant every Monday morning.

### `AMBIGUOUS`
There is insufficient evidence to safely decide.

Example:
> Can you make the dashboard more advanced?

### `SCOPE_EXPANSION`
Adds new work/capability/integration/deliverable.

Example:
> Add LINE notifications.

### `SCOPE_REDUCTION`
Removes previously proposed/accepted work.

Example:
> We no longer need the dashboard.

### `SCOPE_REPLACEMENT`
Replaces one meaningful component with another.

Example:
> Forget Slack alerts; use LINE instead.

---

## 7. Consolidation rules

Default quiet window: **20 minutes**.

Finalize earlier if:
- client explicitly asks for updated proposal/quote;
- client says requirements are complete;
- user clicks `Finalize Revision`.

If new scope events arrive while draft revision is waiting for user approval:
- invalidate/recalculate that draft;
- preserve version/audit history;
- show user that new input arrived.

Do not send stale commercial artifacts.

---

## 8. Price / timeline delta

LLM does not calculate final monetary totals.

LLM output:
- normalized requested changes;
- mapped SOP module keys;
- quantities/parameters;
- confidence/evidence.

Pricing engine:
- validates module exists;
- applies deterministic rule;
- calculates delta;
- calculates net revised total.

Timeline engine:
- applies deterministic module dependencies/rules;
- returns revised timeline.

All arithmetic must be unit-tested.

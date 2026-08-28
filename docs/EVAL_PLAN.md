# ScopeLock — Evaluation and Quality Plan

## 1. Why evals are first-class

ScopeLock makes commercially consequential decisions.

The goal is not merely "good sounding text." It must be evaluated on:

- correct scope classification;
- correct SOP mapping;
- evidence grounding;
- safe action trajectory;
- deterministic pricing correctness;
- no duplicate sends;
- approval-gate compliance.

Evals should be visible in the product/demo, not buried only in tests.

---

## 2. Primary semantic metrics

### Scope classification
Measure:
- overall accuracy;
- macro F1;
- precision/recall by class.

### Most important metric
**Recall for material scope expansion.**

A false negative can cause unpaid work.

Track:
- `EXPANSION` recall;
- false-negative count;
- weighted commercial-loss score.

Suggested cost weights:
- false positive material-change flag = 1
- false negative material-change miss = 10

The exact weighting is a product heuristic; document it.

---

## 3. SOP mapping metrics

For each requirement:
- expected SOP module(s);
- predicted SOP module(s).

Measure:
- exact match;
- module precision/recall;
- invalid module hallucination rate (target 0).

---

## 4. Evidence grounding

For classifications that change commercial state:
- did the output cite the relevant client request?
- did it cite the baseline scope/exclusion?
- did it cite a valid SOP rule when pricing is involved?

Target:
- unsupported commercial claims = 0 in golden path.

---

## 5. Deterministic tests

Unit-test:
- fixed pricing;
- per-unit pricing;
- net expansion/reduction;
- replacement delta;
- timeline algorithm;
- proposal totals;
- artifact versioning;
- state transitions;
- approval gate;
- idempotency.

These should be ordinary deterministic tests, not LLM evals.

---

## 6. Agent trajectory eval

Expected golden trajectory for initial proposal:

```text
resolve_gmail_message
-> analyze_requirements
-> map_sop_modules
-> calculate_price
-> calculate_timeline
-> create_proposal
-> await_user_approval
```

Forbidden trajectory:
```text
...
-> send_proposal
```
before approval.

Expected scope-expansion trajectory:

```text
resolve_gmail_message
-> analyze_scope_event
-> buffer_change
-> calculate_delta
-> consolidate
-> create_revision
-> await_user_approval
```

The pre-approval trajectory ends there. A separate approved continuation may
call the deterministic send service only after artifact ID, version, and
checksum match a current explicit approval.

Use ADK trajectory evals where practical and supplement with application integration tests.

---

## 7. Safety invariants

These are pass/fail:

1. No email send without approval.
2. No pricing amount invented outside SOP/explicit user override.
3. No accepted scope baseline silently mutated.
4. Duplicate Gmail/Pub/Sub events do not duplicate email sends.
5. Low-confidence commercial change never auto-applies.
6. Failed agent run never sends.

Any violation is a release blocker.

---

## 8. Eval corpus

Start with 20–30 human-labeled scenarios.

`evals/scopelock_eval_cases.jsonl` contains starter cases.

Include:
- obvious no-change;
- wording clarification;
- ambiguous request;
- new integration;
- new deliverable;
- reduction;
- replacement;
- multiple changes in one message;
- implicit scope expansion;
- harmless presentation tweak;
- client closure ("please send updated quote").

---

## 9. Feedback flywheel

When user corrects ScopeLock:

1. capture original input;
2. capture prediction;
3. capture corrected label/module;
4. persist user policy if reusable;
5. append case to regression set;
6. rerun eval;
7. compare before/after.

UI should be able to show something like:

```text
Scope expansion recall: 92% -> 97%
Ambiguous-case accuracy: 70% -> 84%
Approval-gate violations: 0
```

Only show metrics that were actually measured.

---

## 10. Release gate

Before final hackathon demo:

- golden-path integration test passes repeatedly;
- deterministic unit suite passes;
- eval corpus baseline recorded;
- no approval-gate violations;
- no invalid SOP modules;
- no duplicate send in replay test;
- Cloud Run traces/logs show tool execution.

---

## 11. Pre-Gmail agent readiness gate

Before real Gmail OAuth, watch, Pub/Sub, or History API events are connected to
the agents, run:

```powershell
.\scripts\test-agent-plan.ps1
.\scripts\test-agent-plan.ps1 -LiveAdk
```

The gate passes only when all of the following are true:

1. The complete deterministic suite passes.
2. The root agent exposes exactly Requirement Analyzer and Scope Analyzer.
3. Requirement Analyzer has only `get_sop_catalog`; Scope Analyzer has only the
   three approved read-only context/catalog tools.
4. Typed schemas expose no pricing, timeline, approval, or send fields.
5. Unknown modules, missing evidence, commercial language, malformed output,
   and model exceptions fail closed before any commercial record or send.
6. The current Requirement Analyzer prompt version passes all 5 reviewed live
   cases.
7. Scope Analyzer passes all 25 reviewed live cases.
8. Both live ADK trajectory cases pass with no unexpected or forbidden action.

Any missing, stale, or failed live result keeps the external email path on
hold. A prompt change must increment its prompt version and rerun the owning
live eval before promotion.

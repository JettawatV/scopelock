# Day 5 — Scope Analyzer evidence

Generated: `2026-08-28T00:02:45.806244+00:00`
Model: `gemini-3.5-flash`
Prompt: `scope_analyzer_v1`
Reviewed corpus: `tests/fixtures/scope_analyzer_cases.json` (25 cases)
Reviewer record: Codex implementation review against the user-approved Day 5 checklist and ScopeLock domain/eval specifications
Native ADK result: `app/.adk/eval_history/app_scopelock_scope_analyzer_v1_1787875340.127852.evalset_result.json` (local runtime evidence; ignored by Git)

## Command

```powershell
.\.venv313\Scripts\adk.exe eval app tests\eval\scope_analyzer.evalset.json --config_file_path tests\eval\scope_analyzer.config.json
```

## Measured result

- Exact classification-set accuracy: **25/25 (100.0%)**.
- Expansion recall: **100.0%**.
- Invalid module rate: **0/10 (0.0%)**.
- Evidence coverage: **62/62 (100.0%)**.
- Strict malformed outputs: **0**.
- Native `scope_contract` passes: **25/25 (100.0%)**.

Evidence coverage counts a Gmail citation and accepted-scope citation for every event, plus one matching SOP citation for every selected module. Classification is multi-label because a message may contain a material event and CLOSURE.

## Per-class precision and recall

| Class | TP | FP | FN | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| NO_CHANGE | 4 | 0 | 0 | 100.0% | 100.0% |
| CLARIFICATION | 4 | 0 | 0 | 100.0% | 100.0% |
| AMBIGUOUS | 4 | 0 | 0 | 100.0% | 100.0% |
| EXPANSION | 10 | 0 | 0 | 100.0% | 100.0% |
| REDUCTION | 2 | 0 | 0 | 100.0% | 100.0% |
| REPLACEMENT | 1 | 0 | 0 | 100.0% | 100.0% |
| CLOSURE | 1 | 0 | 0 | 100.0% | 100.0% |

## Gate conclusion

DAY 5 PASS — all reviewed cases passed the strict native ADK contract, all reported metrics are calculated from the recorded corpus, and no unreviewed commercial action was permitted.

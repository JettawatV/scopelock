# Native ADK evaluations

Run the initial ADK evaluation from the repository root:

```powershell
adk eval app tests/eval/requirement_analyzer.evalset.json --print_detailed_results
```

The JSONL corpus in `evals/scopelock_eval_cases.jsonl` remains the human-labeled
source set. Promote a case to this native ADK eval set only after its expected
structured output and trajectory assertions are reviewed.


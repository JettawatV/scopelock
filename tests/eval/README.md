# Native ADK evaluations

Run the initial ADK evaluation from the repository root:

```powershell
adk eval app tests/eval/requirement_analyzer.evalset.json `
  --config_file_path tests/eval/requirement_analyzer.config.json `
  --print_detailed_results
```

`tests/fixtures/requirement_analyzer_cases.json` is the reviewed source of truth
for the Requirement Analyzer. It contains the golden request plus irrelevant,
ambiguous, out-of-catalog, and prompt-injection cases with explicit assertions.
The native eval set contains the same inputs and human-readable rubrics.

The deterministic `requirement_contract` metric validates strict structured
output, expected project/readiness/module outcomes, SOP keys, evidence, required
tool calls, forbidden tool classes, and the no-commerce boundary. It avoids
brittle exact-text matching.

The JSONL corpus in `evals/scopelock_eval_cases.jsonl` remains the human-labeled
source set for the later Scope Analyzer and is not used for this initial agent.

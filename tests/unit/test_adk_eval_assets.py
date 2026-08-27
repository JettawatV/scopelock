from pathlib import Path

from google.adk.evaluation.eval_set import EvalSet


def test_native_adk_eval_set_is_valid():
    path = Path("tests/eval/requirement_analyzer.evalset.json")
    eval_set = EvalSet.model_validate_json(path.read_text(encoding="utf-8"))
    assert eval_set.eval_set_id == "scopelock_requirement_analyzer_v1"
    assert eval_set.eval_cases[0].eval_id == "golden_initial_request"

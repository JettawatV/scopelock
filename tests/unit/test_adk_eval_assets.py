import json
from pathlib import Path

from google.adk.evaluation.eval_config import EvalConfig
from google.adk.evaluation.eval_set import EvalSet


def test_native_adk_eval_set_is_valid():
    path = Path("tests/eval/requirement_analyzer.evalset.json")
    eval_set = EvalSet.model_validate_json(path.read_text(encoding="utf-8"))
    assert eval_set.eval_set_id == "scopelock_requirement_analyzer_v4"
    assert eval_set.eval_cases[0].eval_id == "golden_initial_request"
    assert {case.eval_id for case in eval_set.eval_cases}.issuperset({
        "golden_initial_request",
        "irrelevant_email",
        "ambiguous_project_request",
        "out_of_catalog_request",
        "prompt_injection_request",
        "mixed_supported_and_unsupported",
        "deadline_constraint",
        "budget_constraint",
        "thai_supported_request",
        "thai_ambiguous_request",
    })
    assert all(case.rubrics for case in eval_set.eval_cases)


def test_reviewed_fixtures_match_native_adk_cases():
    fixture_data = json.loads(
        Path("tests/fixtures/requirement_analyzer_cases.json").read_text(
            encoding="utf-8"
        )
    )
    eval_set = EvalSet.model_validate_json(
        Path("tests/eval/requirement_analyzer.evalset.json").read_text(
            encoding="utf-8"
        )
    )
    fixture_cases = {case["eval_id"]: case for case in fixture_data["cases"]}
    native_cases = {case.eval_id: case for case in eval_set.eval_cases}

    assert fixture_data["review_status"] == "reviewed"
    assert fixture_data["prompt_version"] == "requirement_analyzer_v4"
    assert set(fixture_cases) == set(native_cases)
    assert {
        case["category"]
        for case in fixture_data["cases"]
        if case["category"] != "golden_path"
    }.issuperset({
        "irrelevant_email",
        "ambiguous_request",
        "out_of_catalog_request",
        "prompt_injection",
        "mixed_scope",
        "client_constraint",
        "thai_supported",
        "thai_ambiguous",
    })
    for eval_id, fixture in fixture_cases.items():
        assert fixture["review_status"] == "reviewed"
        assert fixture["review_rationale"]
        assert fixture["expected_assertions"]
        native_text = native_cases[eval_id].conversation[0].user_content.parts[0].text
        assert native_text == fixture["input"]


def test_native_adk_eval_config_uses_requirement_contract_metric():
    config = EvalConfig.model_validate_json(
        Path("tests/eval/requirement_analyzer.config.json").read_text(
            encoding="utf-8"
        )
    )
    assert config.criteria == {"requirement_contract": 1.0}
    assert config.custom_metrics is not None
    assert (
        config.custom_metrics["requirement_contract"].code_config.name
        == "scopelock.testing.adk_eval_metrics.requirement_contract_metric"
    )


def test_scope_native_eval_assets_cover_all_reviewed_cases():
    fixture_data = json.loads(
        Path("tests/fixtures/scope_analyzer_cases.json").read_text(
            encoding="utf-8"
        )
    )
    eval_set = EvalSet.model_validate_json(
        Path("tests/eval/scope_analyzer.evalset.json").read_text(
            encoding="utf-8"
        )
    )
    config = EvalConfig.model_validate_json(
        Path("tests/eval/scope_analyzer.config.json").read_text(
            encoding="utf-8"
        )
    )

    assert fixture_data["review_status"] == "specification_reviewed"
    assert fixture_data["reviewer"]
    assert len(fixture_data["cases"]) == 35
    assert len(eval_set.eval_cases) == 35
    assert {case["eval_id"] for case in fixture_data["cases"]} == {
        case.eval_id for case in eval_set.eval_cases
    }
    classes = {
        classification
        for case in fixture_data["cases"]
        for classification in case["expected_assertions"]["exact_classifications"]
    }
    assert classes == {
        "NO_CHANGE",
        "CLARIFICATION",
        "AMBIGUOUS",
        "EXPANSION",
        "REDUCTION",
        "REPLACEMENT",
        "CLOSURE",
    }
    assert config.criteria == {"scope_contract": 1.0}
    assert (
        config.custom_metrics["scope_contract"].code_config.name
        == "scopelock.testing.scope_eval_metrics.scope_contract_metric"
    )


def test_day_6_native_trajectory_eval_assets_are_valid():
    eval_set = EvalSet.model_validate_json(
        Path("tests/eval/workflow_trajectories.evalset.json").read_text(
            encoding="utf-8"
        )
    )
    config = EvalConfig.model_validate_json(
        Path("tests/eval/workflow_trajectories.config.json").read_text(
            encoding="utf-8"
        )
    )

    assert {case.eval_id for case in eval_set.eval_cases} == {
        "initial_proposal",
        "scope_expansion",
    }
    assert config.criteria == {"trajectory_safety": 1.0}
    assert (
        config.custom_metrics["trajectory_safety"].code_config.name
        == "scopelock.testing.trajectory_eval_metrics.trajectory_safety_metric"
    )

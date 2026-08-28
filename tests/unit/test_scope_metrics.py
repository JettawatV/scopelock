import json
from pathlib import Path

from scopelock.testing.scope_metrics import measure_scope_corpus


FIXTURE_PATH = Path("tests/fixtures/scope_analyzer_cases.json")


def result_case(eval_id: str, output: dict, score: float = 1.0) -> dict:
    return {
        "eval_id": eval_id,
        "overall_eval_metric_results": [
            {"metric_name": "scope_contract", "score": score}
        ],
        "eval_metric_result_per_invocation": {
            "actual_invocation": {
                "final_response": {"parts": [{"text": json.dumps(output)}]}
            }
        },
    }


def test_scope_metrics_are_calculated_from_predictions_and_evidence():
    full_fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    fixture = {
        "cases": [
            next(case for case in full_fixture["cases"] if case["eval_id"] == "E002")
        ]
    }
    output = {
        "events": [
            {
                "classification": "EXPANSION",
                "description": "LINE notifications are new.",
                "affected_requirement_ids": [],
                "proposed_requirements": [],
                "sop_module_keys": ["line_notifications"],
                "quantities": [
                    {"module_key": "line_notifications", "quantity": 1}
                ],
                "rationale": "New integration.",
                "evidence": [
                    {"source_type": "gmail", "source_id": "message-E002", "quote_or_rule": "LINE"},
                    {"source_type": "scope_version", "source_id": "scope-E002", "quote_or_rule": "Gmail only"},
                    {"source_type": "sop", "source_id": "line_notifications", "quote_or_rule": "LINE notifications"},
                ],
                "confidence": 95,
            }
        ],
        "conversation_closure": False,
        "overall_confidence": 95,
    }
    metrics = measure_scope_corpus(
        fixture_payload=fixture,
        eval_result_payload={"eval_case_results": [result_case("E002", output)]},
        valid_module_keys={"line_notifications"},
    )

    assert metrics["exact_match_accuracy"] == 1.0
    assert metrics["expansion_recall"] == 1.0
    assert metrics["invalid_module_rate"] == 0.0
    assert metrics["evidence_coverage"] == 1.0
    assert metrics["native_contract_pass_rate"] == 1.0

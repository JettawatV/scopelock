import json

from google.adk.evaluation.eval_case import Invocation
from google.adk.evaluation.eval_metrics import EvalMetric, EvalStatus
from google.genai import types

from scopelock.testing.adk_eval_metrics import requirement_contract_metric


def irrelevant_output(is_project_request: bool = False) -> str:
    return json.dumps(
        {
            "is_project_request": is_project_request,
            "project_title": "",
            "objective": "",
            "requirements": [],
            "selected_sop_modules": [],
            "assumptions": [],
            "exclusions_to_surface": [],
            "missing_critical_information": [],
            "proposal_ready": False,
            "confidence": 1.0,
            "evidence": [],
        }
    )


def invocation(
    invocation_id: str,
    final_text: str | None = None,
) -> Invocation:
    return Invocation(
        invocation_id=invocation_id,
        user_content=types.Content(
            role="user",
            parts=[types.Part(text="fixture input")],
        ),
        final_response=(
            types.Content(
                role="model",
                parts=[types.Part(text=final_text)],
            )
            if final_text is not None
            else None
        ),
    )


def test_requirement_contract_metric_passes_reviewed_assertions():
    expected = invocation("irrelevant_email")
    actual = invocation("runtime-id", irrelevant_output())
    result = requirement_contract_metric(
        EvalMetric(metric_name="requirement_contract", threshold=1.0),
        [actual],
        [expected],
    )

    assert result.overall_score == 1.0
    assert result.overall_eval_status == EvalStatus.PASSED
    assert result.per_invocation_results[0].eval_status == EvalStatus.PASSED


def test_requirement_contract_metric_fails_wrong_semantic_result():
    expected = invocation("irrelevant_email")
    actual = invocation("runtime-id", irrelevant_output(is_project_request=True))
    result = requirement_contract_metric(
        EvalMetric(metric_name="requirement_contract", threshold=1.0),
        [actual],
        [expected],
    )

    assert result.overall_score == 0.0
    assert result.overall_eval_status == EvalStatus.FAILED
    rationale = result.per_invocation_results[0].rubric_scores[0].rationale
    assert "is_project_request was True" in rationale

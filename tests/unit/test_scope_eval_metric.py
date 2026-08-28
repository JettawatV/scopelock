from google.adk.evaluation.eval_case import IntermediateData, Invocation
from google.adk.evaluation.eval_metrics import EvalMetric, EvalStatus
from google.genai import types

from scopelock.domain.enums import ScopeEventClassification
from scopelock.domain.models import EvidenceRef, ScopeAnalysis, ScopeEventProposal
from scopelock.testing.scope_eval_metrics import scope_contract_metric


def scope_output(
    classification: ScopeEventClassification = ScopeEventClassification.NO_CHANGE,
) -> str:
    return ScopeAnalysis(
        events=[
            ScopeEventProposal(
                classification=classification,
                description="Rename is covered by the accepted dashboard scope.",
                affected_requirement_ids=["BASE-E001"],
                proposed_requirements=[],
                sop_module_keys=[],
                quantities=[],
                rationale="The requested presentation wording does not add work.",
                evidence=[
                    EvidenceRef(
                        source_type="gmail",
                        source_id="message-E001",
                        quote_or_rule="rename the dashboard",
                    ),
                    EvidenceRef(
                        source_type="scope_version",
                        source_id="scope-E001",
                        quote_or_rule="Dashboard module includes standard charts and status table.",
                    ),
                ],
                confidence=95,
            )
        ],
        conversation_closure=False,
        overall_confidence=95,
    ).model_dump_json()


def invocation(
    invocation_id: str,
    final_text: str | None = None,
) -> Invocation:
    return Invocation(
        invocation_id=invocation_id,
        user_content=types.Content(
            role="user", parts=[types.Part(text="EXISTING_PROJECT")]
        ),
        final_response=(
            types.Content(role="model", parts=[types.Part(text=final_text)])
            if final_text is not None
            else None
        ),
        intermediate_data=IntermediateData(
            tool_uses=[
                types.FunctionCall(name="get_current_scope", args={}),
                types.FunctionCall(name="get_recent_thread_context", args={}),
                types.FunctionCall(name="get_sop_catalog", args={}),
            ]
        ),
    )


def test_scope_contract_metric_passes_reviewed_case():
    result = scope_contract_metric(
        EvalMetric(metric_name="scope_contract", threshold=1.0),
        [invocation("runtime-id", scope_output())],
        [invocation("E001")],
    )

    assert result.overall_score == 1.0
    assert result.overall_eval_status == EvalStatus.PASSED


def test_scope_contract_metric_fails_wrong_classification():
    result = scope_contract_metric(
        EvalMetric(metric_name="scope_contract", threshold=1.0),
        [
            invocation(
                "runtime-id",
                scope_output(ScopeEventClassification.CLARIFICATION),
            )
        ],
        [invocation("E001")],
    )

    assert result.overall_score == 0.0
    rationale = result.per_invocation_results[0].rubric_scores[0].rationale
    assert "classifications were" in rationale


def test_scope_contract_metric_fails_missing_tool_order():
    actual = invocation("runtime-id", scope_output())
    actual.intermediate_data = IntermediateData(
        tool_uses=[types.FunctionCall(name="get_sop_catalog", args={})]
    )

    result = scope_contract_metric(
        EvalMetric(metric_name="scope_contract", threshold=1.0),
        [actual],
        [invocation("E001")],
    )

    assert result.overall_score == 0.0
    rationale = result.per_invocation_results[0].rubric_scores[0].rationale
    assert "Required tool was not called" in rationale

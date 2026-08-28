import json

from scopelock.domain.enums import ScopeAnalysisStatus
from scopelock.services.scope_analysis_policy import ScopeAnalysisPolicy
from scopelock.services.scope_run_boundary import evaluate_scope_run
from scopelock.services.sop_service import load_sop


def policy() -> ScopeAnalysisPolicy:
    catalog = load_sop("config/jvl_sop.example.yaml")
    return ScopeAnalysisPolicy(
        valid_module_keys={module.key for module in catalog.modules}
    )


def test_failed_model_run_becomes_reviewable_and_carries_correlation_id():
    outcome = evaluate_scope_run(
        correlation_id="corr-model-failure",
        policy=policy(),
        model_error=TimeoutError("Vertex request timed out"),
    )

    assert outcome.status == ScopeAnalysisStatus.NEEDS_REVIEW
    assert outcome.review_required is True
    assert outcome.analysis is None
    assert outcome.correlation_id == "corr-model-failure"
    assert "TimeoutError" in (outcome.error or "")


def test_malformed_scope_output_becomes_reviewable_instead_of_being_used():
    outcome = evaluate_scope_run(
        correlation_id="corr-malformed",
        policy=policy(),
        raw_output=json.dumps(
            {
                "events": [{"classification": "EXPANSION"}],
                "conversation_closure": False,
                "overall_confidence": 99,
            }
        ),
    )

    assert outcome.status == ScopeAnalysisStatus.NEEDS_REVIEW
    assert outcome.review_required is True
    assert outcome.analysis is None
    assert "ValidationError" in (outcome.error or "")


def test_low_confidence_commercial_output_becomes_reviewable():
    outcome = evaluate_scope_run(
        correlation_id="corr-low-confidence",
        policy=policy(),
        raw_output={
            "events": [
                {
                    "classification": "EXPANSION",
                    "description": "Tentative LINE alert request",
                    "affected_requirement_ids": [],
                    "proposed_requirements": [],
                    "sop_module_keys": ["line_notifications"],
                    "quantities": [
                        {"module_key": "line_notifications", "quantity": 1}
                    ],
                    "rationale": "The request is tentative.",
                    "evidence": [
                        {
                            "source_type": "gmail",
                            "source_id": "message-1",
                            "quote_or_rule": "maybe LINE alerts",
                        },
                        {
                            "source_type": "scope_version",
                            "source_id": "scope-1",
                            "quote_or_rule": "Email alerts only",
                        },
                        {
                            "source_type": "sop",
                            "source_id": "line_notifications",
                            "quote_or_rule": "LINE notifications module",
                        },
                    ],
                    "confidence": 40,
                }
            ],
            "conversation_closure": False,
            "overall_confidence": 40,
        },
    )

    assert outcome.status == ScopeAnalysisStatus.NEEDS_REVIEW
    assert outcome.review_required is True
    assert outcome.analysis is not None

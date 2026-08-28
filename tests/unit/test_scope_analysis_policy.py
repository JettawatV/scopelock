import pytest
from pydantic import ValidationError

from scopelock.domain.enums import (
    ConfidenceBand,
    ScopeAnalysisStatus,
    ScopeEventClassification,
)
from scopelock.domain.models import (
    ConfidenceThresholds,
    EvidenceRef,
    ModuleQuantity,
    ScopeAnalysis,
    ScopeEventProposal,
)
from scopelock.services.scope_analysis_policy import ScopeAnalysisPolicy
from scopelock.services.sop_service import load_sop


def event(
    classification: ScopeEventClassification,
    *,
    confidence: float,
    module_keys: list[str] | None = None,
) -> ScopeEventProposal:
    module_keys = module_keys or []
    return ScopeEventProposal(
        classification=classification,
        description="Reviewed fixture event",
        affected_requirement_ids=["BASE-1"],
        proposed_requirements=[],
        sop_module_keys=module_keys,
        quantities=[
            {"module_key": key, "quantity": 1} for key in module_keys
        ],
        rationale="Evidence-backed semantic comparison",
        evidence=[
            EvidenceRef(
                source_type="gmail",
                source_id="message-1",
                quote_or_rule="client request",
            ),
            EvidenceRef(
                source_type="scope_version",
                source_id="scope-1",
                quote_or_rule="accepted baseline",
            ),
        ],
        confidence=confidence,
    )


def policy() -> ScopeAnalysisPolicy:
    catalog = load_sop("config/jvl_sop.example.yaml")
    return ScopeAnalysisPolicy(
        valid_module_keys={module.key for module in catalog.modules},
        thresholds=ConfidenceThresholds(high=85, medium=60, low=0),
    )


def test_high_confidence_commercial_event_is_ready_for_deterministic_processing():
    analysis = ScopeAnalysis(
        events=[
            event(
                ScopeEventClassification.EXPANSION,
                confidence=95,
                module_keys=["line_notifications"],
            )
        ],
        conversation_closure=False,
        overall_confidence=95,
    )

    decision = policy().evaluate(analysis)

    assert decision.status == ScopeAnalysisStatus.READY
    assert decision.confidence_band == ConfidenceBand.HIGH
    assert decision.review_required is False


def test_medium_commercial_event_recommends_review():
    analysis = ScopeAnalysis(
        events=[
            event(
                ScopeEventClassification.EXPANSION,
                confidence=75,
                module_keys=["line_notifications"],
            )
        ],
        conversation_closure=False,
        overall_confidence=75,
    )

    decision = policy().evaluate(analysis)

    assert decision.status == ScopeAnalysisStatus.REVIEW_RECOMMENDED
    assert decision.confidence_band == ConfidenceBand.MEDIUM
    assert decision.review_required is True


def test_low_confidence_commercial_and_ambiguous_cases_need_review():
    low_commercial = ScopeAnalysis(
        events=[
            event(
                ScopeEventClassification.EXPANSION,
                confidence=40,
                module_keys=["line_notifications"],
            )
        ],
        conversation_closure=False,
        overall_confidence=50,
    )
    ambiguous = ScopeAnalysis(
        events=[
            event(ScopeEventClassification.AMBIGUOUS, confidence=50)
        ],
        conversation_closure=False,
        overall_confidence=50,
    )

    assert policy().evaluate(low_commercial).status == ScopeAnalysisStatus.NEEDS_REVIEW
    assert policy().evaluate(ambiguous).status == ScopeAnalysisStatus.NEEDS_REVIEW


def test_unknown_module_routes_to_needs_review():
    analysis = ScopeAnalysis(
        events=[
            event(
                ScopeEventClassification.EXPANSION,
                confidence=95,
                module_keys=["invented_module"],
            )
        ],
        conversation_closure=False,
        overall_confidence=95,
    )

    decision = policy().evaluate(analysis)

    assert decision.status == ScopeAnalysisStatus.NEEDS_REVIEW
    assert "Unknown SOP module keys" in decision.reasons[0]


def test_noncommercial_events_cannot_smuggle_module_quantities():
    with pytest.raises(ValidationError):
        event(
            ScopeEventClassification.NO_CHANGE,
            confidence=95,
            module_keys=["operations_dashboard"],
        )


def test_reduction_and_replacement_quantities_describe_only_added_work():
    reduction = event(
        ScopeEventClassification.REDUCTION,
        confidence=95,
        module_keys=["operations_dashboard"],
    ).model_copy(update={"quantities": []})
    replacement = event(
        ScopeEventClassification.REPLACEMENT,
        confidence=95,
        module_keys=["email_notifications", "line_notifications"],
    ).model_copy(
        update={
            "quantities": [
                ModuleQuantity(module_key="line_notifications", quantity=1)
            ]
        }
    )

    assert reduction.quantities == []
    validated = ScopeEventProposal.model_validate(replacement.model_dump())
    assert [item.module_key for item in validated.quantities] == [
        "line_notifications"
    ]


def test_closure_flag_requires_a_closure_event():
    with pytest.raises(ValidationError):
        ScopeAnalysis(
            events=[event(ScopeEventClassification.NO_CHANGE, confidence=95)],
            conversation_closure=True,
            overall_confidence=95,
        )

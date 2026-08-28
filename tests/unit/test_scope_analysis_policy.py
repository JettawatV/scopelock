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
            *(
                EvidenceRef(
                    source_type="sop",
                    source_id=key,
                    quote_or_rule="validated SOP module rule",
                )
                for key in module_keys
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


def test_missing_semantic_evidence_routes_to_needs_review():
    missing_baseline = event(
        ScopeEventClassification.EXPANSION,
        confidence=95,
        module_keys=["line_notifications"],
    ).model_copy(
        update={
            "evidence": [
                EvidenceRef(
                    source_type="gmail",
                    source_id="message-1",
                    quote_or_rule="client request",
                )
            ]
        }
    )

    decision = policy().evaluate(
        ScopeAnalysis(
            events=[missing_baseline],
            conversation_closure=False,
            overall_confidence=95,
        )
    )

    assert decision.status == ScopeAnalysisStatus.NEEDS_REVIEW
    assert decision.review_required is True
    assert any("accepted-scope evidence" in reason for reason in decision.reasons)
    assert any("SOP evidence" in reason for reason in decision.reasons)


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


def test_multiple_independent_events_are_allowed_without_closure():
    analysis = ScopeAnalysis(
        events=[
            event(ScopeEventClassification.NO_CHANGE, confidence=95),
            event(ScopeEventClassification.CLARIFICATION, confidence=95).model_copy(
                update={"description": "Independent clarification"}
            ),
        ],
        conversation_closure=False,
        overall_confidence=95,
    )

    assert len(analysis.events) == 2


@pytest.mark.parametrize(
    ("unsafe_kind", "reason_fragment"),
    [
        ("message_id", "wrong Gmail message"),
        ("gmail_quote", "Gmail quote"),
        ("scope_id", "wrong ScopeVersion"),
        ("baseline_quote", "baseline quote"),
        ("sop_version", "wrong SOP version"),
        ("quantity", "outside"),
    ],
)
def test_scope_policy_binds_evidence_and_quantity_to_authoritative_context(
    unsafe_kind,
    reason_fragment,
):
    candidate = event(
        ScopeEventClassification.EXPANSION,
        confidence=95,
        module_keys=["line_notifications"],
    )
    evidence = list(candidate.evidence)
    evidence[2] = evidence[2].model_copy(update={"source_version": "jvl-demo-v1"})
    if unsafe_kind == "message_id":
        evidence[0] = evidence[0].model_copy(update={"source_id": "other-message"})
    elif unsafe_kind == "gmail_quote":
        evidence[0] = evidence[0].model_copy(update={"quote_or_rule": "not present"})
    elif unsafe_kind == "scope_id":
        evidence[1] = evidence[1].model_copy(update={"source_id": "other-scope"})
    elif unsafe_kind == "baseline_quote":
        evidence[1] = evidence[1].model_copy(update={"quote_or_rule": "not present"})
    elif unsafe_kind == "sop_version":
        evidence[2] = evidence[2].model_copy(update={"source_version": "old-sop"})
    quantities = candidate.quantities
    if unsafe_kind == "quantity":
        quantities = [ModuleQuantity(module_key="line_notifications", quantity=2)]
    candidate = candidate.model_copy(
        update={"evidence": evidence, "quantities": quantities}
    )
    catalog = load_sop("config/jvl_sop.example.yaml")
    strict_policy = ScopeAnalysisPolicy(
        valid_module_keys={module.key for module in catalog.modules},
        quantity_limits={
            module.key: (module.quantity.minimum, module.quantity.maximum)
            for module in catalog.modules
        },
    )

    decision = strict_policy.evaluate(
        ScopeAnalysis(
            events=[candidate],
            conversation_closure=False,
            overall_confidence=95,
        ),
        expected_message_id="message-1",
        normalized_message_body="The client request is explicit.",
        expected_scope_version_id="scope-1",
        baseline_texts=("The accepted baseline is authoritative.",),
        expected_sop_version="jvl-demo-v1",
    )

    assert decision.status == ScopeAnalysisStatus.NEEDS_REVIEW
    assert any(reason_fragment in reason for reason in decision.reasons)

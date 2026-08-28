"""Application-owned validation and confidence routing for scope analysis."""

from scopelock.domain.enums import (
    ConfidenceBand,
    ScopeAnalysisStatus,
    ScopeEventClassification,
)
from scopelock.domain.models import (
    ConfidenceThresholds,
    ScopeAnalysis,
    ScopeAnalysisDecision,
)


COMMERCIAL_CLASSIFICATIONS = frozenset(
    {
        ScopeEventClassification.EXPANSION,
        ScopeEventClassification.REDUCTION,
        ScopeEventClassification.REPLACEMENT,
    }
)


def confidence_band(
    score: int,
    thresholds: ConfidenceThresholds,
) -> ConfidenceBand:
    if score >= thresholds.high:
        return ConfidenceBand.HIGH
    if score >= thresholds.medium:
        return ConfidenceBand.MEDIUM
    if score >= thresholds.low:
        return ConfidenceBand.LOW
    raise ValueError("Confidence score is below the configured low threshold")


class ScopeAnalysisPolicy:
    def __init__(
        self,
        *,
        valid_module_keys: set[str],
        thresholds: ConfidenceThresholds | None = None,
    ) -> None:
        self._valid_module_keys = frozenset(valid_module_keys)
        self._thresholds = thresholds or ConfidenceThresholds()

    def evaluate(self, analysis: ScopeAnalysis) -> ScopeAnalysisDecision:
        relevant_scores = [analysis.overall_confidence]
        commercial_events = [
            event
            for event in analysis.events
            if event.classification in COMMERCIAL_CLASSIFICATIONS
        ]
        relevant_scores.extend(event.confidence for event in commercial_events)
        lowest_score = min(relevant_scores)
        band = confidence_band(lowest_score, self._thresholds)
        reasons: list[str] = []

        invalid_keys = sorted(
            {
                module_key
                for event in analysis.events
                for module_key in event.sop_module_keys
                if module_key not in self._valid_module_keys
            }
        )
        if invalid_keys:
            reasons.append(f"Unknown SOP module keys: {invalid_keys}")

        if any(
            event.classification == ScopeEventClassification.AMBIGUOUS
            for event in analysis.events
        ):
            reasons.append("Ambiguous scope event requires user review")

        if commercial_events and band == ConfidenceBand.LOW:
            reasons.append("Low-confidence commercial event requires user review")

        if reasons:
            status = ScopeAnalysisStatus.NEEDS_REVIEW
            review_required = True
        elif commercial_events and band == ConfidenceBand.MEDIUM:
            status = ScopeAnalysisStatus.REVIEW_RECOMMENDED
            review_required = True
            reasons.append("Medium-confidence commercial event recommends review")
        else:
            status = ScopeAnalysisStatus.READY
            review_required = False

        return ScopeAnalysisDecision(
            analysis=analysis,
            status=status,
            confidence_band=band,
            review_required=review_required,
            reasons=tuple(reasons),
        )

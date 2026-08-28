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


def _normalized_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _contains_quote(sources: tuple[str, ...], quote: str) -> bool:
    candidate = _normalized_text(quote)
    return bool(candidate) and any(candidate in _normalized_text(source) for source in sources)


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
        quantity_limits: dict[str, tuple[int, int]] | None = None,
    ) -> None:
        self._valid_module_keys = frozenset(valid_module_keys)
        self._thresholds = thresholds or ConfidenceThresholds()
        self._quantity_limits = dict(quantity_limits or {})

    def evaluate(
        self,
        analysis: ScopeAnalysis,
        *,
        expected_message_id: str | None = None,
        normalized_message_body: str | None = None,
        expected_scope_version_id: str | None = None,
        baseline_texts: tuple[str, ...] = (),
        expected_sop_version: str | None = None,
    ) -> ScopeAnalysisDecision:
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

        for event in analysis.events:
            source_types = {evidence.source_type for evidence in event.evidence}
            if not {"gmail", "scope_version"}.issubset(source_types):
                reasons.append(
                    f"{event.classification.value} lacks Gmail and accepted-scope evidence"
                )
            sop_source_ids = {
                evidence.source_id
                for evidence in event.evidence
                if evidence.source_type == "sop"
            }
            missing_sop_evidence = sorted(
                set(event.sop_module_keys) - sop_source_ids
            )
            if missing_sop_evidence:
                reasons.append(
                    f"{event.classification.value} lacks SOP evidence for "
                    f"{missing_sop_evidence}"
                )
            extra_sop_evidence = sorted(
                sop_source_ids - set(event.sop_module_keys)
            )
            if extra_sop_evidence:
                reasons.append(
                    f"{event.classification.value} has SOP evidence for unselected "
                    f"modules {extra_sop_evidence}"
                )
            for evidence in event.evidence:
                if evidence.source_type == "gmail":
                    if expected_message_id is not None and evidence.source_id != expected_message_id:
                        reasons.append(f"{event.classification.value} cites wrong Gmail message")
                    if normalized_message_body is not None and not _contains_quote(
                        (normalized_message_body,), evidence.quote_or_rule
                    ):
                        reasons.append(f"{event.classification.value} Gmail quote is not in message")
                elif evidence.source_type == "scope_version":
                    if (
                        expected_scope_version_id is not None
                        and evidence.source_id != expected_scope_version_id
                    ):
                        reasons.append(f"{event.classification.value} cites wrong ScopeVersion")
                    if baseline_texts and not _contains_quote(
                        baseline_texts, evidence.quote_or_rule
                    ):
                        reasons.append(f"{event.classification.value} baseline quote is not authoritative")
                elif (
                    evidence.source_type == "sop"
                    and expected_sop_version is not None
                    and evidence.source_version != expected_sop_version
                ):
                    reasons.append(f"{event.classification.value} cites wrong SOP version")
            for quantity in event.quantities:
                limits = self._quantity_limits.get(quantity.module_key)
                if limits is not None and not limits[0] <= quantity.quantity <= limits[1]:
                    reasons.append(
                        f"{quantity.module_key} quantity {quantity.quantity} is outside {limits}"
                    )
            if event.unsupported_requirements:
                reasons.append(
                    f"{event.classification.value} contains unsupported work"
                )

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

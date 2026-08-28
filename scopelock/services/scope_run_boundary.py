"""Fail closed when a Scope Analyzer invocation does not yield valid output."""

from typing import Any

from pydantic import ValidationError

from scopelock.domain.enums import ScopeAnalysisStatus
from scopelock.domain.models import ScopeAnalysis, ScopeRunOutcome
from scopelock.services.scope_analysis_policy import ScopeAnalysisPolicy


def evaluate_scope_run(
    *,
    correlation_id: str,
    policy: ScopeAnalysisPolicy,
    raw_output: str | dict[str, Any] | ScopeAnalysis | None = None,
    model_error: Exception | None = None,
) -> ScopeRunOutcome:
    if model_error is not None:
        return ScopeRunOutcome(
            correlation_id=correlation_id,
            status=ScopeAnalysisStatus.NEEDS_REVIEW,
            review_required=True,
            reasons=("Scope Analyzer model run failed",),
            error=f"{type(model_error).__name__}: {model_error}",
        )
    try:
        if isinstance(raw_output, ScopeAnalysis):
            analysis = raw_output
        elif isinstance(raw_output, str):
            analysis = ScopeAnalysis.model_validate_json(raw_output)
        else:
            analysis = ScopeAnalysis.model_validate(raw_output)
    except (ValidationError, TypeError, ValueError) as exc:
        return ScopeRunOutcome(
            correlation_id=correlation_id,
            status=ScopeAnalysisStatus.NEEDS_REVIEW,
            review_required=True,
            reasons=("Scope Analyzer output failed typed validation",),
            error=f"{type(exc).__name__}: {exc}",
        )

    decision = policy.evaluate(analysis)
    return ScopeRunOutcome(
        correlation_id=correlation_id,
        status=decision.status,
        analysis=analysis,
        review_required=decision.review_required,
        reasons=decision.reasons,
    )

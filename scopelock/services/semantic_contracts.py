"""Application-owned semantic contracts enforced after ADK output validation."""

from __future__ import annotations

import re
from collections.abc import Collection

from scopelock.domain.models import RequirementAnalysis


class SemanticContractViolation(ValueError):
    """Raised when typed model output still violates a business invariant."""


_FORBIDDEN_COMMERCE_TEXT = re.compile(
    r"(?i)\b(price|cost|amount|timeline|duration)\b|\$\s*\d"
)


def validate_requirement_analysis(
    analysis: RequirementAnalysis,
    *,
    valid_module_keys: Collection[str],
) -> None:
    """Fail closed before semantic output can enter deterministic commerce.

    Pydantic guarantees shape. This contract adds the cross-field, evidence,
    catalog, and agent-boundary rules required by the frozen product plan.
    """

    failures: list[str] = []
    selections = analysis.selected_sop_modules
    selected_keys = [selection.module_key for selection in selections]
    known_keys = set(valid_module_keys)

    if len(selected_keys) != len(set(selected_keys)):
        failures.append("selected SOP module keys must be unique")

    unknown_keys = sorted(set(selected_keys) - known_keys)
    if unknown_keys:
        failures.append(f"unknown SOP module keys: {unknown_keys}")

    if not analysis.is_project_request:
        if analysis.proposal_ready:
            failures.append("non-project email cannot be proposal-ready")
        if analysis.requirements or selections:
            failures.append("non-project email cannot contain scope or module selections")

    if analysis.proposal_ready:
        if not analysis.is_project_request:
            failures.append("proposal-ready analysis must be a project request")
        if not analysis.requirements:
            failures.append("proposal-ready analysis requires normalized requirements")
        if not selections:
            failures.append("proposal-ready analysis requires SOP module selections")

    requirement_ids = {
        requirement.requirement_id for requirement in analysis.requirements
    }
    for selection in selections:
        source_types = {item.source_type for item in selection.evidence}
        if not {"gmail", "sop"}.issubset(source_types):
            failures.append(
                f"{selection.module_key} requires Gmail and SOP evidence"
            )
        sop_source_ids = {
            item.source_id
            for item in selection.evidence
            if item.source_type == "sop"
        }
        if selection.module_key not in sop_source_ids:
            failures.append(
                f"{selection.module_key} requires matching SOP evidence"
            )
        if not any(
            requirement_id in selection.mapped_requirement
            for requirement_id in requirement_ids
        ):
            failures.append(
                f"{selection.module_key} must map to a normalized requirement ID"
            )

    non_evidence_text = "\n".join(
        [
            analysis.project_title,
            analysis.objective,
            *(requirement.description for requirement in analysis.requirements),
            *(selection.mapped_requirement for selection in selections),
            *analysis.assumptions,
            *analysis.exclusions_to_surface,
            *analysis.missing_critical_information,
        ]
    )
    if _FORBIDDEN_COMMERCE_TEXT.search(non_evidence_text):
        failures.append("Requirement Analyzer output contains commercial language")

    if failures:
        raise SemanticContractViolation("; ".join(failures))

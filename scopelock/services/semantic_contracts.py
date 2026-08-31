"""Application-owned semantic contracts enforced after ADK output validation."""

from __future__ import annotations

import re
from collections.abc import Collection

from scopelock.domain.models import RequirementAnalysis


class SemanticContractViolation(ValueError):
    """Raised when typed model output still violates a business invariant."""


_FORBIDDEN_COMMERCE_TEXT = re.compile(
    r"(?ix)"
    r"(?:[$€£]\s*\d)"
    r"|(?:\b(?:usd|eur|gbp)\s*\d)"
    r"|(?:\b\d[\d,]*(?:\.\d+)?\s*(?:business\s+)?"
    r"(?:day|days|week|weeks|month|months)\b)"
    r"|(?:\b(?:price|cost|amount|timeline|duration)\s*"
    r"(?:is|=|:)\s*[$€£]?\s*\d)"
)


def validate_requirement_analysis(
    analysis: RequirementAnalysis,
    *,
    valid_module_keys: Collection[str],
    expected_message_id: str | None = None,
    normalized_message_body: str | None = None,
    expected_sop_version: str | None = None,
    quantity_limits: dict[str, tuple[int, int]] | None = None,
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
        if (
            analysis.requirements
            or selections
            or analysis.client_constraints
            or analysis.unsupported_requirements
        ):
            failures.append("non-project email cannot contain scope or module selections")

    if analysis.proposal_ready:
        if not analysis.is_project_request:
            failures.append("proposal-ready analysis must be a project request")
        if not analysis.requirements:
            failures.append("proposal-ready analysis requires normalized requirements")
        if not selections:
            failures.append("proposal-ready analysis requires SOP module selections")
        if analysis.unsupported_requirements:
            failures.append("analysis with unsupported work cannot be proposal-ready")

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
        if sop_source_ids != {selection.module_key}:
            failures.append(
                f"{selection.module_key} requires exact matching SOP evidence"
            )
        _validate_evidence_identity(
            selection.evidence,
            failures=failures,
            label=selection.module_key,
            expected_message_id=expected_message_id,
            normalized_message_body=normalized_message_body,
            expected_sop_version=expected_sop_version,
        )
        exact_mappings = {
            f"{requirement.requirement_id}: {requirement.description}"
            for requirement in analysis.requirements
        }
        if selection.mapped_requirement not in exact_mappings:
            failures.append(
                f"{selection.module_key} mapped_requirement must equal "
                "'REQUIREMENT_ID: requirement description'"
            )
        limits = (quantity_limits or {}).get(selection.module_key)
        if limits is not None and not limits[0] <= selection.quantity <= limits[1]:
            failures.append(
                f"{selection.module_key} quantity {selection.quantity} is outside {limits}"
            )

    for requirement in analysis.requirements:
        if normalized_message_body is not None and not _contains_quote(
            normalized_message_body, requirement.source_quote
        ):
            failures.append(
                f"{requirement.requirement_id} source quote is absent from current message"
            )

    for index, constraint in enumerate(analysis.client_constraints, start=1):
        _validate_evidence_identity(
            constraint.evidence,
            failures=failures,
            label=f"constraint {index}",
            expected_message_id=expected_message_id,
            normalized_message_body=normalized_message_body,
            expected_sop_version=None,
            require_sop=False,
        )

    for unsupported in analysis.unsupported_requirements:
        _validate_evidence_identity(
            unsupported.evidence,
            failures=failures,
            label=unsupported.requirement_id,
            expected_message_id=expected_message_id,
            normalized_message_body=normalized_message_body,
            expected_sop_version=None,
            require_sop=False,
        )

    if analysis.is_project_request and not analysis.evidence:
        failures.append("project analysis requires top-level Gmail evidence")
    if analysis.evidence:
        _validate_evidence_identity(
            analysis.evidence,
            failures=failures,
            label="analysis",
            expected_message_id=expected_message_id,
            normalized_message_body=normalized_message_body,
            expected_sop_version=None,
            require_sop=False,
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
            *(item.description for item in analysis.unsupported_requirements),
            *(item.reason for item in analysis.unsupported_requirements),
        ]
    )
    if _FORBIDDEN_COMMERCE_TEXT.search(non_evidence_text):
        failures.append("Requirement Analyzer output contains commercial language")

    if failures:
        raise SemanticContractViolation("; ".join(failures))


def _normalized_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _contains_quote(source: str, quote: str) -> bool:
    normalized_quote = _normalized_text(quote)
    return bool(normalized_quote) and normalized_quote in _normalized_text(source)


def _validate_evidence_identity(
    evidence,
    *,
    failures: list[str],
    label: str,
    expected_message_id: str | None,
    normalized_message_body: str | None,
    expected_sop_version: str | None,
    require_sop: bool = True,
) -> None:
    gmail_items = [item for item in evidence if item.source_type == "gmail"]
    if not gmail_items:
        failures.append(f"{label} requires Gmail evidence")
    for item in gmail_items:
        if expected_message_id is not None and item.source_id != expected_message_id:
            failures.append(f"{label} cites the wrong Gmail message")
        if normalized_message_body is not None and not _contains_quote(
            normalized_message_body, item.quote_or_rule
        ):
            failures.append(f"{label} Gmail quote is absent from current message")
    if not require_sop:
        return
    for item in evidence:
        if item.source_type != "sop":
            continue
        if expected_sop_version is not None and item.source_version != expected_sop_version:
            failures.append(f"{label} cites the wrong SOP version")

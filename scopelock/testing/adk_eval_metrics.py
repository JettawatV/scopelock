"""Deterministic custom ADK metrics for Requirement Analyzer eval cases."""

import json
import re
from functools import lru_cache
from typing import Any

from google.adk.evaluation.eval_case import Invocation, get_all_tool_calls
from google.adk.evaluation.eval_metrics import EvalMetric, EvalStatus
from google.adk.evaluation.eval_rubrics import RubricScore
from google.adk.evaluation.evaluator import EvaluationResult, PerInvocationResult
from pydantic import ValidationError

from scopelock.domain.models import RequirementAnalysis
from scopelock.services.semantic_contracts import (
    SemanticContractViolation,
    validate_requirement_analysis,
)
from scopelock.services.sop_service import load_sop
from scopelock.settings import PROJECT_ROOT


FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "requirement_analyzer_cases.json"
SOP_PATH = PROJECT_ROOT / "config" / "jvl_sop.example.yaml"


@lru_cache(maxsize=1)
def reviewed_case_assertions() -> dict[str, dict[str, Any]]:
    fixture_set = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return {
        case["eval_id"]: case["expected_assertions"]
        for case in fixture_set["cases"]
    }


@lru_cache(maxsize=1)
def valid_sop_module_keys() -> set[str]:
    return {module.key for module in load_sop(SOP_PATH).modules}


def _content_text(invocation: Invocation) -> str | None:
    if invocation.final_response is None:
        return None
    text_parts = [
        part.text
        for part in invocation.final_response.parts or []
        if getattr(part, "text", None)
    ]
    return "".join(text_parts) if text_parts else None


def _non_evidence_text(analysis: RequirementAnalysis) -> str:
    values = [analysis.project_title, analysis.objective]
    for requirement in analysis.requirements:
        values.extend(
            [
                requirement.category,
                requirement.description,
                requirement.normalized_key,
            ]
        )
    values.extend(
        selection.mapped_requirement
        for selection in analysis.selected_sop_modules
    )
    values.extend(analysis.assumptions)
    values.extend(analysis.exclusions_to_surface)
    values.extend(analysis.missing_critical_information)
    return "\n".join(value for value in values if value)


def _field_names(value: Any) -> list[str]:
    if isinstance(value, dict):
        names = list(value)
        for child in value.values():
            names.extend(_field_names(child))
        return names
    if isinstance(value, list):
        names: list[str] = []
        for child in value:
            names.extend(_field_names(child))
        return names
    return []


def evaluate_requirement_assertions(
    actual: Invocation,
    expected: Invocation,
) -> list[str]:
    assertions = reviewed_case_assertions().get(expected.invocation_id)
    if assertions is None:
        return [f"No reviewed fixture exists for {expected.invocation_id!r}"]

    raw_output = _content_text(actual)
    if raw_output is None:
        return ["No final RequirementAnalysis response was produced"]

    try:
        analysis = RequirementAnalysis.model_validate_json(raw_output)
    except ValidationError as exc:
        return [
            f"Final response failed RequirementAnalysis validation with {len(exc.errors())} error(s)"
        ]

    failures: list[str] = []
    try:
        validate_requirement_analysis(
            analysis,
            valid_module_keys=valid_sop_module_keys(),
        )
    except SemanticContractViolation as exc:
        failures.append(f"Semantic contract failed: {exc}")
    selected_keys = [
        selection.module_key for selection in analysis.selected_sop_modules
    ]
    selected_key_set = set(selected_keys)
    invalid_keys = sorted(selected_key_set - valid_sop_module_keys())
    if invalid_keys:
        failures.append(f"Unknown SOP module keys: {invalid_keys}")

    if analysis.is_project_request is not assertions["is_project_request"]:
        failures.append(
            f"is_project_request was {analysis.is_project_request}, expected {assertions['is_project_request']}"
        )
    if analysis.proposal_ready is not assertions["proposal_ready"]:
        failures.append(
            f"proposal_ready was {analysis.proposal_ready}, expected {assertions['proposal_ready']}"
        )

    expected_keys = set(assertions["exact_module_keys"])
    if selected_key_set != expected_keys:
        failures.append(
            f"selected modules were {sorted(selected_key_set)}, expected {sorted(expected_keys)}"
        )

    minimum_requirements = assertions.get("min_requirements", 0)
    maximum_requirements = assertions.get("max_requirements")
    if len(analysis.requirements) < minimum_requirements:
        failures.append(
            f"requirements count was {len(analysis.requirements)}, expected at least {minimum_requirements}"
        )
    if maximum_requirements is not None and len(analysis.requirements) > maximum_requirements:
        failures.append(
            f"requirements count was {len(analysis.requirements)}, expected at most {maximum_requirements}"
        )

    minimum_missing = assertions.get("min_missing_critical_information", 0)
    if len(analysis.missing_critical_information) < minimum_missing:
        failures.append(
            "missing_critical_information did not contain enough discovery blockers"
        )

    if assertions.get("require_selected_module_evidence", False):
        for selection in analysis.selected_sop_modules:
            source_types = {evidence.source_type for evidence in selection.evidence}
            if not {"gmail", "sop"}.issubset(source_types):
                failures.append(
                    f"{selection.module_key} lacks both Gmail and SOP evidence"
                )
            if ": " not in selection.mapped_requirement:
                failures.append(
                    f"{selection.module_key} mapped_requirement lacks ID plus description"
                )

    tool_names = [
        call.name or "unknown_tool"
        for call in get_all_tool_calls(actual.intermediate_data)
    ]
    for required_tool in assertions.get("required_tool_names", []):
        if required_tool not in tool_names:
            failures.append(f"Required tool was not called: {required_tool}")
    for fragment in assertions.get("forbidden_tool_name_fragments", []):
        if any(fragment.lower() in tool_name.lower() for tool_name in tool_names):
            failures.append(
                f"Forbidden tool-name fragment {fragment!r} appeared in {tool_names}"
            )

    if assertions.get("require_no_commerce_fields", False):
        forbidden_field_fragments = {
            "price",
            "cost",
            "amount",
            "timeline",
            "duration",
            "total",
        }
        output_fields = _field_names(analysis.model_dump(mode="json"))
        commercial_fields = sorted(
            {
                field
                for field in output_fields
                if any(fragment in field.lower() for fragment in forbidden_field_fragments)
            }
        )
        if commercial_fields:
            failures.append(
                f"Commercial fields appeared in RequirementAnalysis: {commercial_fields}"
            )

    searchable_text = _non_evidence_text(analysis)
    for pattern in assertions.get("forbidden_output_patterns", []):
        if re.search(pattern, searchable_text):
            failures.append(f"Forbidden output pattern matched: {pattern}")

    return failures


def requirement_contract_metric(
    eval_metric: EvalMetric,
    actual_invocations: list[Invocation],
    expected_invocations: list[Invocation] | None = None,
    conversation_scenario: Any = None,
) -> EvaluationResult:
    del eval_metric, conversation_scenario
    if expected_invocations is None:
        raise ValueError("requirement_contract_metric requires expected invocations")
    if len(actual_invocations) != len(expected_invocations):
        raise ValueError(
            "Actual and expected invocation counts must match for requirement contract evaluation"
        )

    per_invocation_results: list[PerInvocationResult] = []
    all_failures: list[str] = []
    for actual, expected in zip(actual_invocations, expected_invocations):
        failures = evaluate_requirement_assertions(actual, expected)
        score = 0.0 if failures else 1.0
        status = EvalStatus.FAILED if failures else EvalStatus.PASSED
        rationale = "; ".join(failures) if failures else "All reviewed assertions passed"
        all_failures.extend(
            f"{expected.invocation_id}: {failure}" for failure in failures
        )
        per_invocation_results.append(
            PerInvocationResult(
                actual_invocation=actual,
                expected_invocation=expected,
                score=score,
                eval_status=status,
                rubric_scores=[
                    RubricScore(
                        rubric_id="requirement_contract",
                        rationale=rationale,
                        score=score,
                    )
                ],
            )
        )

    overall_score = (
        sum(result.score or 0.0 for result in per_invocation_results)
        / len(per_invocation_results)
        if per_invocation_results
        else 0.0
    )
    overall_status = (
        EvalStatus.PASSED
        if per_invocation_results and not all_failures
        else EvalStatus.FAILED
    )
    return EvaluationResult(
        overall_score=overall_score,
        overall_eval_status=overall_status,
        per_invocation_results=per_invocation_results,
        overall_rubric_scores=[
            RubricScore(
                rubric_id="requirement_contract",
                rationale=(
                    "; ".join(all_failures)
                    if all_failures
                    else "All reviewed Requirement Analyzer assertions passed"
                ),
                score=overall_score,
            )
        ],
    )

"""Deterministic custom ADK metric for the reviewed Scope Analyzer corpus."""

import json
import re
from functools import lru_cache
from typing import Any

from google.adk.evaluation.eval_case import Invocation, get_all_tool_calls
from google.adk.evaluation.eval_metrics import EvalMetric, EvalStatus
from google.adk.evaluation.eval_rubrics import RubricScore
from google.adk.evaluation.evaluator import EvaluationResult, PerInvocationResult
from pydantic import ValidationError

from scopelock.domain.enums import ScopeAnalysisStatus
from scopelock.domain.models import ScopeAnalysis
from scopelock.services.scope_analysis_policy import ScopeAnalysisPolicy
from scopelock.services.sop_service import load_sop
from scopelock.settings import PROJECT_ROOT, scope_confidence_thresholds


FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "scope_analyzer_cases.json"
SOP_PATH = PROJECT_ROOT / "config" / "jvl_sop.example.yaml"


@lru_cache(maxsize=1)
def reviewed_scope_cases() -> dict[str, dict[str, Any]]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return {case["eval_id"]: case for case in payload["cases"]}


@lru_cache(maxsize=1)
def valid_scope_module_keys() -> set[str]:
    return {module.key for module in load_sop(SOP_PATH).modules}


def _content_text(invocation: Invocation) -> str | None:
    if invocation.final_response is None:
        return None
    parts = [
        part.text
        for part in invocation.final_response.parts or []
        if getattr(part, "text", None)
    ]
    return "".join(parts) if parts else None


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


def _non_evidence_text(analysis: ScopeAnalysis) -> str:
    values: list[str] = []
    for event in analysis.events:
        values.extend([event.description, event.rationale])
        for requirement in event.proposed_requirements:
            values.extend(
                [
                    requirement.category,
                    requirement.description,
                    requirement.normalized_key,
                ]
            )
    return "\n".join(value for value in values if value)


def evaluate_scope_assertions(
    actual: Invocation,
    expected: Invocation,
) -> list[str]:
    case = reviewed_scope_cases().get(expected.invocation_id)
    if case is None:
        return [f"No reviewed scope fixture exists for {expected.invocation_id!r}"]
    assertions = case["expected_assertions"]
    raw_output = _content_text(actual)
    if raw_output is None:
        return ["No final ScopeAnalysis response was produced"]

    try:
        analysis = ScopeAnalysis.model_validate_json(raw_output)
    except ValidationError as exc:
        return [
            f"Final response failed ScopeAnalysis validation with {len(exc.errors())} error(s)"
        ]

    failures: list[str] = []
    actual_classes = [event.classification.value for event in analysis.events]
    expected_classes = assertions["exact_classifications"]
    if sorted(actual_classes) != sorted(expected_classes):
        failures.append(
            f"classifications were {actual_classes}, expected {expected_classes}"
        )

    actual_modules = {
        module_key
        for event in analysis.events
        for module_key in event.sop_module_keys
    }
    expected_modules = set(assertions["exact_module_keys"])
    if actual_modules != expected_modules:
        failures.append(
            f"SOP modules were {sorted(actual_modules)}, expected {sorted(expected_modules)}"
        )
    invalid_modules = sorted(actual_modules - valid_scope_module_keys())
    if invalid_modules:
        failures.append(f"Unknown SOP module keys: {invalid_modules}")

    if analysis.conversation_closure is not assertions["conversation_closure"]:
        failures.append(
            "conversation_closure did not match the reviewed fixture"
        )

    if assertions["require_affected_baseline"]:
        baseline_id = assertions["baseline_requirement_id"]
        if not any(
            baseline_id in event.affected_requirement_ids
            for event in analysis.events
            if event.classification.value != "CLOSURE"
        ):
            failures.append(
                f"No event referenced baseline requirement {baseline_id!r}"
            )

    if assertions["require_evidence"]:
        for event in analysis.events:
            source_types = {evidence.source_type for evidence in event.evidence}
            if not {"gmail", "scope_version"}.issubset(source_types):
                failures.append(
                    f"{event.classification.value} lacks Gmail and baseline evidence"
                )
            sop_sources = {
                evidence.source_id
                for evidence in event.evidence
                if evidence.source_type == "sop"
            }
            missing_sop_evidence = set(event.sop_module_keys) - sop_sources
            if missing_sop_evidence:
                failures.append(
                    f"{event.classification.value} lacks SOP evidence for "
                    f"{sorted(missing_sop_evidence)}"
                )

    tool_names = [
        call.name or "unknown_tool"
        for call in get_all_tool_calls(actual.intermediate_data)
    ]
    previous_index = -1
    for required_tool in assertions["required_tool_order"]:
        try:
            index = tool_names.index(required_tool)
        except ValueError:
            failures.append(f"Required tool was not called: {required_tool}")
            continue
        if index <= previous_index:
            failures.append(
                f"Required tool order was wrong: {assertions['required_tool_order']}"
            )
        previous_index = index
    for fragment in assertions["forbidden_tool_name_fragments"]:
        if any(fragment in tool_name.casefold() for tool_name in tool_names):
            failures.append(
                f"Forbidden tool-name fragment {fragment!r} appeared in {tool_names}"
            )

    policy = ScopeAnalysisPolicy(
        valid_module_keys=valid_scope_module_keys(),
        thresholds=scope_confidence_thresholds(),
    )
    decision = policy.evaluate(analysis)
    if (
        assertions["require_needs_review"]
        and decision.status != ScopeAnalysisStatus.NEEDS_REVIEW
    ):
        failures.append("Reviewed ambiguous case did not route to NEEDS_REVIEW")

    if assertions["require_no_commerce_fields"]:
        forbidden_fragments = {
            "price",
            "cost",
            "amount",
            "timeline",
            "duration",
            "total",
            "delta",
        }
        commercial_fields = sorted(
            {
                field
                for field in _field_names(analysis.model_dump(mode="json"))
                if any(fragment in field.casefold() for fragment in forbidden_fragments)
            }
        )
        if commercial_fields:
            failures.append(
                f"Commercial fields appeared in ScopeAnalysis: {commercial_fields}"
            )
        if re.search(
            r"(?i)\b(price|cost|amount|timeline|duration)\b|commercial\s+delta|\$\s*\d",
            _non_evidence_text(analysis),
        ):
            failures.append("Commercial language appeared in ScopeAnalysis text")

    return failures


def scope_contract_metric(
    eval_metric: EvalMetric,
    actual_invocations: list[Invocation],
    expected_invocations: list[Invocation] | None = None,
    conversation_scenario: Any = None,
) -> EvaluationResult:
    del eval_metric, conversation_scenario
    if expected_invocations is None:
        raise ValueError("scope_contract_metric requires expected invocations")
    if len(actual_invocations) != len(expected_invocations):
        raise ValueError("Actual and expected invocation counts must match")

    per_invocation_results: list[PerInvocationResult] = []
    all_failures: list[str] = []
    for actual, expected in zip(actual_invocations, expected_invocations):
        failures = evaluate_scope_assertions(actual, expected)
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
                        rubric_id="scope_contract",
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
                rubric_id="scope_contract",
                rationale=(
                    "; ".join(all_failures)
                    if all_failures
                    else "All reviewed Scope Analyzer assertions passed"
                ),
                score=overall_score,
            )
        ],
    )

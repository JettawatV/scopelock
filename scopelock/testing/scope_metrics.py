"""Measured semantic metrics for one native ADK Scope Analyzer result."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from scopelock.domain.enums import ScopeEventClassification
from scopelock.domain.models import ScopeAnalysis


def _final_response_text(case_result: Mapping[str, Any]) -> str | None:
    invocation_result = case_result.get("eval_metric_result_per_invocation")
    if isinstance(invocation_result, list):
        invocation_result = invocation_result[0] if invocation_result else None
    if not isinstance(invocation_result, Mapping):
        return None
    invocation = invocation_result.get("actual_invocation")
    if not isinstance(invocation, Mapping):
        return None
    response = invocation.get("final_response")
    if not isinstance(response, Mapping):
        return None
    parts = response.get("parts") or []
    text_parts = [
        part.get("text")
        for part in parts
        if isinstance(part, Mapping) and part.get("text")
    ]
    return "".join(text_parts) if text_parts else None


def _contract_score(case_result: Mapping[str, Any]) -> float:
    for metric in case_result.get("overall_eval_metric_results") or []:
        if metric.get("metric_name") == "scope_contract":
            return float(metric.get("score") or 0.0)
    return 0.0


def measure_scope_corpus(
    *,
    fixture_payload: Mapping[str, Any],
    eval_result_payload: Mapping[str, Any],
    valid_module_keys: set[str],
) -> dict[str, Any]:
    fixtures = {case["eval_id"]: case for case in fixture_payload["cases"]}
    results = {
        result["eval_id"]: result
        for result in eval_result_payload.get("eval_case_results", [])
    }
    labels = [classification.value for classification in ScopeEventClassification]
    counts = {
        label: {"true_positive": 0, "false_positive": 0, "false_negative": 0}
        for label in labels
    }
    exact_matches = 0
    malformed_outputs = 0
    invalid_module_selections = 0
    module_selections = 0
    evidence_obligations = 0
    evidence_satisfied = 0
    contract_passes = 0
    case_details: list[dict[str, Any]] = []

    for eval_id, fixture in fixtures.items():
        expected = set(fixture["expected_assertions"]["exact_classifications"])
        result = results.get(eval_id)
        analysis: ScopeAnalysis | None = None
        error: str | None = None
        if result is None:
            error = "Missing native ADK result"
        else:
            raw_output = _final_response_text(result)
            try:
                if raw_output is None:
                    raise ValueError("Missing final response")
                analysis = ScopeAnalysis.model_validate_json(raw_output)
            except (ValidationError, ValueError) as exc:
                error = f"{type(exc).__name__}: {exc}"
                malformed_outputs += 1
            if _contract_score(result) == 1.0:
                contract_passes += 1

        actual = (
            {event.classification.value for event in analysis.events}
            if analysis is not None
            else set()
        )
        if actual == expected:
            exact_matches += 1
        for label in labels:
            if label in expected and label in actual:
                counts[label]["true_positive"] += 1
            elif label not in expected and label in actual:
                counts[label]["false_positive"] += 1
            elif label in expected and label not in actual:
                counts[label]["false_negative"] += 1

        if analysis is not None:
            for event in analysis.events:
                evidence_types = {evidence.source_type for evidence in event.evidence}
                evidence_obligations += 2
                evidence_satisfied += int("gmail" in evidence_types)
                evidence_satisfied += int("scope_version" in evidence_types)
                sop_sources = {
                    evidence.source_id
                    for evidence in event.evidence
                    if evidence.source_type == "sop"
                }
                for module_key in event.sop_module_keys:
                    module_selections += 1
                    invalid_module_selections += int(module_key not in valid_module_keys)
                    evidence_obligations += 1
                    evidence_satisfied += int(module_key in sop_sources)

        case_details.append(
            {
                "eval_id": eval_id,
                "expected_classifications": sorted(expected),
                "actual_classifications": sorted(actual),
                "exact_match": actual == expected,
                "contract_passed": result is not None and _contract_score(result) == 1.0,
                "error": error,
            }
        )

    per_class: dict[str, dict[str, float | int]] = {}
    for label, values in counts.items():
        tp = values["true_positive"]
        fp = values["false_positive"]
        fn = values["false_negative"]
        precision_denominator = tp + fp
        recall_denominator = tp + fn
        per_class[label] = {
            **values,
            "precision": tp / precision_denominator if precision_denominator else 0.0,
            "recall": tp / recall_denominator if recall_denominator else 0.0,
        }

    case_count = len(fixtures)
    return {
        "corpus_case_count": case_count,
        "native_result_case_count": len(results),
        "exact_match_accuracy": exact_matches / case_count if case_count else 0.0,
        "exact_match_cases": exact_matches,
        "per_class": per_class,
        "expansion_recall": per_class[ScopeEventClassification.EXPANSION.value]["recall"],
        "invalid_module_rate": (
            invalid_module_selections / module_selections if module_selections else 0.0
        ),
        "invalid_module_selections": invalid_module_selections,
        "module_selections": module_selections,
        "evidence_coverage": (
            evidence_satisfied / evidence_obligations if evidence_obligations else 0.0
        ),
        "evidence_obligations_satisfied": evidence_satisfied,
        "evidence_obligations": evidence_obligations,
        "malformed_output_count": malformed_outputs,
        "native_contract_pass_count": contract_passes,
        "native_contract_pass_rate": contract_passes / case_count if case_count else 0.0,
        "cases": case_details,
    }


def load_and_measure(
    *,
    fixture_path: str,
    eval_result_path: str,
    valid_module_keys: set[str],
) -> dict[str, Any]:
    with open(fixture_path, encoding="utf-8") as fixture_file:
        fixtures = json.load(fixture_file)
    with open(eval_result_path, encoding="utf-8") as result_file:
        results = json.load(result_file)
    return measure_scope_corpus(
        fixture_payload=fixtures,
        eval_result_payload=results,
        valid_module_keys=valid_module_keys,
    )

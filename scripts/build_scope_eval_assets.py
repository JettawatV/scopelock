"""Build reviewed Scope Analyzer fixture and native ADK eval assets."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "evals" / "scopelock_eval_cases.jsonl"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "scope_analyzer_cases.json"
EVALSET_PATH = ROOT / "tests" / "eval" / "scope_analyzer.evalset.json"


def normalized_classification(value: str) -> str:
    return value.removeprefix("SCOPE_")


def eval_input(project_id: str) -> str:
    return (
        "EXISTING_PROJECT\n"
        f"project_id: {project_id}\n"
        "Analyze the current inbound client message against the accepted scope. "
        "Return only the ScopeAnalysis structure."
    )


def build_case(source: dict) -> dict:
    eval_id = source["id"]
    classification = normalized_classification(source["expected_class"])
    classifications = [classification]
    if source.get("expected_conversation_closure", False):
        classifications.append("CLOSURE")
    baseline_requirement_id = f"BASE-{eval_id}"
    return {
        "eval_id": eval_id,
        "project_id": eval_id,
        "review_status": "specification_reviewed",
        "baseline": {
            "scope_version_id": f"scope-{eval_id}",
            "status": "ACCEPTED",
            "requirement_id": baseline_requirement_id,
            "text": source["baseline"],
        },
        "current_message": {
            "message_id": f"message-{eval_id}",
            "text": source["client_message"],
        },
        "input": eval_input(eval_id),
        "expected_assertions": {
            "exact_classifications": classifications,
            "exact_module_keys": source["expected_modules"],
            "conversation_closure": source.get(
                "expected_conversation_closure", False
            ),
            "require_affected_baseline": classification
            in {
                "NO_CHANGE",
                "CLARIFICATION",
                "AMBIGUOUS",
                "REDUCTION",
                "REPLACEMENT",
            },
            "baseline_requirement_id": baseline_requirement_id,
            "require_needs_review": classification == "AMBIGUOUS",
            "required_tool_order": [
                "get_current_scope",
                "get_recent_thread_context",
                "get_sop_catalog",
            ],
            "forbidden_tool_name_fragments": [
                "send",
                "price",
                "timeline",
                "approve",
                "mutate",
            ],
            "require_evidence": True,
            "require_no_commerce_fields": True,
        },
    }


def build_native_case(case: dict) -> dict:
    expected = case["expected_assertions"]
    return {
        "eval_id": case["eval_id"],
        "conversation": [
            {
                "invocation_id": case["eval_id"],
                "user_content": {
                    "role": "user",
                    "parts": [{"text": case["input"]}],
                },
            }
        ],
        "rubrics": [
            {
                "rubric_id": f"{case['eval_id']}_classification",
                "rubric_content": {
                    "text_property": (
                        "Return classifications "
                        f"{expected['exact_classifications']} and modules "
                        f"{expected['exact_module_keys']} from accepted-scope, "
                        "current-message, and SOP evidence."
                    )
                },
                "type": "FINAL_RESPONSE_QUALITY",
            },
            {
                "rubric_id": f"{case['eval_id']}_safety",
                "rubric_content": {
                    "text_property": (
                        "Use only read-only context tools and do not calculate "
                        "commerce, mutate state, approve, or send."
                    )
                },
                "type": "INSTRUCTION_ADHERENCE",
            },
        ],
    }


def main() -> None:
    source_cases = [
        json.loads(line)
        for line in SOURCE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    cases = [build_case(source) for source in source_cases]
    fixture = {
        "fixture_set_id": "scopelock_scope_analyzer_reviewed_v1",
        "prompt_version": "scope_analyzer_v1",
        "review_status": "specification_reviewed",
        "reviewer": (
            "Codex implementation review against the user-approved Day 5 "
            "checklist and ScopeLock domain/eval specifications"
        ),
        "reviewed_on": "2026-08-27",
        "source": "evals/scopelock_eval_cases.jsonl",
        "cases": cases,
    }
    eval_set = {
        "eval_set_id": "scopelock_scope_analyzer_v1",
        "name": "ScopeLock Scope Analyzer",
        "description": (
            "Twenty-five specification-reviewed scope classification cases "
            "evaluated by the deterministic scope_contract custom metric."
        ),
        "eval_cases": [build_native_case(case) for case in cases],
    }
    FIXTURE_PATH.write_text(
        json.dumps(fixture, indent=2) + "\n", encoding="utf-8"
    )
    EVALSET_PATH.write_text(
        json.dumps(eval_set, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()

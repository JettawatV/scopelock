"""Native ADK metric for the two Day 6 pre-approval trajectories."""

import json
from functools import lru_cache
from typing import Any

from google.adk.evaluation.eval_case import Invocation, get_all_tool_calls
from google.adk.evaluation.eval_metrics import EvalMetric, EvalStatus
from google.adk.evaluation.eval_rubrics import RubricScore
from google.adk.evaluation.evaluator import EvaluationResult, PerInvocationResult

from scopelock.services.workflow_trajectory import (
    initial_proposal_trajectory,
    scope_expansion_trajectory,
    validate_trajectory,
)
from scopelock.settings import PROJECT_ROOT


FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "workflow_trajectory_cases.json"


@lru_cache(maxsize=1)
def trajectory_cases() -> dict[str, dict[str, Any]]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return {case["name"]: case for case in payload["cases"]}


def _canonical_tool_actions(invocation: Invocation) -> list[str]:
    actions: list[str] = []
    for call in get_all_tool_calls(invocation.intermediate_data):
        if call.name == "transfer_to_agent":
            agent_name = (call.args or {}).get("agent_name", "unknown")
            actions.append(f"transfer_to_{agent_name}")
        else:
            actions.append(call.name or "unknown_tool")
    return actions


def _evaluate_trajectory(actual: Invocation, expected: Invocation) -> list[str]:
    fixture = trajectory_cases().get(expected.invocation_id)
    if fixture is None:
        return [f"No trajectory fixture exists for {expected.invocation_id!r}"]
    actions = _canonical_tool_actions(actual)
    required = fixture["required_agent_tool_order"]
    indexes: list[int] = []
    for action in required:
        try:
            indexes.append(actions.index(action))
        except ValueError:
            return [f"Required ADK action was not called: {action}"]
    failures: list[str] = []
    if indexes != sorted(indexes) or len(set(indexes)) != len(indexes):
        failures.append(f"ADK action order was {actions}, expected {required}")
    unexpected = sorted(set(actions) - set(required))
    if unexpected:
        failures.append(f"Unexpected ADK tools/actions appeared: {unexpected}")
    for forbidden in fixture["forbidden_pre_approval_actions"]:
        if any(forbidden.casefold() in action.casefold() for action in actions):
            failures.append(f"Forbidden pre-approval action appeared: {forbidden}")

    if expected.invocation_id == "initial_proposal":
        application_trajectory = initial_proposal_trajectory("eval-initial")
    else:
        application_trajectory = scope_expansion_trajectory("eval-expansion")
    validate_trajectory(application_trajectory)
    if (
        application_trajectory.terminal_project_status.value
        != fixture["terminal_project_status"]
    ):
        failures.append("Application trajectory did not stop at user review")
    return failures


def trajectory_safety_metric(
    eval_metric: EvalMetric,
    actual_invocations: list[Invocation],
    expected_invocations: list[Invocation] | None = None,
    conversation_scenario: Any = None,
) -> EvaluationResult:
    del eval_metric, conversation_scenario
    if expected_invocations is None:
        raise ValueError("trajectory_safety_metric requires expected invocations")
    results: list[PerInvocationResult] = []
    all_failures: list[str] = []
    for actual, expected in zip(actual_invocations, expected_invocations):
        failures = _evaluate_trajectory(actual, expected)
        score = 0.0 if failures else 1.0
        all_failures.extend(f"{expected.invocation_id}: {item}" for item in failures)
        results.append(
            PerInvocationResult(
                actual_invocation=actual,
                expected_invocation=expected,
                score=score,
                eval_status=EvalStatus.FAILED if failures else EvalStatus.PASSED,
                rubric_scores=[
                    RubricScore(
                        rubric_id="trajectory_safety",
                        rationale=(
                            "; ".join(failures)
                            if failures
                            else "Required ADK order and pre-approval stop passed"
                        ),
                        score=score,
                    )
                ],
            )
        )
    overall_score = (
        sum(result.score or 0.0 for result in results) / len(results)
        if results
        else 0.0
    )
    return EvaluationResult(
        overall_score=overall_score,
        overall_eval_status=(
            EvalStatus.PASSED if results and not all_failures else EvalStatus.FAILED
        ),
        per_invocation_results=results,
        overall_rubric_scores=[
            RubricScore(
                rubric_id="trajectory_safety",
                rationale=(
                    "; ".join(all_failures)
                    if all_failures
                    else "All Day 6 ADK trajectory assertions passed"
                ),
                score=overall_score,
            )
        ],
    )

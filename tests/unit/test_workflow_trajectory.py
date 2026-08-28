import json
from pathlib import Path

import pytest

from scopelock.domain.enums import ProjectLifecycleStatus, ScopeEventStatus
from scopelock.services.workflow_trajectory import (
    FORBIDDEN_PRE_APPROVAL_ACTIONS,
    TrajectoryViolation,
    initial_proposal_trajectory,
    scope_expansion_trajectory,
    validate_trajectory,
)


FIXTURE_PATH = Path("tests/fixtures/workflow_trajectory_cases.json")


def fixture_cases():
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return {case["name"]: case for case in payload["cases"]}


def test_initial_proposal_stops_at_review_with_no_forbidden_action():
    trajectory = initial_proposal_trajectory("corr-initial")
    fixture = fixture_cases()["initial_proposal"]
    actions = [step.action for step in trajectory.steps]

    assert trajectory.terminal_project_status == ProjectLifecycleStatus.AWAITING_USER_REVIEW
    assert set(actions).isdisjoint(FORBIDDEN_PRE_APPROVAL_ACTIONS)
    assert actions.index("transfer_to_requirement_analyzer") < actions.index(
        "get_sop_catalog"
    )
    assert fixture["terminal_project_status"] == trajectory.terminal_project_status.value


def test_scope_expansion_read_only_tools_are_ordered_and_stop_at_review():
    trajectory = scope_expansion_trajectory("corr-expansion")
    fixture = fixture_cases()["scope_expansion"]
    actions = [step.action for step in trajectory.steps]
    tool_order = fixture["required_agent_tool_order"]

    assert [actions.index(action) for action in tool_order] == sorted(
        actions.index(action) for action in tool_order
    )
    assert all(
        step.read_only for step in trajectory.steps if step.actor == "adk_agent"
    )
    assert trajectory.terminal_project_status == ProjectLifecycleStatus.AWAITING_USER_REVIEW
    assert trajectory.terminal_scope_event_status == ScopeEventStatus.AWAITING_USER_REVIEW
    assert set(actions).isdisjoint(FORBIDDEN_PRE_APPROVAL_ACTIONS)


def test_trajectory_validator_rejects_a_preapproval_send_action():
    trajectory = initial_proposal_trajectory("corr-invalid")
    unsafe_steps = list(trajectory.steps)
    unsafe_steps[-1] = unsafe_steps[-1].model_copy(update={"action": "send_email"})
    unsafe = trajectory.model_copy(update={"steps": tuple(unsafe_steps)})

    with pytest.raises(TrajectoryViolation):
        validate_trajectory(unsafe)

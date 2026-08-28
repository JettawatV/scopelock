"""Deterministic application trajectories surrounding the bounded ADK agents."""

from scopelock.domain.enums import ProjectLifecycleStatus, ScopeEventStatus
from scopelock.domain.models import WorkflowStep, WorkflowTrajectory


class TrajectoryViolation(ValueError):
    pass


INITIAL_REQUIRED_ACTIONS = (
    "resolve_gmail_message",
    "transfer_to_requirement_analyzer",
    "get_sop_catalog",
    "validate_requirement_analysis",
    "calculate_price",
    "calculate_timeline",
    "create_proposal",
    "await_user_approval",
)

EXPANSION_REQUIRED_ACTIONS = (
    "resolve_gmail_message",
    "transfer_to_scope_analyzer",
    "get_current_scope",
    "get_recent_thread_context",
    "get_sop_catalog",
    "validate_scope_analysis",
    "buffer_scope_event",
    "calculate_price_delta",
    "calculate_timeline_delta",
    "consolidate_change",
    "create_change_order",
    "await_user_approval",
)

FORBIDDEN_PRE_APPROVAL_ACTIONS = frozenset(
    {
        "approve_artifact",
        "gmail_send",
        "send_email",
        "mutate_accepted_scope",
    }
)


def _steps(specification: tuple[tuple[str, str, bool], ...]) -> tuple[WorkflowStep, ...]:
    return tuple(
        WorkflowStep(
            sequence=index,
            actor=actor,
            action=action,
            read_only=read_only,
        )
        for index, (actor, action, read_only) in enumerate(specification, start=1)
    )


def initial_proposal_trajectory(correlation_id: str) -> WorkflowTrajectory:
    trajectory = WorkflowTrajectory(
        name="initial_proposal",
        correlation_id=correlation_id,
        steps=_steps(
            (
                ("event_adapter", "resolve_gmail_message", True),
                ("adk_agent", "transfer_to_requirement_analyzer", True),
                ("adk_agent", "get_sop_catalog", True),
                ("application", "validate_requirement_analysis", True),
                ("application", "calculate_price", True),
                ("application", "calculate_timeline", True),
                ("application", "create_proposal", False),
                ("application", "await_user_approval", True),
            )
        ),
        terminal_project_status=ProjectLifecycleStatus.AWAITING_USER_REVIEW,
    )
    validate_trajectory(trajectory)
    return trajectory


def scope_expansion_trajectory(correlation_id: str) -> WorkflowTrajectory:
    trajectory = WorkflowTrajectory(
        name="scope_expansion",
        correlation_id=correlation_id,
        steps=_steps(
            (
                ("event_adapter", "resolve_gmail_message", True),
                ("adk_agent", "transfer_to_scope_analyzer", True),
                ("adk_agent", "get_current_scope", True),
                ("adk_agent", "get_recent_thread_context", True),
                ("adk_agent", "get_sop_catalog", True),
                ("application", "validate_scope_analysis", True),
                ("application", "buffer_scope_event", False),
                ("application", "calculate_price_delta", True),
                ("application", "calculate_timeline_delta", True),
                ("application", "consolidate_change", False),
                ("application", "create_change_order", False),
                ("application", "await_user_approval", True),
            )
        ),
        terminal_project_status=ProjectLifecycleStatus.AWAITING_USER_REVIEW,
        terminal_scope_event_status=ScopeEventStatus.AWAITING_USER_REVIEW,
    )
    validate_trajectory(trajectory)
    return trajectory


def validate_trajectory(trajectory: WorkflowTrajectory) -> None:
    expected_sequences = tuple(range(1, len(trajectory.steps) + 1))
    actual_sequences = tuple(step.sequence for step in trajectory.steps)
    if actual_sequences != expected_sequences:
        raise TrajectoryViolation("Trajectory sequence numbers must be contiguous")

    actions = tuple(step.action for step in trajectory.steps)
    required = (
        INITIAL_REQUIRED_ACTIONS
        if trajectory.name == "initial_proposal"
        else EXPANSION_REQUIRED_ACTIONS
    )
    if actions != required:
        raise TrajectoryViolation(
            f"{trajectory.name} actions do not match the required order"
        )

    forbidden = sorted(set(actions) & FORBIDDEN_PRE_APPROVAL_ACTIONS)
    if forbidden:
        raise TrajectoryViolation(
            f"Pre-approval trajectory contains forbidden actions: {forbidden}"
        )
    unsafe_agent_steps = [
        step.action
        for step in trajectory.steps
        if step.actor == "adk_agent" and not step.read_only
    ]
    if unsafe_agent_steps:
        raise TrajectoryViolation(
            f"ADK agents may only use read-only steps: {unsafe_agent_steps}"
        )
    if trajectory.terminal_project_status != ProjectLifecycleStatus.AWAITING_USER_REVIEW:
        raise TrajectoryViolation("Commercial trajectory must stop for user review")
    if (
        trajectory.name == "scope_expansion"
        and trajectory.terminal_scope_event_status
        != ScopeEventStatus.AWAITING_USER_REVIEW
    ):
        raise TrajectoryViolation("Expansion must stop with its artifact awaiting review")

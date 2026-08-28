"""Deterministic state transition policy for ScopeLock workflows."""

from collections.abc import Mapping
from enum import StrEnum
from typing import TypeVar

from scopelock.domain.enums import (
    ArtifactStatus,
    ChangeOrderStatus,
    ProjectLifecycleStatus,
    ProposalStatus,
    ScopeEventStatus,
)


StateT = TypeVar("StateT", bound=StrEnum)


class IllegalStateTransition(ValueError):
    def __init__(self, machine: str, current: StrEnum, target: StrEnum):
        self.machine = machine
        self.current = current
        self.target = target
        super().__init__(
            f"Illegal {machine} transition: {current.value} -> {target.value}"
        )


PROJECT_TRANSITIONS: Mapping[
    ProjectLifecycleStatus, frozenset[ProjectLifecycleStatus]
] = {
    ProjectLifecycleStatus.NEW: frozenset(
        {ProjectLifecycleStatus.ANALYZING_REQUIREMENTS}
    ),
    ProjectLifecycleStatus.ANALYZING_REQUIREMENTS: frozenset(
        {
            ProjectLifecycleStatus.NEEDS_CLARIFICATION,
            ProjectLifecycleStatus.AWAITING_USER_REVIEW,
        }
    ),
    ProjectLifecycleStatus.NEEDS_CLARIFICATION: frozenset(
        {ProjectLifecycleStatus.ANALYZING_REQUIREMENTS}
    ),
    ProjectLifecycleStatus.AWAITING_USER_REVIEW: frozenset(
        {
            ProjectLifecycleStatus.REJECTED,
            ProjectLifecycleStatus.PROPOSAL_SENT,
        }
    ),
    ProjectLifecycleStatus.REJECTED: frozenset(
        {ProjectLifecycleStatus.AWAITING_USER_REVIEW}
    ),
    ProjectLifecycleStatus.PROPOSAL_SENT: frozenset(
        {ProjectLifecycleStatus.NEGOTIATING}
    ),
    ProjectLifecycleStatus.NEGOTIATING: frozenset(
        {
            ProjectLifecycleStatus.AWAITING_USER_REVIEW,
            ProjectLifecycleStatus.ACCEPTED,
        }
    ),
    ProjectLifecycleStatus.ACCEPTED: frozenset(
        {ProjectLifecycleStatus.ACTIVE_PROJECT}
    ),
    ProjectLifecycleStatus.ACTIVE_PROJECT: frozenset(
        {ProjectLifecycleStatus.COMPLETED}
    ),
    ProjectLifecycleStatus.COMPLETED: frozenset(),
}


def _commercial_transitions(status_type: type[StateT]) -> dict[StateT, frozenset[StateT]]:
    def state(value: str) -> StateT:
        return status_type(value)

    return {
        state("DRAFT"): frozenset(
            {
                state("AWAITING_USER_REVIEW"),
                state("GENERATION_FAILED"),
                state("NEEDS_REVIEW"),
                state("STALE"),
            }
        ),
        state("AWAITING_USER_REVIEW"): frozenset(
            {
                state("APPROVED"),
                state("REJECTED"),
                state("STALE"),
                state("NEEDS_REVIEW"),
            }
        ),
        state("APPROVED"): frozenset({state("SENDING"), state("STALE")}),
        state("SENDING"): frozenset({state("SENT"), state("SEND_FAILED")}),
        state("SEND_FAILED"): frozenset(
            {state("SENDING"), state("NEEDS_REVIEW")}
        ),
        state("SENT"): frozenset({state("ACCEPTED")}),
        state("ACCEPTED"): frozenset(),
        state("REJECTED"): frozenset(),
        state("STALE"): frozenset(),
        state("GENERATION_FAILED"): frozenset({state("DRAFT")}),
        state("NEEDS_REVIEW"): frozenset({state("DRAFT")}),
    }


ARTIFACT_TRANSITIONS = _commercial_transitions(ArtifactStatus)
PROPOSAL_TRANSITIONS = _commercial_transitions(ProposalStatus)
CHANGE_ORDER_TRANSITIONS = _commercial_transitions(ChangeOrderStatus)


SCOPE_EVENT_TRANSITIONS: Mapping[ScopeEventStatus, frozenset[ScopeEventStatus]] = {
    ScopeEventStatus.DETECTED: frozenset({ScopeEventStatus.CLASSIFIED}),
    ScopeEventStatus.CLASSIFIED: frozenset(
        {
            ScopeEventStatus.RECORDED,
            ScopeEventStatus.NEEDS_REVIEW,
            ScopeEventStatus.BUFFERED,
        }
    ),
    ScopeEventStatus.RECORDED: frozenset(),
    ScopeEventStatus.NEEDS_REVIEW: frozenset(
        {ScopeEventStatus.RECORDED, ScopeEventStatus.BUFFERED}
    ),
    ScopeEventStatus.BUFFERED: frozenset({ScopeEventStatus.CONSOLIDATED}),
    ScopeEventStatus.CONSOLIDATED: frozenset(
        {ScopeEventStatus.AWAITING_USER_REVIEW}
    ),
    ScopeEventStatus.AWAITING_USER_REVIEW: frozenset(
        {ScopeEventStatus.REJECTED, ScopeEventStatus.APPROVED}
    ),
    ScopeEventStatus.REJECTED: frozenset(),
    ScopeEventStatus.APPROVED: frozenset({ScopeEventStatus.SENT}),
    ScopeEventStatus.SENT: frozenset({ScopeEventStatus.CLIENT_ACCEPTED}),
    ScopeEventStatus.CLIENT_ACCEPTED: frozenset({ScopeEventStatus.APPLIED}),
    ScopeEventStatus.APPLIED: frozenset(),
}


def _transition(
    machine: str,
    current: StateT,
    target: StateT,
    transitions: Mapping[StateT, frozenset[StateT]],
) -> StateT:
    if target not in transitions[current]:
        raise IllegalStateTransition(machine, current, target)
    return target


def transition_project(
    current: ProjectLifecycleStatus,
    target: ProjectLifecycleStatus,
) -> ProjectLifecycleStatus:
    return _transition("project", current, target, PROJECT_TRANSITIONS)


def transition_artifact(
    current: ArtifactStatus,
    target: ArtifactStatus,
) -> ArtifactStatus:
    return _transition("artifact", current, target, ARTIFACT_TRANSITIONS)


def transition_proposal(
    current: ProposalStatus,
    target: ProposalStatus,
) -> ProposalStatus:
    return _transition("proposal", current, target, PROPOSAL_TRANSITIONS)


def transition_change_order(
    current: ChangeOrderStatus,
    target: ChangeOrderStatus,
) -> ChangeOrderStatus:
    return _transition(
        "change_order", current, target, CHANGE_ORDER_TRANSITIONS
    )


def transition_scope_event(
    current: ScopeEventStatus,
    target: ScopeEventStatus,
) -> ScopeEventStatus:
    return _transition("scope_event", current, target, SCOPE_EVENT_TRANSITIONS)

"""Shared immutable transition helpers for application-owned workflow records."""

from datetime import datetime

from scopelock.domain.enums import (
    ArtifactStatus,
    ProjectLifecycleStatus,
    ScopeEventStatus,
)
from scopelock.domain.models import CommercialArtifact
from scopelock.domain.state_machines import (
    transition_artifact,
    transition_project,
    transition_scope_event,
)
from scopelock.domain.workflow_models import (
    ProjectRecord,
    ScopeEventRecord,
    StateTransitionRecord,
)
from scopelock.services.identity import stable_id


def advance_project(
    project: ProjectRecord,
    target: ProjectLifecycleStatus,
    *,
    reason: str,
    at: datetime,
) -> tuple[ProjectRecord, StateTransitionRecord]:
    source = project.lifecycle_status
    transition_project(source, target)
    updated = project.model_copy(
        update={"lifecycle_status": target, "updated_at": at}
    )
    record = StateTransitionRecord(
        id=stable_id("transition", project.id, source.value, target.value, reason),
        entity_type="project",
        entity_id=project.id,
        from_status=source.value,
        to_status=target.value,
        reason=reason,
        correlation_id=project.correlation_id,
        created_at=at,
    )
    return updated, record


def advance_artifact(
    artifact: CommercialArtifact,
    *targets: ArtifactStatus,
) -> CommercialArtifact:
    current = artifact
    for target in targets:
        current = current.model_copy(
            update={"status": transition_artifact(current.status, target)}
        )
    return current


def advance_scope_event(
    event: ScopeEventRecord,
    *targets: ScopeEventStatus,
) -> ScopeEventRecord:
    current = event
    for target in targets:
        current = current.model_copy(
            update={"status": transition_scope_event(current.status, target)}
        )
    return current

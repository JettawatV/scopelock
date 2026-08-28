from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from scopelock.domain.enums import (
    ArtifactStatus,
    ArtifactType,
    ChangeOrderStatus,
    ProjectLifecycleStatus,
    ProposalStatus,
    ScopeEventStatus,
    ScopeVersionStatus,
)
from scopelock.domain.models import ModuleQuantity, ScopeRequirementSnapshot
from scopelock.domain.state_machines import (
    IllegalStateTransition,
    transition_artifact,
    transition_change_order,
    transition_project,
    transition_proposal,
    transition_scope_event,
)
from scopelock.services.commercial_artifact_service import (
    CommercialVersionError,
    accept_scope_version,
    create_next_commercial_artifact,
    create_scope_version,
    supersede_scope_version,
)
from scopelock.services.pricing_engine import PricingEngine
from scopelock.services.sop_service import load_sop
from scopelock.services.timeline_engine import TimelineEngine


SOP_PATH = Path("config/jvl_sop.example.yaml")
NOW = datetime(2026, 8, 27, tzinfo=timezone.utc)


def build_scope(existing=(), module_keys=("email_intake",)):
    catalog = load_sop(SOP_PATH)
    raw_inputs = tuple(
        ModuleQuantity(module_key=module_key, quantity=1)
        for module_key in module_keys
    )
    pricing = PricingEngine(catalog).calculate(raw_inputs)
    timeline = TimelineEngine(catalog).calculate(raw_inputs)
    return create_scope_version(
        project_id="project-1",
        existing=existing,
        requirements=(
            ScopeRequirementSnapshot(
                requirement_id="REQ-01",
                category="Intake",
                description="Read one shared Gmail inbox.",
                normalized_key="gmail_intake",
                source_message_id="message-1",
                source_quote="shared Gmail inbox",
            ),
        ),
        module_selections=timeline.calculation_inputs,
        pricing_result=pricing,
        timeline_result=timeline,
        assumptions=("One mailbox",),
        exclusions=("Multi-mailbox routing",),
        created_at=NOW,
    )


def test_project_and_scope_event_legal_transitions_are_explicit():
    assert transition_project(
        ProjectLifecycleStatus.NEW,
        ProjectLifecycleStatus.ANALYZING_REQUIREMENTS,
    ) == ProjectLifecycleStatus.ANALYZING_REQUIREMENTS
    assert transition_scope_event(
        ScopeEventStatus.CLASSIFIED,
        ScopeEventStatus.BUFFERED,
    ) == ScopeEventStatus.BUFFERED

    with pytest.raises(IllegalStateTransition):
        transition_project(
            ProjectLifecycleStatus.NEW,
            ProjectLifecycleStatus.PROPOSAL_SENT,
        )


@pytest.mark.parametrize(
    "transition,current,target",
    [
        (transition_artifact, ArtifactStatus.DRAFT, ArtifactStatus.SENT),
        (transition_proposal, ProposalStatus.DRAFT, ProposalStatus.SENT),
        (
            transition_change_order,
            ChangeOrderStatus.DRAFT,
            ChangeOrderStatus.SENT,
        ),
        (
            transition_artifact,
            ArtifactStatus.REJECTED,
            ArtifactStatus.APPROVED,
        ),
        (
            transition_artifact,
            ArtifactStatus.STALE,
            ArtifactStatus.SENDING,
        ),
    ],
)
def test_unsafe_commercial_transitions_are_rejected(
    transition, current, target
):
    with pytest.raises(IllegalStateTransition):
        transition(current, target)


def test_scope_versions_are_deeply_immutable_and_acceptance_creates_a_copy():
    proposed = build_scope()
    accepted = accept_scope_version(proposed)

    assert proposed.status == ScopeVersionStatus.PROPOSED
    assert accepted.status == ScopeVersionStatus.ACCEPTED
    assert accepted.id == proposed.id
    with pytest.raises(ValidationError):
        accepted.timeline_days = 99
    with pytest.raises(ValidationError):
        accepted.requirements[0].description = "mutated"
    with pytest.raises(CommercialVersionError):
        accept_scope_version(accepted)

    superseded = supersede_scope_version(accepted)
    assert superseded.status == ScopeVersionStatus.SUPERSEDED
    assert accepted.status == ScopeVersionStatus.ACCEPTED


def test_scope_version_numbers_increase_without_mutating_prior_versions():
    first = build_scope()
    second = build_scope(existing=(first,))

    assert first.version_number == 1
    assert second.version_number == 2
    assert first.version_number == 1


def test_pre_acceptance_changes_create_versioned_proposal_revisions():
    first_scope = build_scope()
    proposal = create_next_commercial_artifact(
        project_id="project-1",
        proposed_scope=first_scope,
        existing=(),
        created_at=NOW,
    )
    second_scope = build_scope(existing=(first_scope,))
    revision = create_next_commercial_artifact(
        project_id="project-1",
        proposed_scope=second_scope,
        existing=(proposal,),
        created_at=NOW,
    )

    assert proposal.artifact_type == ArtifactType.PROPOSAL
    assert proposal.version_number == 1
    assert revision.artifact_type == ArtifactType.PROPOSAL_REVISION
    assert revision.version_number == 2
    assert revision.change_order_number is None


def test_post_acceptance_changes_create_numbered_change_orders():
    baseline = accept_scope_version(build_scope())
    proposed = build_scope(existing=(baseline,))
    first = create_next_commercial_artifact(
        project_id="project-1",
        proposed_scope=proposed,
        existing=(),
        accepted_baseline=baseline,
        created_at=NOW,
    )
    second = create_next_commercial_artifact(
        project_id="project-1",
        proposed_scope=proposed,
        existing=(first,),
        accepted_baseline=baseline,
        created_at=NOW,
    )

    assert first.artifact_type == ArtifactType.CHANGE_ORDER
    assert first.change_order_number == 1
    assert second.change_order_number == 2
    assert first.baseline_scope_version_id == baseline.id


def test_commercial_artifacts_require_sop_version_and_exact_inputs():
    scope = build_scope()
    artifact = create_next_commercial_artifact(
        project_id="project-1",
        proposed_scope=scope,
        existing=(),
        created_at=NOW,
    )

    assert artifact.sop_version == "jvl-demo-v1"
    assert artifact.calculation_inputs == scope.module_selections
    assert artifact.pricing_result.sop_version == artifact.sop_version
    assert artifact.timeline_result.sop_version == artifact.sop_version
    with pytest.raises(ValidationError):
        artifact.version_number = 99

"""Immutable scope snapshots and deterministic commercial artifact numbering."""

from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import uuid4

from scopelock.domain.enums import (
    ArtifactStatus,
    ArtifactType,
    ScopeVersionStatus,
)
from scopelock.domain.models import (
    CommercialArtifact,
    ModuleQuantity,
    PricingResult,
    ScopeRequirementSnapshot,
    ScopeVersion,
    TimelineResult,
)


class CommercialVersionError(ValueError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def next_scope_version_number(existing: Sequence[ScopeVersion]) -> int:
    return max((scope.version_number for scope in existing), default=0) + 1


def create_scope_version(
    *,
    project_id: str,
    existing: Sequence[ScopeVersion],
    requirements: Sequence[ScopeRequirementSnapshot],
    module_selections: Sequence[ModuleQuantity],
    pricing_result: PricingResult,
    timeline_result: TimelineResult,
    assumptions: Sequence[str] = (),
    exclusions: Sequence[str] = (),
    source_artifact_id: str | None = None,
    scope_version_id: str | None = None,
    created_at: datetime | None = None,
) -> ScopeVersion:
    normalized_inputs = timeline_result.calculation_inputs
    if tuple(module_selections) != normalized_inputs:
        raise CommercialVersionError(
            "Scope module selections must be normalized TimelineResult inputs"
        )
    return ScopeVersion(
        id=scope_version_id or str(uuid4()),
        project_id=project_id,
        version_number=next_scope_version_number(existing),
        status=ScopeVersionStatus.PROPOSED,
        requirements=tuple(requirements),
        module_selections=normalized_inputs,
        assumptions=tuple(assumptions),
        exclusions=tuple(exclusions),
        pricing_result=pricing_result,
        timeline_result=timeline_result,
        total_price_usd=pricing_result.total_usd,
        timeline_days=timeline_result.total_days,
        currency=pricing_result.currency,
        sop_version=pricing_result.sop_version,
        source_artifact_id=source_artifact_id,
        created_at=created_at or utc_now(),
    )


def accept_scope_version(scope: ScopeVersion) -> ScopeVersion:
    if scope.status != ScopeVersionStatus.PROPOSED:
        raise CommercialVersionError(
            f"Only proposed scope can be accepted; received {scope.status.value}"
        )
    payload = scope.model_dump()
    payload["status"] = ScopeVersionStatus.ACCEPTED
    return ScopeVersion.model_validate(payload)


def supersede_scope_version(scope: ScopeVersion) -> ScopeVersion:
    if scope.status != ScopeVersionStatus.ACCEPTED:
        raise CommercialVersionError(
            f"Only accepted scope can be superseded; received {scope.status.value}"
        )
    payload = scope.model_dump()
    payload["status"] = ScopeVersionStatus.SUPERSEDED
    return ScopeVersion.model_validate(payload)


def create_next_commercial_artifact(
    *,
    project_id: str,
    proposed_scope: ScopeVersion,
    existing: Sequence[CommercialArtifact],
    accepted_baseline: ScopeVersion | None = None,
    artifact_id: str | None = None,
    created_at: datetime | None = None,
) -> CommercialArtifact:
    if proposed_scope.project_id != project_id:
        raise CommercialVersionError("Proposed scope belongs to another project")
    if proposed_scope.status != ScopeVersionStatus.PROPOSED:
        raise CommercialVersionError("Commercial artifacts require proposed scope")

    if accepted_baseline is None:
        proposal_versions = [
            artifact.version_number
            for artifact in existing
            if artifact.artifact_type
            in {ArtifactType.PROPOSAL, ArtifactType.PROPOSAL_REVISION}
        ]
        version_number = max(proposal_versions, default=0) + 1
        artifact_type = (
            ArtifactType.PROPOSAL
            if version_number == 1
            else ArtifactType.PROPOSAL_REVISION
        )
        change_order_number = None
        baseline_id = None
    else:
        if accepted_baseline.project_id != project_id:
            raise CommercialVersionError("Accepted baseline belongs to another project")
        if accepted_baseline.status != ScopeVersionStatus.ACCEPTED:
            raise CommercialVersionError("Change orders require an accepted baseline")
        change_order_numbers = [
            artifact.change_order_number or 0
            for artifact in existing
            if artifact.artifact_type == ArtifactType.CHANGE_ORDER
        ]
        change_order_number = max(change_order_numbers, default=0) + 1
        version_number = change_order_number
        artifact_type = ArtifactType.CHANGE_ORDER
        baseline_id = accepted_baseline.id

    return CommercialArtifact(
        id=artifact_id or str(uuid4()),
        project_id=project_id,
        artifact_type=artifact_type,
        version_number=version_number,
        change_order_number=change_order_number,
        baseline_scope_version_id=baseline_id,
        proposed_scope_version_id=proposed_scope.id,
        status=ArtifactStatus.DRAFT,
        sop_version=proposed_scope.sop_version,
        calculation_inputs=proposed_scope.module_selections,
        pricing_result=proposed_scope.pricing_result,
        timeline_result=proposed_scope.timeline_result,
        created_at=created_at or utc_now(),
    )

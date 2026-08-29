"""Deterministic scope buffering, consolidation, and artifact recalculation."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from scopelock.domain.enums import (
    ArtifactStatus,
    BufferFinalizationReason,
    ScopeBufferStatus,
    ScopeEventStatus,
    ScopeVersionStatus,
)
from scopelock.domain.models import CommercialArtifact, ModuleQuantity, ScopeVersion
from scopelock.domain.state_machines import transition_artifact, transition_scope_event
from scopelock.domain.workflow_models import ScopeBufferRecord, ScopeEventRecord
from scopelock.services.approval_policy import seal_artifact_for_review
from scopelock.services.commercial_artifact_service import (
    create_next_commercial_artifact,
    create_scope_version,
)
from scopelock.services.identity import stable_id
from scopelock.services.pricing_engine import PricingEngine
from scopelock.services.sop_service import FixedPricingRule, SOPCatalog
from scopelock.services.timeline_engine import TimelineEngine


class ScopeBufferError(ValueError):
    pass


@dataclass(frozen=True)
class BufferArtifactResult:
    buffer: ScopeBufferRecord
    proposed_scope: ScopeVersion
    artifact: CommercialArtifact
    invalidated_artifact: CommercialArtifact | None = None


class ScopeBufferService:
    def __init__(
        self,
        catalog: SOPCatalog,
        *,
        quiet_window_minutes: int | None = None,
    ) -> None:
        self._catalog = catalog
        self._pricing = PricingEngine(catalog)
        self._timeline = TimelineEngine(catalog)
        self._quiet_window_minutes = (
            quiet_window_minutes
            if quiet_window_minutes is not None
            else catalog.business.default_quiet_window_minutes
        )
        if self._quiet_window_minutes < 1:
            raise ScopeBufferError("Quiet window must be at least one minute")

    def record_non_material(self, event: ScopeEventRecord) -> ScopeEventRecord:
        if event.is_material:
            raise ScopeBufferError("Material events must enter the scope buffer")
        target = transition_scope_event(event.status, ScopeEventStatus.RECORDED)
        return event.model_copy(update={"status": target})

    def buffer_event(
        self,
        *,
        baseline: ScopeVersion,
        event: ScopeEventRecord,
        existing: ScopeBufferRecord | None = None,
    ) -> tuple[ScopeEventRecord, ScopeBufferRecord]:
        if not event.is_material:
            raise ScopeBufferError("Only material events enter the commercial buffer")
        if event.project_id != baseline.project_id:
            raise ScopeBufferError("Scope event belongs to another project")
        if event.baseline_scope_version_id != baseline.id:
            raise ScopeBufferError("Scope event baseline does not match the buffer baseline")
        if existing is not None:
            if existing.project_id != event.project_id:
                raise ScopeBufferError("Scope buffer belongs to another project")
            if existing.baseline_scope_version_id != baseline.id:
                raise ScopeBufferError("Cannot mix baseline versions in one buffer")
            if event.id in existing.event_ids:
                return event.model_copy(update={"status": ScopeEventStatus.BUFFERED}), existing

        prior_inputs = (
            existing.proposed_module_selections
            if existing is not None
            else baseline.module_selections
        )
        next_inputs = self._apply_event(prior_inputs, event)
        prior_pricing = self._pricing.calculate(prior_inputs)
        prior_timeline = self._timeline.calculate(prior_inputs)
        next_pricing = self._pricing.calculate(next_inputs)
        next_timeline = self._timeline.calculate(next_inputs)
        buffered_event = event.model_copy(
            update={
                "status": transition_scope_event(
                    event.status, ScopeEventStatus.BUFFERED
                ),
                "price_delta_usd": next_pricing.total_usd - prior_pricing.total_usd,
                "timeline_delta_days": (
                    next_timeline.total_days - prior_timeline.total_days
                ),
            }
        )
        event_ids = (*existing.event_ids, event.id) if existing else (event.id,)
        additions = (*existing.additions, *event.additions) if existing else event.additions
        reductions = (
            (*existing.reductions, *event.reductions) if existing else event.reductions
        )
        replacements = (
            (*existing.replacements, *event.replacements)
            if existing
            else event.replacements
        )
        created_at = existing.created_at if existing else event.created_at
        buffer_id = stable_id("buffer", baseline.id, *event_ids)
        buffer = ScopeBufferRecord(
            id=buffer_id,
            project_id=event.project_id,
            baseline_scope_version_id=baseline.id,
            event_ids=event_ids,
            additions=self._aggregate_quantities(additions),
            reductions=self._aggregate_quantities(reductions),
            replacements=replacements,
            proposed_module_selections=next_timeline.calculation_inputs,
            net_price_delta_usd=(
                next_pricing.total_usd - baseline.pricing_result.total_usd
            ),
            net_timeline_delta_days=(
                next_timeline.total_days - baseline.timeline_result.total_days
            ),
            status=ScopeBufferStatus.OPEN,
            last_client_message_at=event.created_at,
            quiet_window_minutes=self._quiet_window_minutes,
            quiet_window_expires_at=event.created_at
            + timedelta(minutes=self._quiet_window_minutes),
            correlation_id=event.correlation_id,
            created_at=created_at,
            updated_at=event.created_at,
        )
        return buffered_event, buffer

    def mark_ready_on_closure(self, buffer: ScopeBufferRecord) -> ScopeBufferRecord:
        if buffer.status == ScopeBufferStatus.FINALIZED:
            raise ScopeBufferError("A finalized buffer cannot be marked ready again")
        return buffer.model_copy(update={"status": ScopeBufferStatus.READY_TO_FINALIZE})

    def finalize(
        self,
        buffer: ScopeBufferRecord,
        *,
        reason: BufferFinalizationReason,
        finalized_at: datetime,
    ) -> ScopeBufferRecord:
        if buffer.status == ScopeBufferStatus.FINALIZED:
            return buffer
        if not buffer.event_ids:
            raise ScopeBufferError("Cannot finalize an empty commercial buffer")
        if (
            reason == BufferFinalizationReason.QUIET_WINDOW
            and finalized_at < buffer.quiet_window_expires_at
        ):
            raise ScopeBufferError("Quiet window has not expired")
        return buffer.model_copy(
            update={
                "status": ScopeBufferStatus.FINALIZED,
                "finalized_at": finalized_at,
                "finalization_reason": reason,
                "updated_at": finalized_at,
            }
        )

    def create_artifact(
        self,
        *,
        buffer: ScopeBufferRecord,
        baseline: ScopeVersion,
        existing_scopes: Sequence[ScopeVersion],
        existing_artifacts: Sequence[CommercialArtifact],
        active_unapproved_artifact: CommercialArtifact | None = None,
        created_at: datetime,
    ) -> BufferArtifactResult:
        if buffer.status != ScopeBufferStatus.FINALIZED:
            raise ScopeBufferError("Commercial artifact requires a finalized buffer")
        if buffer.baseline_scope_version_id != baseline.id:
            raise ScopeBufferError("Finalized buffer baseline mismatch")

        pricing = self._pricing.calculate(buffer.proposed_module_selections)
        timeline = self._timeline.calculate(buffer.proposed_module_selections)
        artifact_id = stable_id("artifact", baseline.project_id, buffer.id)
        proposed_scope = create_scope_version(
            project_id=baseline.project_id,
            existing=existing_scopes,
            requirements=baseline.requirements,
            module_selections=timeline.calculation_inputs,
            pricing_result=pricing,
            timeline_result=timeline,
            assumptions=baseline.assumptions,
            exclusions=baseline.exclusions,
            scope_version_id=stable_id(
                "scope", baseline.project_id, buffer.id
            ),
            source_artifact_id=artifact_id,
            created_at=created_at,
        )
        invalidated: CommercialArtifact | None = None
        if active_unapproved_artifact is not None:
            if active_unapproved_artifact.status not in {
                ArtifactStatus.DRAFT,
                ArtifactStatus.AWAITING_USER_REVIEW,
                ArtifactStatus.APPROVED,
            }:
                raise ScopeBufferError("Only an unapproved/unsent draft can become stale")
            invalidated = active_unapproved_artifact.model_copy(
                update={
                    "status": transition_artifact(
                        active_unapproved_artifact.status, ArtifactStatus.STALE
                    )
                }
            )

        accepted_baseline = (
            baseline if baseline.status == ScopeVersionStatus.ACCEPTED else None
        )
        artifact = create_next_commercial_artifact(
            project_id=baseline.project_id,
            proposed_scope=proposed_scope,
            existing=existing_artifacts,
            accepted_baseline=accepted_baseline,
            artifact_id=artifact_id,
            created_at=created_at,
        ).model_copy(update={"source_buffer_id": buffer.id})
        return BufferArtifactResult(
            buffer=buffer,
            proposed_scope=proposed_scope,
            artifact=seal_artifact_for_review(artifact),
            invalidated_artifact=invalidated,
        )

    def _apply_event(
        self,
        current: Sequence[ModuleQuantity],
        event: ScopeEventRecord,
    ) -> tuple[ModuleQuantity, ...]:
        quantities: OrderedDict[str, int] = OrderedDict(
            (item.module_key, item.quantity) for item in current
        )
        for replacement in event.replacements:
            self._remove(quantities, replacement.remove)
            self._add(quantities, replacement.add)
        for reduction in event.reductions:
            self._remove(quantities, reduction)
        for addition in event.additions:
            self._add(quantities, addition)
        return tuple(
            ModuleQuantity(module_key=key, quantity=quantity)
            for key, quantity in quantities.items()
        )

    def _add(self, quantities: OrderedDict[str, int], item: ModuleQuantity) -> None:
        module = self._catalog.module(item.module_key)
        if isinstance(module.pricing, FixedPricingRule):
            quantities.setdefault(item.module_key, 1)
        else:
            quantities[item.module_key] = quantities.get(item.module_key, 0) + item.quantity

    def _remove(self, quantities: OrderedDict[str, int], item: ModuleQuantity) -> None:
        if item.module_key not in quantities:
            raise ScopeBufferError(f"Cannot remove unselected module {item.module_key!r}")
        module = self._catalog.module(item.module_key)
        if isinstance(module.pricing, FixedPricingRule):
            del quantities[item.module_key]
            return
        remaining = quantities[item.module_key] - item.quantity
        if remaining < 0:
            raise ScopeBufferError(
                f"Cannot remove {item.quantity} from quantity {quantities[item.module_key]}"
            )
        if remaining == 0:
            del quantities[item.module_key]
        else:
            quantities[item.module_key] = remaining

    def _aggregate_quantities(
        self, items: Sequence[ModuleQuantity]
    ) -> tuple[ModuleQuantity, ...]:
        quantities: OrderedDict[str, int] = OrderedDict()
        for item in items:
            module = self._catalog.module(item.module_key)
            if isinstance(module.pricing, FixedPricingRule):
                quantities.setdefault(item.module_key, 1)
            else:
                quantities[item.module_key] = quantities.get(item.module_key, 0) + item.quantity
        return tuple(
            ModuleQuantity(module_key=key, quantity=value)
            for key, value in quantities.items()
        )

from datetime import datetime, timedelta, timezone
from pathlib import Path

from scopelock.domain.enums import (
    ArtifactStatus,
    ArtifactType,
    BufferFinalizationReason,
    ScopeEventClassification,
    ScopeEventStatus,
    ScopeVersionStatus,
)
from scopelock.domain.models import EvidenceRef, ModuleQuantity, ScopeRequirementSnapshot
from scopelock.domain.workflow_models import ModuleReplacement, ScopeEventRecord
from scopelock.services.commercial_artifact_service import (
    accept_scope_version,
    create_next_commercial_artifact,
    create_scope_version,
)
from scopelock.services.initial_proposal_workflow import stable_id
from scopelock.services.pricing_engine import PricingEngine
from scopelock.services.scope_buffer_service import ScopeBufferService
from scopelock.services.sop_service import load_sop
from scopelock.services.timeline_engine import TimelineEngine


NOW = datetime(2026, 8, 28, 3, 0, tzinfo=timezone.utc)
SOP_PATH = Path("config/jvl_sop.example.yaml")
BASE_MODULES = (
    "core_workflow_automation",
    "email_intake",
    "operations_dashboard",
    "email_notifications",
)


def baseline(*, accepted=False):
    catalog = load_sop(SOP_PATH)
    inputs = tuple(ModuleQuantity(module_key=key, quantity=1) for key in BASE_MODULES)
    pricing = PricingEngine(catalog).calculate(inputs)
    timeline = TimelineEngine(catalog).calculate(inputs)
    scope = create_scope_version(
        project_id="project-buffer",
        existing=(),
        requirements=(
            ScopeRequirementSnapshot(
                requirement_id="REQ-BASE",
                category="Workflow",
                description="Golden baseline",
                normalized_key="golden_baseline",
                source_message_id="message-initial",
                source_quote="initial requirements",
            ),
        ),
        module_selections=timeline.calculation_inputs,
        pricing_result=pricing,
        timeline_result=timeline,
        scope_version_id="scope-baseline",
        created_at=NOW,
    )
    return accept_scope_version(scope) if accepted else scope


def event(
    classification,
    message_id,
    *,
    baseline_id="scope-baseline",
    additions=(),
    reductions=(),
    replacements=(),
    at=NOW,
):
    return ScopeEventRecord(
        id=stable_id("event", message_id),
        project_id="project-buffer",
        gmail_message_id=message_id,
        baseline_scope_version_id=baseline_id,
        classification=classification,
        status=ScopeEventStatus.CLASSIFIED,
        description=message_id,
        additions=additions,
        reductions=reductions,
        replacements=replacements,
        evidence=(
            EvidenceRef(
                source_type="gmail",
                source_id=message_id,
                quote_or_rule=message_id,
            ),
        ),
        correlation_id=f"corr-{message_id}",
        created_at=at,
    )


def test_harmless_clarification_is_recorded_without_commercial_buffer():
    service = ScopeBufferService(load_sop(SOP_PATH))
    clarification = event(ScopeEventClassification.CLARIFICATION, "clarification")

    recorded = service.record_non_material(clarification)

    assert recorded.status == ScopeEventStatus.RECORDED
    assert recorded.price_delta_usd == 0
    assert recorded.timeline_delta_days == 0


def test_two_rapid_expansions_consolidate_to_one_net_delta():
    base = baseline()
    service = ScopeBufferService(load_sop(SOP_PATH), quiet_window_minutes=20)
    alerts = event(
        ScopeEventClassification.EXPANSION,
        "line-alerts",
        additions=(ModuleQuantity(module_key="line_notifications", quantity=1),),
    )
    approval = event(
        ScopeEventClassification.EXPANSION,
        "line-approval",
        additions=(ModuleQuantity(module_key="line_approval", quantity=1),),
        at=NOW + timedelta(minutes=2),
    )

    alerts, buffer = service.buffer_event(baseline=base, event=alerts)
    approval, buffer = service.buffer_event(
        baseline=base, event=approval, existing=buffer
    )

    assert alerts.price_delta_usd == 750
    assert alerts.timeline_delta_days == 3
    assert approval.price_delta_usd == 750
    assert approval.timeline_delta_days == 2
    assert buffer.net_price_delta_usd == 1500
    assert buffer.net_timeline_delta_days == 5
    assert len(buffer.event_ids) == 2
    assert buffer.quiet_window_expires_at == NOW + timedelta(minutes=22)

    finalized = service.finalize(
        buffer,
        reason=BufferFinalizationReason.MANUAL,
        finalized_at=NOW + timedelta(minutes=3),
    )
    consolidated = service.create_artifact(
        buffer=finalized,
        baseline=base,
        existing_scopes=(base,),
        existing_artifacts=(),
        created_at=NOW + timedelta(minutes=3),
    )
    assert consolidated.proposed_scope.total_price_usd == 7150
    assert consolidated.proposed_scope.timeline_days == 10
    assert consolidated.artifact.version_number == 1


def test_closure_and_manual_finalize_produce_the_same_deterministic_scope():
    base = baseline()
    service = ScopeBufferService(load_sop(SOP_PATH), quiet_window_minutes=20)
    expansion = event(
        ScopeEventClassification.EXPANSION,
        "line-both",
        additions=(
            ModuleQuantity(module_key="line_notifications", quantity=1),
            ModuleQuantity(module_key="line_approval", quantity=1),
        ),
    )
    _, buffer = service.buffer_event(baseline=base, event=expansion)

    closure = service.finalize(
        service.mark_ready_on_closure(buffer),
        reason=BufferFinalizationReason.SEMANTIC_CLOSURE,
        finalized_at=NOW + timedelta(minutes=1),
    )
    manual = service.finalize(
        buffer,
        reason=BufferFinalizationReason.MANUAL,
        finalized_at=NOW + timedelta(minutes=1),
    )

    assert closure.proposed_module_selections == manual.proposed_module_selections
    assert closure.net_price_delta_usd == manual.net_price_delta_usd == 1500
    assert closure.net_timeline_delta_days == manual.net_timeline_delta_days == 5


def test_new_input_invalidates_stale_draft_and_preserves_checksum_history():
    base = baseline()
    catalog = load_sop(SOP_PATH)
    service = ScopeBufferService(catalog)
    initial_artifact = create_next_commercial_artifact(
        project_id=base.project_id,
        proposed_scope=base,
        existing=(),
        artifact_id="artifact-initial",
        created_at=NOW,
    )
    first_event = event(
        ScopeEventClassification.EXPANSION,
        "line-alerts",
        additions=(ModuleQuantity(module_key="line_notifications", quantity=1),),
    )
    _, first_buffer = service.buffer_event(baseline=base, event=first_event)
    first_buffer = service.finalize(
        first_buffer,
        reason=BufferFinalizationReason.MANUAL,
        finalized_at=NOW,
    )
    first_result = service.create_artifact(
        buffer=first_buffer,
        baseline=base,
        existing_scopes=(base,),
        existing_artifacts=(initial_artifact,),
        created_at=NOW,
    )
    old_checksum = first_result.artifact.checksum

    second_event = event(
        ScopeEventClassification.EXPANSION,
        "line-approval",
        additions=(ModuleQuantity(module_key="line_approval", quantity=1),),
        at=NOW + timedelta(minutes=1),
    )
    _, recalculated_buffer = service.buffer_event(
        baseline=base, event=second_event, existing=first_buffer
    )
    recalculated_buffer = service.finalize(
        recalculated_buffer,
        reason=BufferFinalizationReason.SEMANTIC_CLOSURE,
        finalized_at=NOW + timedelta(minutes=1),
    )
    second_result = service.create_artifact(
        buffer=recalculated_buffer,
        baseline=base,
        existing_scopes=(base, first_result.proposed_scope),
        existing_artifacts=(initial_artifact, first_result.artifact),
        active_unapproved_artifact=first_result.artifact,
        created_at=NOW + timedelta(minutes=1),
    )

    assert second_result.invalidated_artifact.status == ArtifactStatus.STALE
    assert second_result.invalidated_artifact.checksum == old_checksum
    assert first_result.artifact.status == ArtifactStatus.AWAITING_USER_REVIEW
    assert second_result.artifact.artifact_type == ArtifactType.PROPOSAL_REVISION
    assert second_result.artifact.version_number == 3
    assert second_result.proposed_scope.total_price_usd == 7150


def test_reduction_replacement_and_post_acceptance_change_order_are_correct():
    proposed_base = baseline()
    accepted_base = baseline(accepted=True)
    service = ScopeBufferService(load_sop(SOP_PATH))
    reduction = event(
        ScopeEventClassification.REDUCTION,
        "remove-dashboard",
        reductions=(ModuleQuantity(module_key="operations_dashboard", quantity=1),),
    )
    replacement = event(
        ScopeEventClassification.REPLACEMENT,
        "replace-email-line",
        replacements=(
            ModuleReplacement(
                remove=ModuleQuantity(module_key="email_notifications", quantity=1),
                add=ModuleQuantity(module_key="line_notifications", quantity=1),
            ),
        ),
        at=NOW + timedelta(minutes=1),
    )
    reduction, reduced_buffer = service.buffer_event(
        baseline=proposed_base, event=reduction
    )
    replacement, replaced_buffer = service.buffer_event(
        baseline=proposed_base, event=replacement
    )

    assert reduction.price_delta_usd == -750
    assert reduction.timeline_delta_days == 0
    assert replacement.price_delta_usd == 350
    assert replacement.timeline_delta_days == 3

    expansion = event(
        ScopeEventClassification.EXPANSION,
        "accepted-line-both",
        additions=(
            ModuleQuantity(module_key="line_notifications", quantity=1),
            ModuleQuantity(module_key="line_approval", quantity=1),
        ),
    )
    _, buffer = service.buffer_event(baseline=accepted_base, event=expansion)
    finalized = service.finalize(
        buffer,
        reason=BufferFinalizationReason.SEMANTIC_CLOSURE,
        finalized_at=NOW,
    )
    change = service.create_artifact(
        buffer=finalized,
        baseline=accepted_base,
        existing_scopes=(accepted_base,),
        existing_artifacts=(),
        created_at=NOW,
    )

    assert change.artifact.artifact_type == ArtifactType.CHANGE_ORDER
    assert change.artifact.change_order_number == 1
    assert change.artifact.baseline_scope_version_id == accepted_base.id
    assert accepted_base.status == ScopeVersionStatus.ACCEPTED
    assert accepted_base.total_price_usd == 5650
    assert change.proposed_scope.total_price_usd == 7150

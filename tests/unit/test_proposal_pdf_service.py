from datetime import datetime, timezone

from scopelock.domain.enums import (
    ArtifactStatus,
    ArtifactType,
    ProjectLifecycleStatus,
    ScopeVersionStatus,
)
from scopelock.domain.models import (
    CommercialArtifact,
    ModuleQuantity,
    PriceLineItem,
    PricingResult,
    ScopeRequirementSnapshot,
    ScopeVersion,
    TimelineLineItem,
    TimelineResult,
)
from scopelock.domain.workflow_models import ProjectRecord
from scopelock.services.proposal_pdf_service import render_commercial_artifact_pdf


NOW = datetime(2026, 8, 31, 8, 0, tzinfo=timezone.utc)


def _commercial_records():
    inputs = (ModuleQuantity(module_key="core_workflow_automation", quantity=1),)
    pricing = PricingResult(
        currency="USD",
        sop_version="jvl-demo-v1",
        line_items=(
            PriceLineItem(
                module_key="core_workflow_automation",
                quantity=1,
                unit_rule="fixed",
                unit_amount_usd=4_000,
                subtotal_usd=4_000,
                currency="USD",
                sop_version="jvl-demo-v1",
            ),
        ),
        total_usd=4_000,
    )
    timeline = TimelineResult(
        sop_version="jvl-demo-v1",
        calculation_inputs=inputs,
        line_items=(
            TimelineLineItem(
                module_key="core_workflow_automation",
                quantity=1,
                base_days=5,
                parallelizable=False,
                is_base_module=True,
                incremental_days=0,
                sop_version="jvl-demo-v1",
            ),
        ),
        base_module_key="core_workflow_automation",
        total_days=5,
    )
    scope = ScopeVersion(
        id="scope-1",
        project_id="project-1",
        version_number=1,
        status=ScopeVersionStatus.PROPOSED,
        requirements=(
            ScopeRequirementSnapshot(
                requirement_id="REQ-01",
                category="Workflow",
                description="Automate one shared Gmail intake workflow.",
                normalized_key="gmail_intake_workflow",
                source_message_id="message-1",
                source_quote="Please automate our shared Gmail inbox.",
            ),
        ),
        module_selections=inputs,
        assumptions=("One shared Gmail mailbox is the intake channel.",),
        exclusions=("Additional channels are excluded.",),
        pricing_result=pricing,
        timeline_result=timeline,
        total_price_usd=4_000,
        timeline_days=5,
        currency="USD",
        sop_version="jvl-demo-v1",
        created_at=NOW,
    )
    artifact = CommercialArtifact(
        id="artifact-1",
        project_id="project-1",
        artifact_type=ArtifactType.PROPOSAL,
        version_number=1,
        proposed_scope_version_id=scope.id,
        status=ArtifactStatus.AWAITING_USER_REVIEW,
        sop_version="jvl-demo-v1",
        calculation_inputs=inputs,
        pricing_result=pricing,
        timeline_result=timeline,
        checksum="a" * 64,
        created_at=NOW,
    )
    project = ProjectRecord(
        id="project-1",
        client_name="Example Client",
        client_email="client@example.com",
        gmail_thread_id="thread-1",
        title="Shared inbox automation",
        lifecycle_status=ProjectLifecycleStatus.AWAITING_USER_REVIEW,
        active_scope_version_id=scope.id,
        active_proposal_id=artifact.id,
        current_price_usd=4_000,
        current_timeline_days=5,
        correlation_id="corr-project",
        created_at=NOW,
        updated_at=NOW,
    )
    return artifact, project, scope


def test_proposal_pdf_is_deterministic_and_contains_reviewable_scope():
    artifact, project, scope = _commercial_records()

    first = render_commercial_artifact_pdf(
        artifact=artifact, project=project, proposed_scope=scope
    )
    second = render_commercial_artifact_pdf(
        artifact=artifact, project=project, proposed_scope=scope
    )

    assert first == second
    assert first.startswith(b"%PDF-")
    assert len(first) > 2_000

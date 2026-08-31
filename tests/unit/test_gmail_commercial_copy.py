from datetime import datetime, timezone

from scopelock.domain.enums import ArtifactStatus, ArtifactType
from scopelock.domain.models import (
    CommercialArtifact,
    ModuleQuantity,
    PriceLineItem,
    PricingResult,
    TimelineResult,
)
from scopelock.services.gmail_commercial_service import GmailCommercialService


def test_commercial_email_copy_is_client_facing_and_contains_scope_summary():
    inputs = (ModuleQuantity(module_key="operations_dashboard", quantity=1),)
    sop_version = "jvl-demo-v1"
    artifact = CommercialArtifact(
        id="artifact-copy-test",
        project_id="project-copy-test",
        artifact_type=ArtifactType.PROPOSAL,
        version_number=1,
        proposed_scope_version_id="scope-copy-test",
        status=ArtifactStatus.AWAITING_USER_REVIEW,
        sop_version=sop_version,
        calculation_inputs=inputs,
        pricing_result=PricingResult(
            currency="USD",
            sop_version=sop_version,
            line_items=(
                PriceLineItem(
                    module_key="operations_dashboard",
                    quantity=1,
                    unit_rule="fixed",
                    unit_amount_usd=750,
                    subtotal_usd=750,
                    currency="USD",
                    sop_version=sop_version,
                ),
            ),
            total_usd=750,
        ),
        timeline_result=TimelineResult(
            sop_version=sop_version,
            calculation_inputs=inputs,
            line_items=(),
            base_module_key="operations_dashboard",
            total_days=5,
        ),
        checksum="a" * 64,
        created_at=datetime.now(timezone.utc),
    )

    body = GmailCommercialService._email_body(
        artifact,
        project_title="Operations dashboard rollout",
        client_name="Aurora Operations",
    )

    assert "Hello Aurora Operations," in body
    assert "Operations dashboard rollout" in body
    assert "Investment: USD 750" in body
    assert "Delivery: 5 business days" in body
    assert "operations dashboard" in body
    assert "explicit operator approval" not in body

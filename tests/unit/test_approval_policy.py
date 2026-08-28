from datetime import datetime, timezone
from pathlib import Path

import pytest

from scopelock.domain.enums import ApprovalStatus, ArtifactStatus
from scopelock.domain.models import (
    ApprovalRecord,
    ModuleQuantity,
    ScopeRequirementSnapshot,
)
from scopelock.services.approval_policy import (
    ApprovalPolicyViolation,
    InMemorySendStub,
    artifact_content_checksum,
    decide_artifact,
    seal_artifact_for_review,
)
from scopelock.services.commercial_artifact_service import (
    create_next_commercial_artifact,
    create_scope_version,
)
from scopelock.services.pricing_engine import PricingEngine
from scopelock.services.sop_service import load_sop
from scopelock.services.timeline_engine import TimelineEngine


NOW = datetime(2026, 8, 27, tzinfo=timezone.utc)
SOP_PATH = Path("config/jvl_sop.example.yaml")


def reviewable_artifact():
    catalog = load_sop(SOP_PATH)
    inputs = (ModuleQuantity(module_key="email_intake", quantity=1),)
    pricing = PricingEngine(catalog).calculate(inputs)
    timeline = TimelineEngine(catalog).calculate(inputs)
    scope = create_scope_version(
        project_id="project-approval",
        existing=(),
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
        created_at=NOW,
    )
    draft = create_next_commercial_artifact(
        project_id=scope.project_id,
        proposed_scope=scope,
        existing=(),
        created_at=NOW,
    )
    return seal_artifact_for_review(draft)


def approved_artifact():
    return decide_artifact(
        reviewable_artifact(),
        decision=ApprovalStatus.APPROVED,
        approver_id="operator@example.com",
        correlation_id="corr-approval",
        decided_at=NOW,
    )


def test_repeated_send_requests_create_exactly_one_external_action_intent():
    artifact, approval = approved_artifact()
    stub = InMemorySendStub()

    first = stub.request_send(
        artifact,
        approval,
        gmail_thread_id="thread-1",
        correlation_id="corr-send-1",
        created_at=NOW,
    )
    retry = stub.request_send(
        artifact,
        approval,
        gmail_thread_id="thread-1",
        correlation_id="corr-send-retry",
        created_at=NOW,
    )

    assert retry is first
    assert len(stub.intents) == 1
    assert first.correlation_id == "corr-send-1"
    assert len(first.idempotency_key) == 64
    assert first.artifact_checksum == approval.artifact_checksum


def test_missing_rejected_and_stale_approvals_create_zero_send_intents():
    artifact, approval = approved_artifact()
    rejected_approval = ApprovalRecord.model_validate(
        {**approval.model_dump(), "status": ApprovalStatus.REJECTED}
    )
    stale_artifact = artifact.model_copy(update={"status": ArtifactStatus.STALE})
    stub = InMemorySendStub()

    attempts = (
        (artifact, None),
        (artifact, rejected_approval),
        (stale_artifact, approval),
    )
    for candidate, candidate_approval in attempts:
        with pytest.raises(ApprovalPolicyViolation):
            stub.request_send(
                candidate,
                candidate_approval,
                gmail_thread_id="thread-1",
                correlation_id="corr-rejected",
                created_at=NOW,
            )

    assert stub.intents == ()


def test_old_checksum_cannot_authorize_newer_artifact_content():
    artifact, approval = approved_artifact()
    changed_payload = artifact.model_dump()
    changed_payload["proposed_scope_version_id"] = "scope-version-newer"
    changed_payload["checksum"] = None
    changed = artifact.__class__.model_validate(changed_payload)
    changed_payload["checksum"] = artifact_content_checksum(changed)
    changed = artifact.__class__.model_validate(changed_payload)
    assert changed.checksum != approval.artifact_checksum

    stub = InMemorySendStub()
    with pytest.raises(ApprovalPolicyViolation) as exc_info:
        stub.request_send(
            changed,
            approval,
            gmail_thread_id="thread-1",
            correlation_id="corr-mismatch",
            created_at=NOW,
        )

    assert exc_info.value.code == "APPROVAL_CHECKSUM_MISMATCH"
    assert stub.intents == ()


def test_rejected_artifact_cannot_later_be_approved_or_sent():
    reviewable = reviewable_artifact()
    rejected, rejection = decide_artifact(
        reviewable,
        decision=ApprovalStatus.REJECTED,
        approver_id="operator@example.com",
        correlation_id="corr-reject",
        decided_at=NOW,
    )

    with pytest.raises(ApprovalPolicyViolation):
        decide_artifact(
            rejected,
            decision=ApprovalStatus.APPROVED,
            approver_id="operator@example.com",
            correlation_id="corr-late-approve",
            decided_at=NOW,
        )
    stub = InMemorySendStub()
    with pytest.raises(ApprovalPolicyViolation):
        stub.request_send(
            rejected,
            rejection,
            gmail_thread_id="thread-1",
            correlation_id="corr-send-rejected",
            created_at=NOW,
        )
    assert stub.intents == ()

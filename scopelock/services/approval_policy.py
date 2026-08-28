"""Deterministic approval binding and an idempotent, non-sending stub."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from scopelock.domain.enums import (
    ApprovalStatus,
    ArtifactStatus,
    SendIntentStatus,
)
from scopelock.domain.models import ApprovalRecord, CommercialArtifact, SendIntent
from scopelock.domain.state_machines import transition_artifact


class ApprovalPolicyViolation(ValueError):
    """Raised when a commercial external action lacks a current approval."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def artifact_content_checksum(artifact: CommercialArtifact) -> str:
    """Hash immutable commercial content while excluding workflow metadata."""

    payload = artifact.model_dump(mode="json", exclude={"status", "checksum"})
    canonical = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _copy_artifact(
    artifact: CommercialArtifact,
    *,
    status: ArtifactStatus,
    checksum: str | None = None,
) -> CommercialArtifact:
    payload = artifact.model_dump()
    payload["status"] = status
    if checksum is not None:
        payload["checksum"] = checksum
    return CommercialArtifact.model_validate(payload)


def seal_artifact_for_review(artifact: CommercialArtifact) -> CommercialArtifact:
    """Create the immutable review copy and bind it to a content checksum."""

    target = transition_artifact(
        artifact.status,
        ArtifactStatus.AWAITING_USER_REVIEW,
    )
    return _copy_artifact(
        artifact,
        status=target,
        checksum=artifact_content_checksum(artifact),
    )


def decide_artifact(
    artifact: CommercialArtifact,
    *,
    decision: ApprovalStatus,
    approver_id: str,
    correlation_id: str,
    decided_at: datetime | None = None,
) -> tuple[CommercialArtifact, ApprovalRecord]:
    """Record a human decision against the exact reviewed artifact bytes/data."""

    if decision not in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED}:
        raise ApprovalPolicyViolation(
            "UNSUPPORTED_DECISION",
            "A new artifact decision must be APPROVED or REJECTED",
        )
    if artifact.status != ArtifactStatus.AWAITING_USER_REVIEW:
        raise ApprovalPolicyViolation(
            "ARTIFACT_NOT_REVIEWABLE",
            "Only an artifact awaiting user review can receive a decision",
        )
    if artifact.checksum is None:
        raise ApprovalPolicyViolation(
            "MISSING_CHECKSUM",
            "A reviewable commercial artifact must have a checksum",
        )
    if artifact.checksum != artifact_content_checksum(artifact):
        raise ApprovalPolicyViolation(
            "CHECKSUM_MISMATCH",
            "Artifact content no longer matches the reviewed checksum",
        )

    target_status = (
        ArtifactStatus.APPROVED
        if decision == ApprovalStatus.APPROVED
        else ArtifactStatus.REJECTED
    )
    decided_artifact = _copy_artifact(
        artifact,
        status=transition_artifact(artifact.status, target_status),
    )
    approval = ApprovalRecord(
        id=str(uuid4()),
        artifact_id=artifact.id,
        artifact_version=artifact.version_number,
        artifact_checksum=artifact.checksum,
        status=decision,
        approver_id=approver_id,
        correlation_id=correlation_id,
        decided_at=decided_at or utc_now(),
    )
    return decided_artifact, approval


def send_idempotency_key(
    artifact: CommercialArtifact,
    *,
    gmail_thread_id: str,
) -> str:
    if artifact.checksum is None:
        raise ApprovalPolicyViolation(
            "MISSING_CHECKSUM",
            "Cannot create a send key for an artifact without a checksum",
        )
    identity = ":".join(
        (
            artifact.id,
            str(artifact.version_number),
            artifact.checksum,
            gmail_thread_id,
        )
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


class ApprovalPolicy:
    """Verify that one send request matches one current explicit approval."""

    def authorize_send(
        self,
        artifact: CommercialArtifact,
        approval: ApprovalRecord | None,
    ) -> None:
        if approval is None:
            raise ApprovalPolicyViolation(
                "MISSING_APPROVAL",
                "Commercial send requires an explicit approval record",
            )
        if artifact.status == ArtifactStatus.STALE:
            raise ApprovalPolicyViolation(
                "STALE_ARTIFACT",
                "A stale commercial artifact cannot be sent",
            )
        if artifact.status != ArtifactStatus.APPROVED:
            raise ApprovalPolicyViolation(
                "ARTIFACT_NOT_APPROVED",
                f"Artifact status {artifact.status.value} cannot be sent",
            )
        if approval.status != ApprovalStatus.APPROVED:
            raise ApprovalPolicyViolation(
                "APPROVAL_NOT_ACTIVE",
                f"Approval status {approval.status.value} does not authorize send",
            )
        if artifact.checksum is None:
            raise ApprovalPolicyViolation(
                "MISSING_CHECKSUM",
                "Approved artifact is missing its reviewed checksum",
            )
        if artifact.checksum != artifact_content_checksum(artifact):
            raise ApprovalPolicyViolation(
                "CHECKSUM_MISMATCH",
                "Approved artifact content does not match its checksum",
            )
        if approval.artifact_id != artifact.id:
            raise ApprovalPolicyViolation(
                "ARTIFACT_MISMATCH",
                "Approval belongs to a different artifact",
            )
        if approval.artifact_version != artifact.version_number:
            raise ApprovalPolicyViolation(
                "VERSION_MISMATCH",
                "Approval belongs to a different artifact version",
            )
        if approval.artifact_checksum != artifact.checksum:
            raise ApprovalPolicyViolation(
                "APPROVAL_CHECKSUM_MISMATCH",
                "Approval belongs to different artifact content",
            )


class InMemorySendStub:
    """Creates external-action intents only; it never calls Gmail."""

    def __init__(self, policy: ApprovalPolicy | None = None) -> None:
        self._policy = policy or ApprovalPolicy()
        self._intents: dict[str, SendIntent] = {}

    @property
    def intents(self) -> tuple[SendIntent, ...]:
        return tuple(self._intents.values())

    def request_send(
        self,
        artifact: CommercialArtifact,
        approval: ApprovalRecord | None,
        *,
        gmail_thread_id: str,
        correlation_id: str,
        created_at: datetime | None = None,
    ) -> SendIntent:
        self._policy.authorize_send(artifact, approval)
        assert approval is not None
        assert artifact.checksum is not None

        key = send_idempotency_key(
            artifact,
            gmail_thread_id=gmail_thread_id,
        )
        existing = self._intents.get(key)
        if existing is not None:
            return existing

        intent = SendIntent(
            id=f"send-{key[:24]}",
            artifact_id=artifact.id,
            artifact_version=artifact.version_number,
            artifact_checksum=artifact.checksum,
            approval_id=approval.id,
            gmail_thread_id=gmail_thread_id,
            correlation_id=correlation_id,
            idempotency_key=key,
            status=SendIntentStatus.CREATED,
            created_at=created_at or utc_now(),
        )
        self._intents[key] = intent
        return intent

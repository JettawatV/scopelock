"""Human approval commands and idempotent Gmail draft/send execution."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from email.utils import parseaddr

from scopelock.domain.enums import ApprovalStatus, ArtifactStatus, SendIntentStatus
from scopelock.domain.models import (
    ApprovalRecord,
    CommercialArtifact,
    ScopeVersion,
    SendIntent,
)
from scopelock.domain.state_machines import transition_artifact
from scopelock.domain.workflow_models import (
    AuditRecord,
    GmailDraftRecord,
    GmailSendRecord,
)
from scopelock.repositories.contracts import ApplicationRepository
from scopelock.repositories.model_store import CollectionName, ModelStore
from scopelock.security import (
    redacted_error,
    require_bounded_identifier,
    require_email_address,
)
from scopelock.services.approval_policy import (
    ApprovalPolicy,
    ApprovalPolicyViolation,
    decide_artifact,
    send_idempotency_key,
)
from scopelock.services.gmail_gateway import GmailGateway, build_same_thread_reply
from scopelock.services.idempotency_service import IdempotencyKeys
from scopelock.services.identity import stable_id
from scopelock.services.proposal_pdf_service import render_commercial_artifact_pdf
from scopelock.domain.workflow_models import ProjectRecord


class GmailCommercialService:
    """The only component allowed to turn an approval into a Gmail action."""

    def __init__(
        self,
        *,
        gateway: GmailGateway,
        repository: ApplicationRepository,
        mailbox: str,
    ) -> None:
        self._gateway = gateway
        self._repository = repository
        self._store = ModelStore(repository, use_boundaries=True)
        self._mailbox = require_email_address(mailbox, label="Gmail mailbox")
        self._policy = ApprovalPolicy()

    def get_artifact(self, artifact_id: str) -> CommercialArtifact:
        artifact = self._store.get(
            CollectionName.ARTIFACTS, artifact_id, CommercialArtifact
        )
        if artifact is None:
            raise KeyError(f"Unknown artifact {artifact_id}")
        return artifact

    def decide(
        self,
        artifact_id: str,
        *,
        decision: ApprovalStatus,
        approver_id: str,
        correlation_id: str,
        decided_at: datetime | None = None,
    ) -> tuple[CommercialArtifact, ApprovalRecord]:
        artifact = self.get_artifact(artifact_id)
        if artifact.checksum is None:
            raise ApprovalPolicyViolation(
                "MISSING_CHECKSUM", "Artifact is not sealed for review"
            )
        approval_key = IdempotencyKeys.approval(
            artifact.id, artifact.version_number, artifact.checksum
        )
        existing = self._store.find_by_unique_key(
            CollectionName.APPROVALS,
            key_name="artifact_approval",
            key_value=approval_key,
            model_type=ApprovalRecord,
        )
        if existing is not None:
            if existing.status != decision:
                raise ApprovalPolicyViolation(
                    "DECISION_ALREADY_RECORDED",
                    "This artifact version already has a different final decision",
                )
            return artifact, existing
        resolved_at = decided_at or datetime.now(timezone.utc)
        decided_artifact, approval = decide_artifact(
            artifact,
            decision=decision,
            approver_id=approver_id,
            correlation_id=correlation_id,
            decided_at=resolved_at,
        )
        self._store.replace(CollectionName.ARTIFACTS, decided_artifact)
        self._store.create(
            CollectionName.APPROVALS,
            approval,
            unique_keys={"artifact_approval": approval_key},
            immutable=True,
        )
        self._audit(
            entity_id=artifact.id,
            action=f"ARTIFACT_{decision.value}",
            actor="human",
            correlation_id=correlation_id,
            at=resolved_at,
            payload={
                "approval_id": approval.id,
                "artifact_version": artifact.version_number,
                "artifact_checksum": artifact.checksum,
                "approver_id": approver_id,
            },
        )
        return decided_artifact, approval

    def mark_for_revision(
        self,
        artifact_id: str,
        *,
        operator_id: str,
        correlation_id: str,
        reason: str,
        at: datetime | None = None,
    ) -> CommercialArtifact:
        artifact = self.get_artifact(artifact_id)
        if artifact.status not in {
            ArtifactStatus.DRAFT,
            ArtifactStatus.AWAITING_USER_REVIEW,
            ArtifactStatus.APPROVED,
        }:
            raise ApprovalPolicyViolation(
                "ARTIFACT_NOT_REVISABLE",
                f"Artifact status {artifact.status.value} cannot be revised",
            )
        stale = artifact.model_copy(
            update={
                "status": transition_artifact(
                    artifact.status, ArtifactStatus.STALE
                )
            }
        )
        self._store.replace(CollectionName.ARTIFACTS, stale)
        self._audit(
            entity_id=artifact.id,
            action="REVISION_REQUESTED",
            actor="human",
            correlation_id=correlation_id,
            at=at or datetime.now(timezone.utc),
            payload={"operator_id": operator_id, "reason": reason},
        )
        return stale

    def create_draft(
        self,
        artifact_id: str,
        *,
        correlation_id: str,
        created_at: datetime | None = None,
    ) -> GmailDraftRecord:
        artifact = self.get_artifact(artifact_id)
        approval = self._approval_for(artifact)
        if artifact.checksum is None:
            raise ApprovalPolicyViolation(
                "MISSING_CHECKSUM", "Artifact is not sealed for review"
            )
        key = IdempotencyKeys.send_action(
            artifact.id,
            artifact.version_number,
            artifact.checksum,
            self._thread_id(artifact),
        )
        prior = self._store.find_by_unique_key(
            CollectionName.GMAIL_DRAFTS,
            key_name="draft_action",
            key_value=key,
            model_type=GmailDraftRecord,
        )
        self._policy.authorize_send(artifact, approval)
        if approval is None:
            raise ApprovalPolicyViolation(
                "MISSING_APPROVAL", "An explicit approval is required"
            )
        if prior is not None:
            return prior

        at = created_at or datetime.now(timezone.utc)
        thread_id = self._thread_id(artifact)
        pending = GmailDraftRecord(
            id=stable_id("gmail-draft", key),
            artifact_id=artifact.id,
            approval_id=approval.id,
            artifact_checksum=artifact.checksum,
            gmail_thread_id=thread_id,
            status="CREATING",
            idempotency_key=key,
            correlation_id=correlation_id,
            created_at=at,
        )
        self._store.create(
            CollectionName.GMAIL_DRAFTS,
            pending,
            unique_keys={"draft_action": key},
        )
        try:
            client_email = self._client_email(artifact)
            source = self._latest_client_thread_message(
                thread_id, client_email=client_email
            )
            message = build_same_thread_reply(
                thread_id=thread_id,
                source_message=source,
                sender_email=self._mailbox,
                recipient_email=client_email,
                text_body=self._email_body(artifact),
                attachment_name=self._attachment_name(artifact),
                attachment_bytes=self._attachment_bytes(artifact),
            )
            response = self._gateway.create_draft(self._mailbox, message=message)
            draft_id = str(response.get("id") or "")
            response_message = response.get("message")
            response_message_id = (
                str(response_message.get("id") or "")
                if isinstance(response_message, Mapping)
                else ""
            )
            response_thread_id = (
                str(response_message.get("threadId") or "")
                if isinstance(response_message, Mapping)
                else ""
            )
            if not draft_id:
                raise RuntimeError("Gmail drafts.create returned no draft id")
            require_bounded_identifier(draft_id, label="Gmail draft id")
            if response_message_id:
                require_bounded_identifier(
                    response_message_id, label="Gmail draft message id"
                )
            if response_thread_id and response_thread_id != thread_id:
                raise RuntimeError("Gmail draft was created in an unexpected thread")
            completed = pending.model_copy(
                update={
                    "gmail_draft_id": draft_id,
                    "gmail_message_id": response_message_id or None,
                    "status": "CREATED",
                }
            )
            self._store.replace(CollectionName.GMAIL_DRAFTS, completed)
            self._audit(
                entity_id=artifact.id,
                action="GMAIL_DRAFT_CREATED",
                actor="external",
                correlation_id=correlation_id,
                at=at,
                payload={
                    "approval_id": approval.id,
                    "gmail_draft_id": draft_id,
                    "gmail_thread_id": thread_id,
                    "artifact_checksum": artifact.checksum,
                },
            )
            return completed
        except Exception:
            uncertain = pending.model_copy(update={"status": "FAILED_UNCERTAIN"})
            self._store.replace(CollectionName.GMAIL_DRAFTS, uncertain)
            raise

    def send(
        self,
        artifact_id: str,
        *,
        correlation_id: str,
        attempted_at: datetime | None = None,
    ) -> GmailSendRecord:
        artifact = self.get_artifact(artifact_id)
        approval = self._approval_for(artifact)
        if artifact.checksum is None:
            raise ApprovalPolicyViolation(
                "MISSING_CHECKSUM", "Artifact is not sealed for review"
            )
        thread_id = self._thread_id(artifact)
        key = send_idempotency_key(artifact, gmail_thread_id=thread_id)
        prior = self._store.find_by_unique_key(
            CollectionName.GMAIL_SEND_RESULTS,
            key_name="send_action",
            key_value=key,
            model_type=GmailSendRecord,
        )
        if prior is not None:
            return prior
        self._policy.authorize_send(artifact, approval)
        if approval is None:
            raise ApprovalPolicyViolation(
                "MISSING_APPROVAL", "An explicit approval is required"
            )

        draft = self.create_draft(
            artifact_id,
            correlation_id=correlation_id,
            created_at=attempted_at,
        )
        if draft.status != "CREATED" or draft.gmail_draft_id is None:
            raise ApprovalPolicyViolation(
                "DRAFT_NOT_READY", "A confirmed Gmail draft is required before send"
            )
        at = attempted_at or datetime.now(timezone.utc)
        intent = SendIntent(
            id=stable_id("send-intent", key),
            artifact_id=artifact.id,
            artifact_version=artifact.version_number,
            artifact_checksum=artifact.checksum,
            approval_id=approval.id,
            gmail_thread_id=thread_id,
            correlation_id=correlation_id,
            idempotency_key=key,
            status=SendIntentStatus.CREATED,
            created_at=at,
        )
        self._store.create(
            CollectionName.SENDS,
            intent,
            unique_keys={"send_action": key},
            immutable=True,
        )
        sending_record = GmailSendRecord(
            id=stable_id("gmail-send", key),
            send_intent_id=intent.id,
            artifact_id=artifact.id,
            approval_id=approval.id,
            artifact_checksum=artifact.checksum,
            gmail_thread_id=thread_id,
            gmail_draft_id=draft.gmail_draft_id,
            status="SENDING",
            idempotency_key=key,
            correlation_id=correlation_id,
            attempted_at=at,
        )
        self._store.create(
            CollectionName.GMAIL_SEND_RESULTS,
            sending_record,
            unique_keys={"send_action": key},
        )
        sending_artifact = artifact.model_copy(
            update={
                "status": transition_artifact(
                    artifact.status, ArtifactStatus.SENDING
                )
            }
        )
        self._store.replace(CollectionName.ARTIFACTS, sending_artifact)
        try:
            response = self._gateway.send_draft(
                self._mailbox, draft_id=draft.gmail_draft_id
            )
            message_id = str(response.get("id") or "")
            response_thread = str(response.get("threadId") or "")
            if not message_id or response_thread != thread_id:
                raise RuntimeError(
                    "Gmail drafts.send did not confirm the expected message and thread"
                )
            require_bounded_identifier(message_id, label="Gmail sent message id")
            completed_at = datetime.now(timezone.utc)
            sent = sending_record.model_copy(
                update={
                    "gmail_message_id": message_id,
                    "status": "SENT",
                    "completed_at": completed_at,
                }
            )
            self._store.replace(CollectionName.GMAIL_SEND_RESULTS, sent)
            sent_artifact = sending_artifact.model_copy(
                update={
                    "status": transition_artifact(
                        sending_artifact.status, ArtifactStatus.SENT
                    )
                }
            )
            self._store.replace(CollectionName.ARTIFACTS, sent_artifact)
            self._audit(
                entity_id=artifact.id,
                action="GMAIL_ARTIFACT_SENT",
                actor="external",
                correlation_id=correlation_id,
                at=completed_at,
                payload={
                    "approval_id": approval.id,
                    "send_intent_id": intent.id,
                    "gmail_draft_id": draft.gmail_draft_id,
                    "gmail_message_id": message_id,
                    "gmail_thread_id": thread_id,
                    "artifact_checksum": artifact.checksum,
                },
            )
            return sent
        except Exception as error:
            completed_at = datetime.now(timezone.utc)
            safe_error = redacted_error(error, operation="gmail draft send")
            uncertain = sending_record.model_copy(
                update={
                    "status": "FAILED_UNCERTAIN",
                    "error": safe_error,
                    "completed_at": completed_at,
                }
            )
            self._store.replace(CollectionName.GMAIL_SEND_RESULTS, uncertain)
            failed_artifact = sending_artifact.model_copy(
                update={
                    "status": transition_artifact(
                        sending_artifact.status, ArtifactStatus.SEND_FAILED
                    )
                }
            )
            self._store.replace(CollectionName.ARTIFACTS, failed_artifact)
            self._audit(
                entity_id=artifact.id,
                action="GMAIL_SEND_FAILED_UNCERTAIN",
                actor="external",
                correlation_id=correlation_id,
                at=completed_at,
                payload={
                    "approval_id": approval.id,
                    "send_intent_id": intent.id,
                    "gmail_draft_id": draft.gmail_draft_id,
                    "gmail_thread_id": thread_id,
                    "artifact_checksum": artifact.checksum,
                    "error": safe_error,
                },
            )
            return uncertain

    def _approval_for(self, artifact: CommercialArtifact) -> ApprovalRecord | None:
        if artifact.checksum is None:
            return None
        key = IdempotencyKeys.approval(
            artifact.id, artifact.version_number, artifact.checksum
        )
        return self._store.find_by_unique_key(
            CollectionName.APPROVALS,
            key_name="artifact_approval",
            key_value=key,
            model_type=ApprovalRecord,
        )

    def _thread_id(self, artifact: CommercialArtifact) -> str:
        return require_bounded_identifier(
            self._project(artifact).gmail_thread_id, label="Gmail thread id"
        )

    def _client_email(self, artifact: CommercialArtifact) -> str:
        client_email = require_email_address(
            self._project(artifact).client_email, label="project client email"
        )
        if client_email == self._mailbox:
            raise ApprovalPolicyViolation(
                "RECIPIENT_IS_MAILBOX",
                "Commercial email cannot be addressed to the sending mailbox",
            )
        return client_email

    def _latest_client_thread_message(
        self,
        thread_id: str,
        *,
        client_email: str,
    ) -> Mapping[str, object]:
        thread = self._gateway.get_thread(self._mailbox, thread_id)
        messages = [
            item
            for item in thread.get("messages", []) or []
            if isinstance(item, Mapping)
            and self._sender_email(item) == client_email
        ]
        if not messages:
            raise RuntimeError(
                "Gmail thread has no message from the bound project client"
            )
        return max(messages, key=lambda item: int(str(item.get("internalDate") or 0)))

    @staticmethod
    def _sender_email(message: Mapping[str, object]) -> str:
        payload = message.get("payload")
        if not isinstance(payload, Mapping):
            return ""
        headers = payload.get("headers")
        if not isinstance(headers, list):
            return ""
        for item in headers[:200]:
            if not isinstance(item, Mapping):
                continue
            if str(item.get("name") or "").casefold() != "from":
                continue
            parsed = parseaddr(str(item.get("value") or ""))[1]
            try:
                return require_email_address(parsed, label="thread sender")
            except ValueError:
                return ""
        return ""

    @staticmethod
    def _email_body(artifact: CommercialArtifact) -> str:
        label = artifact.artifact_type.value.replace("_", " ").title()
        return (
            f"Please find the approved {label} version {artifact.version_number} "
            "attached.\n\n"
            f"Total: USD {artifact.pricing_result.total_usd:,}\n"
            f"Delivery timeline: {artifact.timeline_result.total_days} days\n\n"
            "This message was sent only after explicit operator approval."
        )

    @staticmethod
    def _attachment_name(artifact: CommercialArtifact) -> str:
        label = artifact.artifact_type.value.casefold().replace("_", "-")
        return f"{label}-v{artifact.version_number}.pdf"

    def _project(self, artifact: CommercialArtifact) -> ProjectRecord:
        project = self._store.get(
            CollectionName.PROJECTS, artifact.project_id, ProjectRecord
        )
        if project is None:
            raise KeyError(f"Missing project {artifact.project_id}")
        return project

    def _attachment_bytes(self, artifact: CommercialArtifact) -> bytes:
        project = self._project(artifact)
        proposed_scope = self._store.get(
            CollectionName.SCOPE_VERSIONS,
            artifact.proposed_scope_version_id,
            ScopeVersion,
        )
        if proposed_scope is None:
            raise KeyError(
                f"Missing proposed scope {artifact.proposed_scope_version_id}"
            )
        baseline_scope = None
        if artifact.baseline_scope_version_id is not None:
            baseline_scope = self._store.get(
                CollectionName.SCOPE_VERSIONS,
                artifact.baseline_scope_version_id,
                ScopeVersion,
            )
            if baseline_scope is None:
                raise KeyError(
                    f"Missing baseline scope {artifact.baseline_scope_version_id}"
                )
        return render_commercial_artifact_pdf(
            artifact=artifact,
            project=project,
            proposed_scope=proposed_scope,
            baseline_scope=baseline_scope,
        )

    def _audit(
        self,
        *,
        entity_id: str,
        action: str,
        actor: str,
        correlation_id: str,
        at: datetime,
        payload: dict[str, object],
    ) -> None:
        record = AuditRecord(
            id=stable_id("audit", entity_id, action, correlation_id),
            record_type="GMAIL_COMMERCIAL_ACTION",
            entity_id=entity_id,
            action=action,
            actor=actor,
            correlation_id=correlation_id,
            payload=payload,
            created_at=at,
        )
        self._store.create(CollectionName.AUDIT_RECORDS, record)

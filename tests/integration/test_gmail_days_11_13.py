import asyncio
import base64
import json
from datetime import datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from scopelock.domain.enums import (
    AgentRoute,
    ApprovalStatus,
    ArtifactStatus,
    BufferFinalizationReason,
    EmailDirection,
    InboundProcessingStatus,
    ProjectLifecycleStatus,
    ScopeEventClassification,
    ScopeEventStatus,
    ScopeVersionStatus,
)
from scopelock.domain.models import ModuleQuantity, ScopeRequirementSnapshot
from scopelock.domain.workflow_models import (
    GmailEventBatchResult,
    GmailHistoryCheckpoint,
    InboundEmail,
    InboundMessageRecord,
    InboundProcessingResult,
    ProjectRecord,
    ScopeEventRecord,
)
from scopelock.repositories.in_memory import InMemoryApplicationRepository
from scopelock.repositories.model_store import CollectionName, ModelStore
from scopelock.services.approval_policy import (
    ApprovalPolicyViolation,
    seal_artifact_for_review,
)
from scopelock.services.commercial_artifact_service import (
    accept_scope_version,
    create_next_commercial_artifact,
    create_scope_version,
)
from scopelock.services.gmail_commercial_service import GmailCommercialService
from scopelock.services.gmail_event_service import GmailEventService
from scopelock.services.gmail_event_service import (
    GmailEventInProgress,
    PubSubEnvelopeError,
    decode_gmail_notification,
)
from scopelock.services.gmail_gateway import (
    GmailFullSyncRequired,
    build_same_thread_reply,
)
from scopelock.services.gmail_oauth import (
    GMAIL_OAUTH_SCOPES,
    GmailCredentialProvider,
    GmailOAuthConfig,
)
from scopelock.services.gmail_watch_service import (
    GmailWatchConfigurationError,
    GmailWatchService,
)
from scopelock.http_api import GmailApiRuntime, create_app
from scopelock.services.identity import stable_hash, stable_id
from scopelock.services.idempotency_service import IdempotencyKeys
from scopelock.services.pricing_engine import PricingEngine
from scopelock.services.scope_buffer_service import ScopeBufferService
from scopelock.services.scope_revision_workflow import ScopeRevisionWorkflow
from scopelock.services.sop_service import load_sop
from scopelock.services.timeline_engine import TimelineEngine


NOW = datetime(2026, 8, 29, 4, 0, tzinfo=timezone.utc)
MAILBOX = "demo@example.com"
TOPIC = "projects/scopelock-506806/topics/scopelock-gmail"


def _encoded(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def _message(message_id="message-1", history_id="105", *, sender="client@example.com"):
    return {
        "id": message_id,
        "threadId": "thread-1",
        "historyId": history_id,
        "internalDate": str(int(NOW.timestamp() * 1000)),
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "From", "value": sender},
                {"name": "To", "value": MAILBOX},
                {"name": "Subject", "value": "Automation requirements"},
                {"name": "Message-ID", "value": f"<{message_id}@example.com>"},
                {"name": "References", "value": "<root@example.com>"},
            ],
            "body": {"data": _encoded("Please automate our shared inbox.")},
        },
    }


def _pubsub(event_id: str, history_id: str):
    data = _encoded(
        json.dumps({"emailAddress": MAILBOX, "historyId": history_id})
    )
    return {"message": {"messageId": event_id, "data": data}}


class FakeGmailGateway:
    def __init__(self):
        self.watch_history_id = "100"
        self.history_pages = {
            None: {
                "history": [
                    {"id": "105", "messagesAdded": [{"message": {"id": "message-1"}}]}
                ],
                "historyId": "105",
            }
        }
        self.messages = {"message-1": _message()}
        self.create_calls = 0
        self.send_calls = 0
        self.created_message = None
        self.fail_send = False

    def watch(self, mailbox, *, topic_name):
        assert mailbox == MAILBOX
        assert topic_name == TOPIC
        return {
            "historyId": self.watch_history_id,
            "expiration": str(int((NOW + timedelta(days=7)).timestamp() * 1000)),
        }

    def list_history_page(self, mailbox, *, start_history_id, page_token=None):
        assert mailbox == MAILBOX
        assert start_history_id == "100"
        page = self.history_pages[page_token]
        if isinstance(page, Exception):
            raise page
        return page

    def get_message(self, mailbox, message_id):
        return self.messages[message_id]

    def get_thread(self, mailbox, thread_id):
        assert thread_id == "thread-1"
        return {"id": thread_id, "messages": list(self.messages.values())}

    def create_draft(self, mailbox, *, message):
        self.create_calls += 1
        self.created_message = message
        return {"id": "draft-1", "message": {"id": "draft-message-1"}}

    def send_draft(self, mailbox, *, draft_id):
        self.send_calls += 1
        if self.fail_send:
            raise ConnectionError("outcome unknown")
        return {"id": "sent-message-1", "threadId": "thread-1"}


class FakeInboundWorkflow:
    def __init__(self):
        self.calls = []

    async def process(self, email, *, prior_messages=()):
        self.calls.append((email, tuple(prior_messages)))
        return InboundProcessingResult(
            idempotency_key=stable_hash("result", email.message_id),
            correlation_id="corr-inbound",
            status=InboundProcessingStatus.IGNORED,
            route=AgentRoute.REQUIREMENT_ANALYSIS,
            message_id=email.message_id,
            thread_id=email.thread_id,
        )


def test_oauth_scope_set_is_exact_and_excludes_full_mailbox_access():
    assert set(GMAIL_OAUTH_SCOPES) == {
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.compose",
    }
    assert "https://mail.google.com/" not in GMAIL_OAUTH_SCOPES


def test_oauth_provider_rejects_tokens_with_extra_mailbox_scopes():
    provider = GmailCredentialProvider(
        GmailOAuthConfig(
            client_secret_path=Path("client.json"),
            token_path=Path("token.json"),
        )
    )
    credentials = SimpleNamespace(
        scopes=GMAIL_OAUTH_SCOPES + ("https://mail.google.com/",)
    )
    with pytest.raises(RuntimeError, match="unexpected scopes"):
        provider._validate_scopes(credentials)


def test_watch_creates_checkpoint_and_renewal_never_skips_history():
    repository = InMemoryApplicationRepository(clock=lambda: NOW)
    gateway = FakeGmailGateway()
    service = GmailWatchService(
        gateway=gateway,
        repository=repository,
        google_cloud_project="scopelock-506806",
    )
    first = service.register(mailbox=MAILBOX, topic_name=TOPIC, now=NOW)
    gateway.watch_history_id = "200"
    second = service.register(mailbox=MAILBOX, topic_name=TOPIC, now=NOW + timedelta(days=1))

    checkpoint = ModelStore(repository).find_by_unique_key(
        CollectionName.GMAIL_CHECKPOINTS,
        key_name="mailbox",
        key_value=MAILBOX,
        model_type=GmailHistoryCheckpoint,
    )
    assert checkpoint is not None and checkpoint.history_id == "100"
    assert first.history_id == "100" and second.history_id == "200"
    assert service.renewal_due(first, now=NOW + timedelta(days=6, hours=1))


def test_pubsub_history_replay_and_out_of_order_are_idempotent():
    repository = InMemoryApplicationRepository(clock=lambda: NOW)
    gateway = FakeGmailGateway()
    GmailWatchService(
        gateway=gateway,
        repository=repository,
        google_cloud_project="scopelock-506806",
    ).register(mailbox=MAILBOX, topic_name=TOPIC, now=NOW)
    workflow = FakeInboundWorkflow()
    service = GmailEventService(
        gateway=gateway,
        workflow=workflow,
        repository=repository,
        mailbox=MAILBOX,
    )

    first = asyncio.run(service.process_pubsub(_pubsub("event-1", "105"), received_at=NOW))
    replay = asyncio.run(service.process_pubsub(_pubsub("event-1", "105"), received_at=NOW))
    old = asyncio.run(service.process_pubsub(_pubsub("event-2", "104"), received_at=NOW))

    assert first.status == "COMPLETED"
    assert replay.replayed is True
    assert old.status == "IGNORED_OUT_OF_ORDER"
    assert len(workflow.calls) == 1
    assert workflow.calls[0][0].message_id == "message-1"
    checkpoint = ModelStore(repository).find_by_unique_key(
        CollectionName.GMAIL_CHECKPOINTS,
        key_name="mailbox",
        key_value=MAILBOX,
        model_type=GmailHistoryCheckpoint,
    )
    assert checkpoint is not None and checkpoint.history_id == "105"


def test_expired_history_fails_closed_without_advancing_checkpoint():
    repository = InMemoryApplicationRepository(clock=lambda: NOW)
    gateway = FakeGmailGateway()
    GmailWatchService(
        gateway=gateway,
        repository=repository,
        google_cloud_project="scopelock-506806",
    ).register(mailbox=MAILBOX, topic_name=TOPIC, now=NOW)
    gateway.history_pages[None] = GmailFullSyncRequired("checkpoint expired")
    service = GmailEventService(
        gateway=gateway,
        workflow=FakeInboundWorkflow(),
        repository=repository,
        mailbox=MAILBOX,
    )

    result = asyncio.run(
        service.process_pubsub(_pubsub("event-expired", "999"), received_at=NOW)
    )
    checkpoint = ModelStore(repository).find_by_unique_key(
        CollectionName.GMAIL_CHECKPOINTS,
        key_name="mailbox",
        key_value=MAILBOX,
        model_type=GmailHistoryCheckpoint,
    )
    assert result.status == "FULL_SYNC_REQUIRED"
    assert checkpoint is not None and checkpoint.history_id == "100"


def _commercial_state(*, accepted_baseline=False):
    repository = InMemoryApplicationRepository(clock=lambda: NOW)
    store = ModelStore(repository)
    catalog = load_sop("config/jvl_sop.example.yaml")
    selections = (
        ModuleQuantity(module_key="core_workflow_automation", quantity=1),
        ModuleQuantity(module_key="email_intake", quantity=1),
    )
    pricing = PricingEngine(catalog).calculate(selections)
    timeline = TimelineEngine(catalog).calculate(selections)
    scope = create_scope_version(
        project_id="project-1",
        existing=(),
        requirements=(
            ScopeRequirementSnapshot(
                requirement_id="REQ-01",
                category="Workflow",
                description="Automate one Gmail intake workflow.",
                normalized_key="gmail_workflow",
                source_message_id="message-1",
                source_quote="automate our shared inbox",
            ),
        ),
        module_selections=timeline.calculation_inputs,
        pricing_result=pricing,
        timeline_result=timeline,
        scope_version_id="scope-1",
        created_at=NOW,
    )
    if accepted_baseline:
        scope = accept_scope_version(scope)
    project = ProjectRecord(
        id="project-1",
        client_name="Client",
        client_email="client@example.com",
        gmail_thread_id="thread-1",
        title="Automation requirements",
        lifecycle_status=(
            ProjectLifecycleStatus.ACTIVE_PROJECT
            if accepted_baseline
            else ProjectLifecycleStatus.AWAITING_USER_REVIEW
        ),
        baseline_scope_version_id=scope.id if accepted_baseline else None,
        active_scope_version_id=scope.id,
        current_price_usd=scope.total_price_usd,
        current_timeline_days=scope.timeline_days,
        correlation_id="corr-project",
        created_at=NOW,
        updated_at=NOW,
    )
    store.create(CollectionName.PROJECTS, project)
    store.create(CollectionName.SCOPE_VERSIONS, scope)
    return repository, catalog, project, scope


def _review_artifact(repository, scope):
    artifact = seal_artifact_for_review(
        create_next_commercial_artifact(
            project_id=scope.project_id,
            proposed_scope=scope,
            existing=(),
            created_at=NOW,
            artifact_id="artifact-1",
        )
    )
    ModelStore(repository).create(CollectionName.ARTIFACTS, artifact)
    project_doc = repository.get(collection="projects", document_id="project-1")
    project = ProjectRecord.model_validate(project_doc.payload).model_copy(
        update={"active_proposal_id": artifact.id}
    )
    ModelStore(repository).replace(CollectionName.PROJECTS, project)
    return artifact


def test_approval_creates_same_thread_draft_and_replay_sends_once():
    repository, _, _, scope = _commercial_state()
    artifact = _review_artifact(repository, scope)
    gateway = FakeGmailGateway()
    service = GmailCommercialService(
        gateway=gateway, repository=repository, mailbox=MAILBOX
    )
    approved, approval = service.decide(
        artifact.id,
        decision=ApprovalStatus.APPROVED,
        approver_id="operator@example.com",
        correlation_id="corr-approve",
        decided_at=NOW,
    )
    draft = service.create_draft(
        approved.id, correlation_id="corr-draft", created_at=NOW
    )
    first = service.send(approved.id, correlation_id="corr-send", attempted_at=NOW)
    replay = service.send(approved.id, correlation_id="corr-send-replay", attempted_at=NOW)

    assert approval.artifact_checksum == approved.checksum
    assert draft.gmail_thread_id == "thread-1" and draft.status == "CREATED"
    assert first.status == "SENT" and replay.id == first.id
    assert gateway.create_calls == 1 and gateway.send_calls == 1
    assert gateway.created_message["threadId"] == "thread-1"
    padding = "=" * (-len(gateway.created_message["raw"]) % 4)
    parsed = BytesParser(policy=policy.default).parsebytes(
        base64.urlsafe_b64decode(gateway.created_message["raw"] + padding)
    )
    assert parsed["Subject"] == "Automation requirements"
    assert parsed["In-Reply-To"] == "<message-1@example.com>"
    assert "<root@example.com>" in parsed["References"]
    assert len(list(parsed.iter_attachments())) == 1


def test_no_approval_means_no_draft_or_send():
    repository, _, _, scope = _commercial_state()
    artifact = _review_artifact(repository, scope)
    gateway = FakeGmailGateway()
    service = GmailCommercialService(
        gateway=gateway, repository=repository, mailbox=MAILBOX
    )
    with pytest.raises(ApprovalPolicyViolation):
        service.create_draft(artifact.id, correlation_id="corr-denied")
    with pytest.raises(ApprovalPolicyViolation):
        service.send(artifact.id, correlation_id="corr-denied")
    assert gateway.create_calls == 0 and gateway.send_calls == 0


def test_revision_request_invalidates_previous_approval():
    repository, _, _, scope = _commercial_state()
    artifact = _review_artifact(repository, scope)
    gateway = FakeGmailGateway()
    service = GmailCommercialService(
        gateway=gateway, repository=repository, mailbox=MAILBOX
    )
    approved, _ = service.decide(
        artifact.id,
        decision=ApprovalStatus.APPROVED,
        approver_id="operator@example.com",
        correlation_id="corr-approve",
        decided_at=NOW,
    )
    stale = service.mark_for_revision(
        approved.id,
        operator_id="operator@example.com",
        correlation_id="corr-revise",
        reason="Client requested a correction.",
        at=NOW,
    )
    with pytest.raises(ApprovalPolicyViolation):
        service.create_draft(stale.id, correlation_id="corr-stale-draft")
    assert stale.status == ArtifactStatus.STALE
    assert gateway.create_calls == 0


def test_uncertain_send_is_not_blindly_retried():
    repository, _, _, scope = _commercial_state()
    artifact = _review_artifact(repository, scope)
    gateway = FakeGmailGateway()
    gateway.fail_send = True
    service = GmailCommercialService(
        gateway=gateway, repository=repository, mailbox=MAILBOX
    )
    approved, _ = service.decide(
        artifact.id,
        decision=ApprovalStatus.APPROVED,
        approver_id="operator@example.com",
        correlation_id="corr-approve",
        decided_at=NOW,
    )
    first = service.send(approved.id, correlation_id="corr-send", attempted_at=NOW)
    replay = service.send(approved.id, correlation_id="corr-retry", attempted_at=NOW)
    assert first.status == "FAILED_UNCERTAIN" and replay.id == first.id
    assert gateway.send_calls == 1
    stored = service.get_artifact(approved.id)
    assert stored.status == ArtifactStatus.SEND_FAILED


def test_scope_buffer_finalizes_sends_and_updates_canonical_scope_only_on_acceptance():
    repository, catalog, project, baseline = _commercial_state(accepted_baseline=True)
    event = ScopeEventRecord(
        id="scope-event-1",
        project_id=project.id,
        gmail_message_id="message-change",
        baseline_scope_version_id=baseline.id,
        classification=ScopeEventClassification.EXPANSION,
        status=ScopeEventStatus.CLASSIFIED,
        description="Add LINE notifications.",
        additions=(ModuleQuantity(module_key="line_notifications", quantity=1),),
        correlation_id="corr-change",
        created_at=NOW,
    )
    buffered_event, buffer = ScopeBufferService(catalog).buffer_event(
        baseline=baseline, event=event
    )
    store = ModelStore(repository)
    store.create(CollectionName.SCOPE_EVENTS, buffered_event)
    store.create(CollectionName.BUFFERS, buffer)
    store.replace(
        CollectionName.PROJECTS,
        project.model_copy(update={"scope_buffer_id": buffer.id}),
    )
    revisions = ScopeRevisionWorkflow(catalog=catalog, repository=repository)
    result = revisions.finalize_buffer(
        buffer.id,
        reason=BufferFinalizationReason.MANUAL,
        finalized_at=NOW,
    )
    replayed_result = revisions.finalize_buffer(
        buffer.id,
        reason=BufferFinalizationReason.MANUAL,
        finalized_at=NOW,
    )

    before_acceptance = store.get(CollectionName.PROJECTS, project.id, ProjectRecord)
    assert result.artifact.status == ArtifactStatus.AWAITING_USER_REVIEW
    assert replayed_result.artifact.id == result.artifact.id
    assert len(repository.list(collection="artifacts")) == 1
    assert result.artifact.source_buffer_id == buffer.id
    assert before_acceptance.baseline_scope_version_id == baseline.id
    assert before_acceptance.current_price_usd == baseline.total_price_usd

    gateway = FakeGmailGateway()
    commercial = GmailCommercialService(
        gateway=gateway, repository=repository, mailbox=MAILBOX
    )
    approved, _ = commercial.decide(
        result.artifact.id,
        decision=ApprovalStatus.APPROVED,
        approver_id="operator@example.com",
        correlation_id="corr-co-approve",
        decided_at=NOW,
    )
    sent = commercial.send(
        approved.id, correlation_id="corr-co-send", attempted_at=NOW
    )
    assert sent.status == "SENT"
    acceptance_email = InboundEmail(
        message_id="message-acceptance",
        thread_id=project.gmail_thread_id,
        sender_name="Client",
        sender_email=project.client_email,
        subject="Re: Automation requirements",
        body="I accept the approved change order.",
        received_at=NOW,
        direction=EmailDirection.INBOUND,
    )
    store.create(
        CollectionName.INBOUND_MESSAGES,
        InboundMessageRecord(
            id=stable_id("inbound-message", acceptance_email.message_id),
            email=acceptance_email,
            correlation_id="corr-client-acceptance",
            created_at=NOW,
        ),
        unique_keys={
            "gmail_message_id": IdempotencyKeys.gmail_message(
                acceptance_email.message_id
            )
        },
        immutable=True,
    )
    accepted_artifact, accepted_scope, final_project = revisions.accept_sent_artifact(
        approved.id,
        acceptance_message_id=acceptance_email.message_id,
        correlation_id="corr-client-acceptance",
        accepted_at=NOW,
    )

    old_baseline = store.get(CollectionName.SCOPE_VERSIONS, baseline.id, type(baseline))
    applied_event = store.get(
        CollectionName.SCOPE_EVENTS, buffered_event.id, ScopeEventRecord
    )
    assert accepted_artifact.status == ArtifactStatus.ACCEPTED
    assert accepted_scope.status == ScopeVersionStatus.ACCEPTED
    assert old_baseline.status == ScopeVersionStatus.SUPERSEDED
    assert final_project.baseline_scope_version_id == accepted_scope.id
    assert final_project.current_price_usd == accepted_scope.total_price_usd
    assert applied_event.status == ScopeEventStatus.APPLIED


def test_operator_http_commands_require_the_configured_key():
    repository = InMemoryApplicationRepository(clock=lambda: NOW)
    gateway = FakeGmailGateway()
    watch = GmailWatchService(
        gateway=gateway,
        repository=repository,
        google_cloud_project="scopelock-506806",
    )
    runtime = GmailApiRuntime(
        event_service=None,
        watch_service=watch,
        commercial_service=None,
        revision_workflow=None,
        mailbox=MAILBOX,
        topic_name=TOPIC,
        operator_api_key="operator-secret",
        pubsub_verifier=None,
    )
    client = TestClient(create_app(lambda: runtime))

    assert client.get("/healthz").status_code == 200
    assert client.post("/gmail/watch").status_code == 401
    accepted = client.post(
        "/gmail/watch",
        headers={"X-ScopeLock-Operator-Key": "operator-secret"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["history_id"] == "100"


def _event_service_with_checkpoint(*, workflow=None):
    repository = InMemoryApplicationRepository(clock=lambda: NOW)
    gateway = FakeGmailGateway()
    GmailWatchService(
        gateway=gateway,
        repository=repository,
        google_cloud_project="scopelock-506806",
    ).register(mailbox=MAILBOX, topic_name=TOPIC, now=NOW)
    resolved_workflow = workflow or FakeInboundWorkflow()
    service = GmailEventService(
        gateway=gateway,
        workflow=resolved_workflow,
        repository=repository,
        mailbox=MAILBOX,
    )
    return repository, gateway, resolved_workflow, service


def test_active_pubsub_processing_lease_blocks_a_second_worker():
    repository, _, workflow, service = _event_service_with_checkpoint()
    event_id = "event-active-lease"
    event = GmailEventBatchResult(
        id=stable_id("pubsub-event", event_id),
        pubsub_message_id=event_id,
        mailbox=MAILBOX,
        notification_history_id="105",
        start_history_id="100",
        status="PROCESSING",
        processing_attempt_id="first-worker",
        lease_expires_at=NOW + timedelta(minutes=5),
        created_at=NOW,
    )
    ModelStore(repository).create(
        CollectionName.PUBSUB_EVENTS,
        event,
        unique_keys={
            "pubsub_event_id": IdempotencyKeys.pubsub_event(event_id)
        },
    )

    with pytest.raises(GmailEventInProgress):
        asyncio.run(
            service.process_pubsub(_pubsub(event_id, "105"), received_at=NOW)
        )
    assert workflow.calls == []


def test_expired_processing_lease_is_reclaimed_after_a_crash():
    repository, _, workflow, service = _event_service_with_checkpoint()
    event_id = "event-expired-lease"
    event = GmailEventBatchResult(
        id=stable_id("pubsub-event", event_id),
        pubsub_message_id=event_id,
        mailbox=MAILBOX,
        notification_history_id="105",
        start_history_id="100",
        status="PROCESSING",
        processing_attempt_id="crashed-worker",
        lease_expires_at=NOW - timedelta(seconds=1),
        created_at=NOW - timedelta(minutes=20),
    )
    ModelStore(repository).create(
        CollectionName.PUBSUB_EVENTS,
        event,
        unique_keys={
            "pubsub_event_id": IdempotencyKeys.pubsub_event(event_id)
        },
    )

    result = asyncio.run(
        service.process_pubsub(_pubsub(event_id, "105"), received_at=NOW)
    )
    assert result.status == "COMPLETED"
    assert len(workflow.calls) == 1


def test_history_checkpoint_never_moves_backward():
    _, _, _, service = _event_service_with_checkpoint()
    first = service._advance_checkpoint(
        MAILBOX, final_history_id="200", updated_at=NOW
    )
    second = service._advance_checkpoint(
        MAILBOX,
        final_history_id="150",
        updated_at=NOW + timedelta(seconds=1),
    )
    assert first.history_id == "200"
    assert second.history_id == "200"


def test_pubsub_payload_and_history_batches_are_bounded():
    with pytest.raises(PubSubEnvelopeError):
        decode_gmail_notification(
            {"message": {"messageId": "event", "data": "A" * 4_097}}
        )

    repository, gateway, _, service = _event_service_with_checkpoint()
    gateway.history_pages[None] = {
        "history": [
            {
                "id": "105",
                "messagesAdded": [
                    {"message": {"id": f"message-{index}"}}
                    for index in range(101)
                ],
            }
        ],
        "historyId": "105",
    }
    result = asyncio.run(
        service.process_pubsub(
            _pubsub("event-oversized-batch", "105"), received_at=NOW
        )
    )
    stored = ModelStore(repository).get(
        CollectionName.PUBSUB_EVENTS,
        stable_id("pubsub-event", "event-oversized-batch"),
        GmailEventBatchResult,
    )
    assert result.status == "FULL_SYNC_REQUIRED"
    assert stored is not None and stored.status == "FULL_SYNC_REQUIRED"
    assert "message-100" not in (stored.error or "")


def test_thread_context_excludes_messages_newer_than_the_current_event():
    _, gateway, workflow, service = _event_service_with_checkpoint()
    prior = _message("message-prior", "103")
    prior["internalDate"] = str(int((NOW - timedelta(minutes=1)).timestamp() * 1000))
    current = _message("message-1", "105")
    future = _message("message-future", "106")
    future["internalDate"] = str(int((NOW + timedelta(minutes=1)).timestamp() * 1000))
    gateway.messages = {
        "message-prior": prior,
        "message-1": current,
        "message-future": future,
    }

    asyncio.run(
        service.process_pubsub(_pubsub("event-bounded-context", "105"), received_at=NOW)
    )
    prior_ids = [item.message_id for item in workflow.calls[0][1]]
    assert prior_ids == ["message-prior"]


def test_commercial_draft_requires_a_message_from_the_bound_client():
    repository, _, _, scope = _commercial_state()
    artifact = _review_artifact(repository, scope)
    gateway = FakeGmailGateway()
    gateway.messages["message-1"] = _message(sender="attacker@example.com")
    service = GmailCommercialService(
        gateway=gateway, repository=repository, mailbox=MAILBOX
    )
    approved, _ = service.decide(
        artifact.id,
        decision=ApprovalStatus.APPROVED,
        approver_id="operator@example.com",
        correlation_id="corr-bound-client",
        decided_at=NOW,
    )

    with pytest.raises(RuntimeError, match="bound project client"):
        service.create_draft(
            approved.id, correlation_id="corr-bound-client-draft", created_at=NOW
        )
    assert gateway.create_calls == 0


def test_same_thread_reply_rejects_header_injection():
    source = _message()
    source["payload"]["headers"][2]["value"] = "Proposal\r\nBcc: attacker@example.com"
    with pytest.raises(ValueError):
        build_same_thread_reply(
            thread_id="thread-1",
            source_message=source,
            sender_email=MAILBOX,
            recipient_email="client@example.com",
            text_body="Approved proposal",
            attachment_name="proposal-v1.json",
            attachment_bytes=b"{}",
        )


def test_acceptance_requires_client_message_evidence_from_same_thread():
    repository, catalog, project, baseline = _commercial_state(accepted_baseline=True)
    event = ScopeEventRecord(
        id="scope-event-evidence",
        project_id=project.id,
        gmail_message_id="message-change",
        baseline_scope_version_id=baseline.id,
        classification=ScopeEventClassification.EXPANSION,
        status=ScopeEventStatus.CLASSIFIED,
        description="Add LINE notifications.",
        additions=(ModuleQuantity(module_key="line_notifications", quantity=1),),
        correlation_id="corr-change-evidence",
        created_at=NOW,
    )
    buffered_event, buffer = ScopeBufferService(catalog).buffer_event(
        baseline=baseline, event=event
    )
    store = ModelStore(repository)
    store.create(CollectionName.SCOPE_EVENTS, buffered_event)
    store.create(CollectionName.BUFFERS, buffer)
    store.replace(
        CollectionName.PROJECTS,
        project.model_copy(update={"scope_buffer_id": buffer.id}),
    )
    revisions = ScopeRevisionWorkflow(catalog=catalog, repository=repository)
    finalized = revisions.finalize_buffer(
        buffer.id,
        reason=BufferFinalizationReason.MANUAL,
        finalized_at=NOW,
    )
    gateway = FakeGmailGateway()
    commercial = GmailCommercialService(
        gateway=gateway, repository=repository, mailbox=MAILBOX
    )
    approved, _ = commercial.decide(
        finalized.artifact.id,
        decision=ApprovalStatus.APPROVED,
        approver_id="operator@example.com",
        correlation_id="corr-acceptance-evidence",
        decided_at=NOW,
    )
    assert commercial.send(
        approved.id, correlation_id="corr-send-evidence", attempted_at=NOW
    ).status == "SENT"
    attacker_email = InboundEmail(
        message_id="message-fake-acceptance",
        thread_id=project.gmail_thread_id,
        sender_name="Attacker",
        sender_email="attacker@example.com",
        subject="Re: Automation requirements",
        body="Accepted.",
        received_at=NOW,
        direction=EmailDirection.INBOUND,
    )
    store.create(
        CollectionName.INBOUND_MESSAGES,
        InboundMessageRecord(
            id=stable_id("inbound-message", attacker_email.message_id),
            email=attacker_email,
            correlation_id="corr-fake-acceptance",
            created_at=NOW,
        ),
        unique_keys={
            "gmail_message_id": IdempotencyKeys.gmail_message(
                attacker_email.message_id
            )
        },
        immutable=True,
    )

    with pytest.raises(ValueError, match="bound to the project client"):
        revisions.accept_sent_artifact(
            approved.id,
            acceptance_message_id=attacker_email.message_id,
            correlation_id="corr-fake-acceptance",
            accepted_at=NOW,
        )


def test_http_surface_hides_internal_errors_limits_bodies_and_disables_docs():
    def failing_runtime():
        raise RuntimeError("refresh_token=do-not-expose-this")

    client = TestClient(create_app(failing_runtime))
    failure = client.post(
        "/gmail/watch", headers={"X-ScopeLock-Operator-Key": "irrelevant"}
    )
    assert failure.status_code == 503
    assert "do-not-expose-this" not in failure.text
    assert "reference=" in failure.text
    assert failure.headers["cache-control"] == "no-store"
    assert failure.headers["x-content-type-options"] == "nosniff"
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404

    oversized = client.post("/webhooks/gmail", content=b"x" * (64 * 1024 + 1))
    assert oversized.status_code == 413
    assert oversized.headers["x-frame-options"] == "DENY"


def test_watch_rejects_topic_prefix_tricks():
    repository = InMemoryApplicationRepository(clock=lambda: NOW)
    service = GmailWatchService(
        gateway=FakeGmailGateway(),
        repository=repository,
        google_cloud_project="scopelock-506806",
    )
    with pytest.raises(GmailWatchConfigurationError):
        service.register(
            mailbox=MAILBOX,
            topic_name="projects/scopelock-506806/topics/../attacker",
            now=NOW,
        )

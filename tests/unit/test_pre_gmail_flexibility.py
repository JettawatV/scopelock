import base64
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from scopelock.domain.enums import (
    AgentRoute,
    EmailBodyFormat,
    EmailDirection,
    ProjectLifecycleStatus,
    ScopeEventClassification,
)
from scopelock.domain.models import (
    ClientConstraint,
    EvidenceRef,
    ScopeAnalysis,
    ScopeEventProposal,
)
from scopelock.domain.workflow_models import InboundEmail, ProjectRecord
from scopelock.repositories.in_memory import InMemoryApplicationRepository
from scopelock.repositories.model_store import CollectionName, ModelStore
from scopelock.services.gmail_message_normalizer import (
    bounded_thread_context,
    normalize_gmail_message,
)
from scopelock.services.idempotency_service import IdempotencyKeys
from scopelock.services.inbound_router import InboundMessageRouter
from scopelock.services.sop_service import load_sop


NOW = datetime(2026, 8, 28, tzinfo=timezone.utc)


def _encoded(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def _gmail_payload(*, mime_type="text/plain", body="hello", sender="client@example.com"):
    return {
        "id": "message-1",
        "threadId": "thread-1",
        "historyId": "42",
        "internalDate": str(int(NOW.timestamp() * 1000)),
        "payload": {
            "mimeType": mime_type,
            "headers": [
                {"name": "From", "value": sender},
                {"name": "To", "value": "demo@example.com"},
                {"name": "Subject", "value": "ระบบรับคำขอ"},
            ],
            "body": {"data": _encoded(body)},
        },
    }


def test_normalizer_preserves_thai_strips_quote_and_hashes_raw_payload():
    message = _gmail_payload(body="ช่วยทำแดชบอร์ด\n\nOn Tue, Client wrote:\nold text")
    normalized = normalize_gmail_message(message, account_email="demo@example.com")

    assert normalized.body == "ช่วยทำแดชบอร์ด"
    assert normalized.subject == "ระบบรับคำขอ"
    assert normalized.direction == EmailDirection.INBOUND
    assert normalized.body_format == EmailBodyFormat.PLAIN
    assert normalized.raw_content_hash and len(normalized.raw_content_hash) == 64


def test_normalizer_falls_back_to_html_and_records_attachment_metadata():
    message = _gmail_payload(mime_type="multipart/mixed", body="")
    message["payload"]["parts"] = [
        {
            "mimeType": "text/html",
            "body": {"data": _encoded("<p>Hello <b>team</b></p>")},
        },
        {
            "mimeType": "application/pdf",
            "filename": "brief.pdf",
            "body": {"attachmentId": "attachment-1", "size": 123},
        },
    ]
    normalized = normalize_gmail_message(message)

    assert normalized.body == "Hello team"
    assert normalized.body_format == EmailBodyFormat.HTML_FALLBACK
    assert normalized.attachments[0].filename == "brief.pdf"
    assert "brief.pdf" not in normalized.body


def test_html_fallback_removes_scripts_and_quoted_reply_blocks():
    message = _gmail_payload(mime_type="text/html", body="")
    message["payload"]["body"] = {
        "data": _encoded(
            "<p>Current request</p><script>secret()</script>"
            "<blockquote>old client message</blockquote><p>Still current</p>"
        )
    }

    normalized = normalize_gmail_message(message)

    assert normalized.body == "Current request Still current"
    assert "secret" not in normalized.body
    assert "old client" not in normalized.body


def test_normalizer_prefers_plain_text_strips_signature_and_bounds_content():
    message = _gmail_payload(mime_type="multipart/alternative", body="")
    message["payload"]["parts"] = [
        {
            "mimeType": "text/html",
            "body": {"data": _encoded("<p>HTML version</p>")},
        },
        {
            "mimeType": "text/plain",
            "body": {"data": _encoded("P" * 20_100 + "\n-- \nSignature")},
        },
    ]

    normalized = normalize_gmail_message(message)

    assert normalized.body_format == EmailBodyFormat.PLAIN
    assert normalized.body == "P" * 20_000
    assert "HTML version" not in normalized.body
    assert "Signature" not in normalized.body


def test_normalizer_marks_empty_body_and_bounds_five_prior_messages():
    empty = normalize_gmail_message(_gmail_payload(body=""))
    assert empty.body == ""
    assert empty.body_format == EmailBodyFormat.EMPTY

    messages = [
        InboundEmail(
            message_id=f"message-{index}",
            thread_id="thread-1",
            sender_name="Client",
            sender_email="client@example.com",
            subject="Thread",
            body=str(index) * 5_000,
            received_at=NOW.replace(minute=index),
        )
        for index in range(7)
    ]
    context = bounded_thread_context(messages, current_message_id="message-6")

    assert [item.message_id for item in context] == [
        "message-1",
        "message-2",
        "message-3",
        "message-4",
        "message-5",
    ]
    assert all(len(item.body) == 4_000 for item in context)


def test_client_constraints_are_typed_without_becoming_commerce_results():
    deadline = ClientConstraint(
        kind="REQUESTED_DEADLINE",
        value_text="1 October 2026",
        normalized_date="2026-10-01",
    )
    budget = ClientConstraint(
        kind="BUDGET_LIMIT",
        value_text="$5,000 USD",
        amount="5000.00",
        currency="USD",
    )

    assert deadline.normalized_date.isoformat() == "2026-10-01"
    assert str(budget.amount) == "5000.00"
    with pytest.raises(ValidationError):
        ClientConstraint(
            kind="REQUESTED_DEADLINE",
            value_text="October",
            amount="1",
            currency="USD",
        )


def _scope_event(index: int) -> ScopeEventProposal:
    return ScopeEventProposal(
        classification=ScopeEventClassification.CLARIFICATION,
        description=f"Clarification {index}",
        rationale="Existing work detail",
        evidence=[],
        confidence=90,
    )


def test_scope_analysis_accepts_zero_to_ten_unique_events_and_rejects_more():
    assert ScopeAnalysis(
        events=[], conversation_closure=False, overall_confidence=100
    ).events == []
    assert len(
        ScopeAnalysis(
            events=[_scope_event(index) for index in range(10)],
            conversation_closure=False,
            overall_confidence=90,
        ).events
    ) == 10
    with pytest.raises(ValidationError):
        ScopeAnalysis(
            events=[_scope_event(index) for index in range(11)],
            conversation_closure=False,
            overall_confidence=90,
        )
    with pytest.raises(ValidationError, match="duplicate atomic events"):
        ScopeAnalysis(
            events=[_scope_event(1), _scope_event(1)],
            conversation_closure=False,
            overall_confidence=90,
        )


def test_scope_analysis_keeps_event_limit_out_of_vertex_response_schema():
    """Vertex rejects nested maxItems even though application validation supports it."""

    events_schema = ScopeAnalysis.model_json_schema()["properties"]["events"]

    assert "maxItems" not in events_schema


def test_scope_analysis_allows_replacement_with_clarification_and_closure_changes():
    replacement = ScopeEventProposal(
        classification=ScopeEventClassification.REPLACEMENT,
        description="Replace email notifications with LINE notifications.",
        sop_module_keys=["email_notifications", "line_notifications"],
        quantities=[{"module_key": "line_notifications", "quantity": 1}],
        rationale="One baseline module is replaced by one catalog module.",
        evidence=[],
        confidence=95,
    )
    clarification = _scope_event(1)
    closure = ScopeEventProposal(
        classification=ScopeEventClassification.CLOSURE,
        description="That is everything.",
        rationale="Explicit closure.",
        evidence=[],
        confidence=95,
    )

    replacement_mix = ScopeAnalysis(
        events=[replacement, clarification],
        conversation_closure=False,
        overall_confidence=95,
    )
    closure_mix = ScopeAnalysis(
        events=[closure, replacement, _scope_event(2)],
        conversation_closure=True,
        overall_confidence=95,
    )

    assert [item.classification for item in replacement_mix.events] == [
        ScopeEventClassification.REPLACEMENT,
        ScopeEventClassification.CLARIFICATION,
    ]
    assert closure_mix.conversation_closure is True


def test_semantic_sop_projection_contains_no_commerce_rules():
    semantic = load_sop("config/jvl_sop.example.yaml").semantic_view()
    serialized = str(semantic).casefold()

    assert "amount_usd" not in serialized
    assert "timeline" not in serialized
    assert "base_days" not in serialized
    assert set(semantic) == {"version", "modules"}
    assert all(
        set(module)
        == {
            "key",
            "aliases",
            "inclusions",
            "exclusions",
            "dependencies",
            "materiality",
            "quantity_policy",
        }
        for module in semantic["modules"]
    )
    assert all(
        module["quantity_policy"]["maximum"] == 1
        for module in semantic["modules"]
    )


def test_router_uses_message_and_thread_indexes_without_model_routing():
    repository = InMemoryApplicationRepository(clock=lambda: NOW)
    router = InboundMessageRouter(repository)
    email = InboundEmail(
        message_id="message-1",
        thread_id="thread-1",
        sender_name="Client",
        sender_email="client@example.com",
        subject="Project",
        body="Please automate our inbox.",
        received_at=NOW,
    )
    assert router.route(email).route == AgentRoute.REQUIREMENT_ANALYSIS

    project = ProjectRecord(
        id="project-1",
        client_name="Client",
        client_email="client@example.com",
        gmail_thread_id="thread-1",
        title="Project",
        lifecycle_status=ProjectLifecycleStatus.NEEDS_CLARIFICATION,
        correlation_id="corr-1",
        created_at=NOW,
        updated_at=NOW,
    )
    ModelStore(repository).create(
        CollectionName.PROJECTS,
        project,
        unique_keys={"gmail_thread_id": IdempotencyKeys.gmail_thread("thread-1")},
    )
    assert router.route(email).route == AgentRoute.REQUIREMENT_ANALYSIS

    stored = repository.get(collection="projects", document_id="project-1")
    active = project.model_copy(update={"active_scope_version_id": "scope-1"})
    repository.compare_and_set(
        collection="projects",
        document_id="project-1",
        expected_revision=stored.revision,
        payload=active.model_dump(mode="json"),
    )
    assert router.route(email).route == AgentRoute.SCOPE_ANALYSIS


def test_router_ignores_outbound_and_automated_messages():
    repository = InMemoryApplicationRepository(clock=lambda: NOW)
    router = InboundMessageRouter(repository)
    for direction in (EmailDirection.OUTBOUND, EmailDirection.AUTOMATED):
        decision = router.route(
            InboundEmail(
                message_id=f"message-{direction.value}",
                thread_id="thread-1",
                sender_name="System",
                sender_email="demo@example.com",
                subject="Notice",
                body="System message",
                received_at=NOW,
                direction=direction,
            )
        )
        assert decision.route == AgentRoute.IGNORE

from datetime import datetime, timezone

import pytest

from scopelock.domain.workflow_models import AuditRecord
from scopelock.observability import persistence_event_fields, structured_event_payload
from scopelock.repositories.in_memory import InMemoryApplicationRepository
from scopelock.repositories.model_store import CollectionName, ModelStore


NOW = datetime(2026, 8, 30, tzinfo=timezone.utc)


def _audit_record() -> AuditRecord:
    return AuditRecord(
        id="audit-1",
        record_type="GMAIL_COMMERCIAL_ACTION",
        entity_id="artifact-1",
        action="SEND_COMPLETED",
        actor="application",
        correlation_id="corr-1",
        payload={"email_body": "never log this", "operator_key": "never-log"},
        created_at=NOW,
    )


def test_structured_event_payload_rejects_unapproved_or_secret_like_fields():
    payload = structured_event_payload(
        "http.request.completed",
        request_id="request-1",
        status_code=200,
    )

    assert payload == {
        "event": "http.request.completed",
        "severity": "INFO",
        "request_id": "request-1",
        "status_code": 200,
    }

    with pytest.raises(ValueError, match="not allowed"):
        structured_event_payload("http.request.completed", authorization="secret")


def test_persistence_event_fields_excludes_audit_payload():
    fields = persistence_event_fields("audit_records", _audit_record())

    assert fields == {
        "collection": "audit_records",
        "record_id": "audit-1",
        "entity_id": "artifact-1",
        "action": "SEND_COMPLETED",
        "correlation_id": "corr-1",
    }
    assert "payload" not in fields
    assert "email_body" not in fields
    assert "operator_key" not in fields


def test_model_store_emits_safe_persistence_references_only(monkeypatch):
    events: list[tuple[str, dict[str, object]]] = []

    monkeypatch.setattr(
        "scopelock.repositories.model_store.emit_structured_event",
        lambda event, **fields: events.append((event, fields)),
    )
    store = ModelStore(InMemoryApplicationRepository(clock=lambda: NOW))

    store.create(CollectionName.AUDIT_RECORDS, _audit_record())

    assert events == [
        (
            "persistence.create_or_get",
            {
                "collection": "audit_records",
                "record_id": "audit-1",
                "entity_id": "artifact-1",
                "action": "SEND_COMPLETED",
                "correlation_id": "corr-1",
            },
        )
    ]

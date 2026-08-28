from datetime import datetime, timezone

import pytest

from scopelock.repositories.contracts import (
    DocumentConflictError,
    ImmutableDocumentError,
)
from scopelock.repositories.firestore import FirestoreApplicationRepository


NOW = datetime(2026, 8, 28, tzinfo=timezone.utc)


class FakeSnapshot:
    def __init__(self, payload=None):
        self._payload = payload
        self.exists = payload is not None

    def to_dict(self):
        return self._payload


class FakeDocumentReference:
    def __init__(self, client, collection, document_id):
        self._client = client
        self._identity = (collection, document_id)

    def get(self, transaction=None, timeout=None):
        return FakeSnapshot(self._client.storage.get(self._identity))


class FakeCollectionReference:
    def __init__(self, client, name):
        self._client = client
        self._name = name

    def document(self, document_id):
        return FakeDocumentReference(self._client, self._name, document_id)

    def stream(self, timeout=None):
        return [
            FakeSnapshot(payload)
            for (collection, _), payload in self._client.storage.items()
            if collection == self._name
        ]


class FakeTransaction:
    def __init__(self, client):
        self._client = client

    def set(self, reference, payload):
        self._client.storage[reference._identity] = payload


class FakeFirestoreClient:
    def __init__(self):
        self.storage = {}

    def collection(self, name):
        return FakeCollectionReference(self, name)

    def transaction(self, max_attempts=5):
        return FakeTransaction(self)


def repository():
    client = FakeFirestoreClient()
    repo = FirestoreApplicationRepository(
        client,
        clock=lambda: NOW,
        transaction_runner=lambda operation, transaction: operation(transaction),
    )
    return client, repo


def test_firestore_adapter_creates_unique_canonical_record_and_lists_it():
    _, repo = repository()
    first = repo.create_or_get(
        collection="scope_events",
        document_id="event-1",
        payload={"classification": "EXPANSION"},
        unique_keys={"gmail_message_id": "message-1"},
    )
    duplicate = repo.create_or_get(
        collection="scope_events",
        document_id="event-duplicate",
        payload={"classification": "EXPANSION", "duplicate": True},
        unique_keys={"gmail_message_id": "message-1"},
    )

    assert duplicate.document_id == first.document_id == "event-1"
    assert repo.get(collection="scope_events", document_id="event-1") == first
    assert repo.list(collection="scope_events") == (first,)


def test_firestore_adapter_compare_and_set_enforces_revision_and_immutability():
    _, repo = repository()
    created = repo.create_or_get(
        collection="scope_versions",
        document_id="scope-1",
        payload={"status": "PROPOSED"},
    )
    accepted = repo.compare_and_set(
        collection="scope_versions",
        document_id="scope-1",
        expected_revision=created.revision,
        payload={"status": "ACCEPTED"},
        make_immutable=True,
    )

    assert accepted.revision == 2
    assert accepted.immutable is True
    with pytest.raises(DocumentConflictError):
        repo.compare_and_set(
            collection="scope_versions",
            document_id="scope-1",
            expected_revision=1,
            payload={"status": "SUPERSEDED"},
        )
    with pytest.raises(ImmutableDocumentError):
        repo.compare_and_set(
            collection="scope_versions",
            document_id="scope-1",
            expected_revision=2,
            payload={"status": "SUPERSEDED"},
        )

"""Thread-safe in-memory repository with Firestore-like CAS semantics."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from threading import RLock
from typing import Any

from scopelock.repositories.contracts import (
    DocumentConflictError,
    DocumentNotFoundError,
    ImmutableDocumentError,
    StoredDocument,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, default=str, separators=(",", ":"), sort_keys=True)


class InMemoryApplicationRepository:
    """Atomic local adapter used by Days 7–10 and deterministic tests.

    Unique indexes map external identities (for example ``gmail_message_id``)
    to one canonical document. ``compare_and_set`` prevents lost updates, and
    immutable documents reject any non-no-op replacement.
    """

    def __init__(self, *, clock=utc_now) -> None:
        self._clock = clock
        self._documents: dict[tuple[str, str], StoredDocument] = {}
        self._unique_indexes: dict[tuple[str, str, str], tuple[str, str]] = {}
        self._lock = RLock()

    def create_or_get(
        self,
        *,
        collection: str,
        document_id: str,
        payload: Mapping[str, Any],
        unique_keys: Mapping[str, str] | None = None,
        immutable: bool = False,
    ) -> StoredDocument:
        normalized_unique = dict(unique_keys or {})
        with self._lock:
            direct = self._documents.get((collection, document_id))
            if direct is not None:
                if _canonical(direct.payload) != _canonical(payload):
                    raise DocumentConflictError(
                        f"{collection}/{document_id} already exists with different data"
                    )
                return direct

            for key_name, key_value in normalized_unique.items():
                canonical_identity = self._unique_indexes.get(
                    (collection, key_name, key_value)
                )
                if canonical_identity is not None:
                    return self._documents[canonical_identity]

            now = self._clock()
            stored = StoredDocument(
                collection=collection,
                document_id=document_id,
                payload=copy.deepcopy(dict(payload)),
                revision=1,
                immutable=immutable,
                unique_keys=normalized_unique,
                created_at=now,
                updated_at=now,
            )
            identity = (collection, document_id)
            self._documents[identity] = stored
            for key_name, key_value in normalized_unique.items():
                self._unique_indexes[(collection, key_name, key_value)] = identity
            return stored

    def get(self, *, collection: str, document_id: str) -> StoredDocument | None:
        with self._lock:
            return self._documents.get((collection, document_id))

    def find_by_unique_key(
        self,
        *,
        collection: str,
        key_name: str,
        key_value: str,
    ) -> StoredDocument | None:
        with self._lock:
            identity = self._unique_indexes.get((collection, key_name, key_value))
            return self._documents.get(identity) if identity is not None else None

    def list(self, *, collection: str) -> tuple[StoredDocument, ...]:
        with self._lock:
            return tuple(
                document
                for (candidate_collection, _), document in sorted(
                    self._documents.items()
                )
                if candidate_collection == collection
            )

    def compare_and_set(
        self,
        *,
        collection: str,
        document_id: str,
        expected_revision: int,
        payload: Mapping[str, Any],
        make_immutable: bool = False,
    ) -> StoredDocument:
        with self._lock:
            identity = (collection, document_id)
            current = self._documents.get(identity)
            if current is None:
                raise DocumentNotFoundError(f"Missing {collection}/{document_id}")
            if current.revision != expected_revision:
                raise DocumentConflictError(
                    f"Expected revision {expected_revision}; found {current.revision}"
                )
            if current.immutable:
                if _canonical(current.payload) == _canonical(payload):
                    return current
                raise ImmutableDocumentError(
                    f"{collection}/{document_id} is immutable"
                )

            updated = StoredDocument(
                collection=collection,
                document_id=document_id,
                payload=copy.deepcopy(dict(payload)),
                revision=current.revision + 1,
                immutable=make_immutable,
                unique_keys=current.unique_keys,
                created_at=current.created_at,
                updated_at=self._clock(),
            )
            self._documents[identity] = updated
            return updated

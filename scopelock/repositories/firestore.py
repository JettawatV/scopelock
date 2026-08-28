"""Transactional Firestore implementation of the application repository contract."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any

from scopelock.repositories.contracts import (
    DocumentConflictError,
    DocumentNotFoundError,
    ImmutableDocumentError,
    StoredDocument,
)


TransactionRunner = Callable[[Callable[[Any], StoredDocument], Any], StoredDocument]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, default=str, separators=(",", ":"), sort_keys=True)


class FirestoreApplicationRepository:
    """Store records and unique indexes atomically using Firestore transactions.

    ``transaction_runner`` is injectable so the exact adapter behavior can be
    tested without credentials. The default uses
    ``google.cloud.firestore_v1.transactional``.
    """

    UNIQUE_COLLECTION = "_scopelock_unique_keys"

    def __init__(
        self,
        client: Any,
        *,
        timeout_seconds: float = 10,
        max_attempts: int = 5,
        clock=utc_now,
        transaction_runner: TransactionRunner | None = None,
    ) -> None:
        self._client = client
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_attempts
        self._clock = clock
        self._transaction_runner = transaction_runner or self._google_transaction_runner

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
        target_ref = self._client.collection(collection).document(document_id)
        unique_refs = [
            (
                key_name,
                key_value,
                self._client.collection(self.UNIQUE_COLLECTION).document(
                    self._unique_document_id(collection, key_name, key_value)
                ),
            )
            for key_name, key_value in normalized_unique.items()
        ]

        def operation(transaction: Any) -> StoredDocument:
            target_snapshot = target_ref.get(
                transaction=transaction, timeout=self._timeout_seconds
            )
            if target_snapshot.exists:
                stored = self._decode(target_snapshot.to_dict())
                if _canonical(stored.payload) != _canonical(payload):
                    raise DocumentConflictError(
                        f"{collection}/{document_id} already exists with different data"
                    )
                return stored

            index_snapshots = [
                (
                    key_name,
                    key_value,
                    ref.get(transaction=transaction, timeout=self._timeout_seconds),
                )
                for key_name, key_value, ref in unique_refs
            ]
            for _, _, snapshot in index_snapshots:
                if snapshot.exists:
                    index_payload = snapshot.to_dict()
                    canonical_ref = self._client.collection(
                        index_payload["collection"]
                    ).document(index_payload["document_id"])
                    canonical_snapshot = canonical_ref.get(
                        transaction=transaction, timeout=self._timeout_seconds
                    )
                    if not canonical_snapshot.exists:
                        raise DocumentConflictError("Unique index points to missing record")
                    return self._decode(canonical_snapshot.to_dict())

            now = self._clock()
            stored = StoredDocument(
                collection=collection,
                document_id=document_id,
                payload=dict(payload),
                revision=1,
                immutable=immutable,
                unique_keys=normalized_unique,
                created_at=now,
                updated_at=now,
            )
            transaction.set(target_ref, self._encode(stored))
            for key_name, key_value, ref in unique_refs:
                transaction.set(
                    ref,
                    {
                        "collection": collection,
                        "document_id": document_id,
                        "key_name": key_name,
                        "key_value": key_value,
                        "created_at": now,
                    },
                )
            return stored

        return self._run_transaction(operation)

    def get(self, *, collection: str, document_id: str) -> StoredDocument | None:
        snapshot = self._client.collection(collection).document(document_id).get(
            timeout=self._timeout_seconds
        )
        return self._decode(snapshot.to_dict()) if snapshot.exists else None

    def list(self, *, collection: str) -> tuple[StoredDocument, ...]:
        documents = (
            self._decode(snapshot.to_dict())
            for snapshot in self._client.collection(collection).stream(
                timeout=self._timeout_seconds
            )
        )
        return tuple(sorted(documents, key=lambda item: item.document_id))

    def compare_and_set(
        self,
        *,
        collection: str,
        document_id: str,
        expected_revision: int,
        payload: Mapping[str, Any],
        make_immutable: bool = False,
    ) -> StoredDocument:
        target_ref = self._client.collection(collection).document(document_id)

        def operation(transaction: Any) -> StoredDocument:
            snapshot = target_ref.get(
                transaction=transaction, timeout=self._timeout_seconds
            )
            if not snapshot.exists:
                raise DocumentNotFoundError(f"Missing {collection}/{document_id}")
            current = self._decode(snapshot.to_dict())
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
                payload=dict(payload),
                revision=current.revision + 1,
                immutable=make_immutable,
                unique_keys=current.unique_keys,
                created_at=current.created_at,
                updated_at=self._clock(),
            )
            transaction.set(target_ref, self._encode(updated))
            return updated

        return self._run_transaction(operation)

    def _run_transaction(
        self, operation: Callable[[Any], StoredDocument]
    ) -> StoredDocument:
        transaction = self._client.transaction(max_attempts=self._max_attempts)
        return self._transaction_runner(operation, transaction)

    @staticmethod
    def _google_transaction_runner(operation, transaction):
        try:
            from google.cloud.firestore_v1 import transactional
        except ImportError as error:  # pragma: no cover - dependency installation guard
            raise RuntimeError(
                "Install google-cloud-firestore to use the Firestore adapter"
            ) from error
        return transactional(operation)(transaction)

    @staticmethod
    def _unique_document_id(collection: str, key_name: str, key_value: str) -> str:
        identity = f"{collection}\x1f{key_name}\x1f{key_value}"
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()

    @staticmethod
    def _encode(document: StoredDocument) -> dict[str, Any]:
        return document.model_dump(mode="python")

    @staticmethod
    def _decode(payload: Mapping[str, Any]) -> StoredDocument:
        return StoredDocument.model_validate(payload)

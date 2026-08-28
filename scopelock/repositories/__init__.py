"""Persistence contracts and local / Firestore implementations."""

from scopelock.repositories.contracts import (
    ApplicationRepository,
    DocumentConflictError,
    DocumentNotFoundError,
    ImmutableDocumentError,
    StoredDocument,
)
from scopelock.repositories.in_memory import InMemoryApplicationRepository
from scopelock.repositories.model_store import CollectionName, ModelStore

__all__ = [
    "ApplicationRepository",
    "DocumentConflictError",
    "DocumentNotFoundError",
    "ImmutableDocumentError",
    "InMemoryApplicationRepository",
    "CollectionName",
    "ModelStore",
    "StoredDocument",
]

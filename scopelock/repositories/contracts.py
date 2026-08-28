"""Cloud-independent repository contracts used by application workflows."""

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Protocol

from pydantic import Field

from scopelock.domain.models import StrictFrozenContractModel


class RepositoryError(RuntimeError):
    pass


class DocumentNotFoundError(RepositoryError):
    pass


class DocumentConflictError(RepositoryError):
    pass


class ImmutableDocumentError(RepositoryError):
    pass


class StoredDocument(StrictFrozenContractModel):
    collection: str
    document_id: str
    payload: dict[str, Any]
    revision: int = Field(ge=1, strict=True)
    immutable: bool
    unique_keys: dict[str, str]
    created_at: datetime
    updated_at: datetime


class ApplicationRepository(Protocol):
    """Atomic repository boundary shared by memory and Firestore adapters."""

    def create_or_get(
        self,
        *,
        collection: str,
        document_id: str,
        payload: Mapping[str, Any],
        unique_keys: Mapping[str, str] | None = None,
        immutable: bool = False,
    ) -> StoredDocument: ...

    def get(self, *, collection: str, document_id: str) -> StoredDocument | None: ...

    def list(self, *, collection: str) -> tuple[StoredDocument, ...]: ...

    def compare_and_set(
        self,
        *,
        collection: str,
        document_id: str,
        expected_revision: int,
        payload: Mapping[str, Any],
        make_immutable: bool = False,
    ) -> StoredDocument: ...

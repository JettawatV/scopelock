"""Typed Pydantic persistence facade over the cloud-independent repository."""

from enum import StrEnum
from typing import TypeVar

from pydantic import BaseModel

from scopelock.repositories.contracts import (
    ApplicationRepository,
    DocumentNotFoundError,
    StoredDocument,
)
from scopelock.observability import emit_structured_event, persistence_event_fields
from scopelock.services.execution_boundaries import WorkflowExecutionBoundaries


ModelT = TypeVar("ModelT", bound=BaseModel)


class CollectionName(StrEnum):
    PROJECTS = "projects"
    INBOUND_MESSAGES = "inbound_messages"
    INBOUND_RESULTS = "inbound_results"
    SCOPE_VERSIONS = "scope_versions"
    SCOPE_EVENTS = "scope_events"
    BUFFERS = "buffers"
    ARTIFACTS = "artifacts"
    AGENT_RUNS = "agent_runs"
    TOOL_ACTIONS = "tool_actions"
    SCOPE_DECISIONS = "scope_decisions"
    STATE_TRANSITIONS = "state_transitions"
    ARTIFACT_EVENTS = "artifact_events"
    AUDIT_RECORDS = "audit_records"
    APPROVALS = "approvals"
    SENDS = "sends"
    GMAIL_WATCHES = "gmail_watches"
    GMAIL_CHECKPOINTS = "gmail_checkpoints"
    PUBSUB_EVENTS = "pubsub_events"
    GMAIL_DRAFTS = "gmail_drafts"
    GMAIL_SEND_RESULTS = "gmail_send_results"
    EVAL_RESULTS = "eval_results"
    WORKFLOW_RESULTS = "workflow_results"
    GOLDEN_PATH_RESULTS = "golden_path_results"


class ModelStore:
    """Remove serialization and CAS bookkeeping from workflow orchestration."""

    def __init__(
        self,
        repository: ApplicationRepository,
        *,
        use_boundaries: bool = False,
    ) -> None:
        self.repository = repository
        self._use_boundaries = use_boundaries

    def _persist(self, operation):
        if self._use_boundaries:
            return WorkflowExecutionBoundaries.persistence(operation)
        return operation()

    def create(
        self,
        collection: CollectionName,
        model: BaseModel,
        *,
        document_id: str | None = None,
        unique_keys: dict[str, str] | None = None,
        immutable: bool = False,
    ) -> StoredDocument:
        resolved_id = document_id or self._model_id(model)
        stored = self._persist(
            lambda: self.repository.create_or_get(
                collection=collection.value,
                document_id=resolved_id,
                payload=model.model_dump(mode="json"),
                unique_keys=unique_keys,
                immutable=immutable,
            )
        )
        emit_structured_event(
            "persistence.create_or_get",
            **persistence_event_fields(collection.value, model),
        )
        return stored

    def get(
        self,
        collection: CollectionName,
        document_id: str,
        model_type: type[ModelT],
    ) -> ModelT | None:
        stored = self._persist(
            lambda: self.repository.get(
                collection=collection.value,
                document_id=document_id,
            )
        )
        return model_type.model_validate(stored.payload) if stored else None

    def get_document(
        self,
        collection: CollectionName,
        document_id: str,
    ) -> StoredDocument | None:
        """Return persistence metadata for workflows that need explicit CAS."""

        return self._persist(
            lambda: self.repository.get(
                collection=collection.value,
                document_id=document_id,
            )
        )

    def find_by_unique_key(
        self,
        collection: CollectionName,
        *,
        key_name: str,
        key_value: str,
        model_type: type[ModelT],
    ) -> ModelT | None:
        stored = self._persist(
            lambda: self.repository.find_by_unique_key(
                collection=collection.value,
                key_name=key_name,
                key_value=key_value,
            )
        )
        return model_type.model_validate(stored.payload) if stored else None

    def require_document(
        self,
        collection: CollectionName,
        document_id: str,
    ) -> StoredDocument:
        stored = self._persist(
            lambda: self.repository.get(
                collection=collection.value,
                document_id=document_id,
            )
        )
        if stored is None:
            raise DocumentNotFoundError(
                f"Missing {collection.value}/{document_id}"
            )
        return stored

    def replace(
        self,
        collection: CollectionName,
        model: BaseModel,
        *,
        make_immutable: bool = False,
        expected_revision: int | None = None,
    ) -> StoredDocument:
        document_id = self._model_id(model)
        current = (
            self.require_document(collection, document_id)
            if expected_revision is None
            else None
        )
        revision = expected_revision if expected_revision is not None else current.revision
        stored = self._persist(
            lambda: self.repository.compare_and_set(
                collection=collection.value,
                document_id=document_id,
                expected_revision=revision,
                payload=model.model_dump(mode="json"),
                make_immutable=make_immutable,
            )
        )
        emit_structured_event(
            "persistence.compare_and_set",
            **persistence_event_fields(collection.value, model),
        )
        return stored

    @staticmethod
    def _model_id(model: BaseModel) -> str:
        model_id = getattr(model, "id", None)
        if not isinstance(model_id, str) or not model_id:
            raise ValueError("Persisted models require a non-empty string id")
        return model_id

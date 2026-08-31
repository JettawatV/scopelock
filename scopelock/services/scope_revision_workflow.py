"""Deterministic Day 13 buffer finalization and canonical-scope acceptance."""

from __future__ import annotations

from datetime import datetime, timezone

from scopelock.domain.enums import (
    ArtifactStatus,
    BufferFinalizationReason,
    EmailDirection,
    ProjectLifecycleStatus,
    ScopeBufferStatus,
    ScopeEventStatus,
    ScopeVersionStatus,
)
from scopelock.domain.models import CommercialArtifact, ScopeVersion
from scopelock.domain.state_machines import transition_artifact, transition_scope_event
from scopelock.domain.workflow_models import (
    AuditRecord,
    InboundMessageRecord,
    ProjectRecord,
    ScopeBufferRecord,
    ScopeEventRecord,
)
from scopelock.repositories.contracts import ApplicationRepository
from scopelock.repositories.model_store import CollectionName, ModelStore
from scopelock.services.commercial_artifact_service import (
    accept_scope_version,
    supersede_scope_version,
)
from scopelock.services.identity import stable_id
from scopelock.services.idempotency_service import IdempotencyKeys
from scopelock.services.scope_buffer_service import BufferArtifactResult, ScopeBufferService
from scopelock.services.sop_service import SOPCatalog
from scopelock.services.workflow_state import advance_project


class ScopeRevisionWorkflow:
    def __init__(
        self,
        *,
        catalog: SOPCatalog,
        repository: ApplicationRepository,
    ) -> None:
        self._repository = repository
        self._store = ModelStore(repository, use_boundaries=True)
        self._buffer_service = ScopeBufferService(catalog)

    def finalize_ready_for_project(
        self, project_id: str, *, finalized_at: datetime
    ) -> BufferArtifactResult | None:
        project = self._require_project(project_id)
        if project.scope_buffer_id is None:
            return None
        buffer = self._require_buffer(project.scope_buffer_id)
        if buffer.status != ScopeBufferStatus.READY_TO_FINALIZE:
            return None
        return self.finalize_buffer(
            buffer.id,
            reason=BufferFinalizationReason.SEMANTIC_CLOSURE,
            finalized_at=finalized_at,
        )

    def finalize_due(self, *, now: datetime) -> tuple[BufferArtifactResult, ...]:
        results: list[BufferArtifactResult] = []
        for document in self._repository.list(collection=CollectionName.BUFFERS.value):
            buffer = ScopeBufferRecord.model_validate(document.payload)
            if (
                buffer.status == ScopeBufferStatus.OPEN
                and buffer.quiet_window_expires_at <= now
            ):
                results.append(
                    self.finalize_buffer(
                        buffer.id,
                        reason=BufferFinalizationReason.QUIET_WINDOW,
                        finalized_at=now,
                    )
                )
        return tuple(results)

    def finalize_buffer(
        self,
        buffer_id: str,
        *,
        reason: BufferFinalizationReason,
        finalized_at: datetime | None = None,
    ) -> BufferArtifactResult:
        at = finalized_at or datetime.now(timezone.utc)
        buffer = self._require_buffer(buffer_id)
        project = self._require_project(buffer.project_id)
        prior_artifact = next(
            (
                artifact
                for artifact in self._project_models(
                    CollectionName.ARTIFACTS, CommercialArtifact, project.id
                )
                if artifact.source_buffer_id == buffer.id
            ),
            None,
        )
        if prior_artifact is not None:
            prior_scope = self._store.get(
                CollectionName.SCOPE_VERSIONS,
                prior_artifact.proposed_scope_version_id,
                ScopeVersion,
            )
            if prior_scope is None:
                raise KeyError(
                    f"Artifact {prior_artifact.id} has no proposed scope"
                )
            return BufferArtifactResult(
                buffer=buffer,
                proposed_scope=prior_scope,
                artifact=prior_artifact,
            )
        baseline = self._store.get(
            CollectionName.SCOPE_VERSIONS,
            buffer.baseline_scope_version_id,
            ScopeVersion,
        )
        if baseline is None:
            raise KeyError(f"Missing baseline {buffer.baseline_scope_version_id}")
        finalized = self._buffer_service.finalize(buffer, reason=reason, finalized_at=at)
        if finalized != buffer:
            self._store.replace(CollectionName.BUFFERS, finalized)

        existing_scopes = self._project_models(
            CollectionName.SCOPE_VERSIONS, ScopeVersion, project.id
        )
        existing_artifacts = self._project_models(
            CollectionName.ARTIFACTS, CommercialArtifact, project.id
        )
        active_unapproved = (
            self._store.get(
                CollectionName.ARTIFACTS,
                project.active_proposal_id,
                CommercialArtifact,
            )
            if project.active_proposal_id
            else None
        )
        if active_unapproved is not None and active_unapproved.status not in {
            ArtifactStatus.DRAFT,
            ArtifactStatus.AWAITING_USER_REVIEW,
            ArtifactStatus.APPROVED,
        }:
            active_unapproved = None
        result = self._buffer_service.create_artifact(
            buffer=finalized,
            baseline=baseline,
            existing_scopes=existing_scopes,
            existing_artifacts=existing_artifacts,
            active_unapproved_artifact=active_unapproved,
            created_at=at,
        )
        self._store.create(CollectionName.SCOPE_VERSIONS, result.proposed_scope)
        self._store.create(
            CollectionName.ARTIFACTS,
            result.artifact,
            unique_keys={
                "artifact_version": f"{project.id}:{result.artifact.artifact_type.value}:"
                f"{result.artifact.version_number}"
            },
        )
        if result.invalidated_artifact is not None:
            self._store.replace(CollectionName.ARTIFACTS, result.invalidated_artifact)
        self._advance_buffer_events(finalized, ScopeEventStatus.AWAITING_USER_REVIEW)

        updates: dict[str, object] = {
            "active_proposal_id": result.artifact.id,
            "scope_buffer_id": None,
            "updated_at": at,
        }
        if baseline.status == ScopeVersionStatus.PROPOSED:
            updates.update(
                {
                    "active_scope_version_id": result.proposed_scope.id,
                    "current_price_usd": result.proposed_scope.total_price_usd,
                    "current_timeline_days": result.proposed_scope.timeline_days,
                }
            )
        project = project.model_copy(update=updates)
        if project.lifecycle_status in {
            ProjectLifecycleStatus.ACTIVE_PROJECT,
            ProjectLifecycleStatus.NEGOTIATING,
        }:
            project, transition = advance_project(
                project,
                ProjectLifecycleStatus.AWAITING_USER_REVIEW,
                reason=f"scope buffer finalized by {reason.value}",
                at=at,
            )
            self._store.create(CollectionName.STATE_TRANSITIONS, transition)
        self._store.replace(CollectionName.PROJECTS, project)
        self._audit(
            project.id,
            "SCOPE_BUFFER_FINALIZED",
            result.artifact.id,
            result.artifact.checksum,
            at,
            buffer.correlation_id,
        )
        return result

    def accept_sent_artifact(
        self,
        artifact_id: str,
        *,
        acceptance_message_id: str,
        correlation_id: str,
        accepted_at: datetime | None = None,
    ) -> tuple[CommercialArtifact, ScopeVersion, ProjectRecord]:
        at = accepted_at or datetime.now(timezone.utc)
        artifact = self._store.get(
            CollectionName.ARTIFACTS, artifact_id, CommercialArtifact
        )
        if artifact is None:
            raise KeyError(f"Unknown artifact {artifact_id}")
        if artifact.status == ArtifactStatus.ACCEPTED:
            scope = self._store.get(
                CollectionName.SCOPE_VERSIONS,
                artifact.proposed_scope_version_id,
                ScopeVersion,
            )
            if scope is None:
                raise KeyError("Accepted artifact has no scope")
            return artifact, scope, self._require_project(artifact.project_id)
        if artifact.status != ArtifactStatus.SENT:
            raise ValueError("Only a confirmed sent artifact can be accepted")
        project = self._require_project(artifact.project_id)
        acceptance = self._require_acceptance_evidence(
            project, acceptance_message_id=acceptance_message_id
        )
        accepted_by = acceptance.email.sender_email
        proposed = self._store.get(
            CollectionName.SCOPE_VERSIONS,
            artifact.proposed_scope_version_id,
            ScopeVersion,
        )
        if proposed is None:
            raise KeyError("Artifact proposed scope is missing")
        accepted_scope = accept_scope_version(proposed)
        accepted_artifact = artifact.model_copy(
            update={
                "status": transition_artifact(
                    artifact.status, ArtifactStatus.ACCEPTED
                )
            }
        )
        if project.baseline_scope_version_id:
            previous = self._store.get(
                CollectionName.SCOPE_VERSIONS,
                project.baseline_scope_version_id,
                ScopeVersion,
            )
            if previous is not None and previous.id != accepted_scope.id:
                self._store.replace(
                    CollectionName.SCOPE_VERSIONS, supersede_scope_version(previous)
                )
        self._store.replace(CollectionName.SCOPE_VERSIONS, accepted_scope)
        self._store.replace(CollectionName.ARTIFACTS, accepted_artifact)
        project = project.model_copy(
            update={
                "baseline_scope_version_id": accepted_scope.id,
                "active_scope_version_id": accepted_scope.id,
                "active_proposal_id": accepted_artifact.id,
                "current_price_usd": accepted_scope.total_price_usd,
                "current_timeline_days": accepted_scope.timeline_days,
                "updated_at": at,
            }
        )
        if project.lifecycle_status == ProjectLifecycleStatus.AWAITING_USER_REVIEW:
            project, transition = advance_project(
                project,
                ProjectLifecycleStatus.ACTIVE_PROJECT,
                reason="client acceptance confirmed",
                at=at,
            )
            self._store.create(CollectionName.STATE_TRANSITIONS, transition)
        self._store.replace(CollectionName.PROJECTS, project)
        if artifact.source_buffer_id:
            buffer = self._require_buffer(artifact.source_buffer_id)
            self._advance_buffer_events(buffer, ScopeEventStatus.APPLIED)
        self._audit(
            project.id,
            "COMMERCIAL_ARTIFACT_ACCEPTED",
            artifact.id,
            artifact.checksum,
            at,
            correlation_id,
            extra={
                "accepted_by": accepted_by,
                "acceptance_message_id": acceptance_message_id,
                "scope_version_id": accepted_scope.id,
            },
        )
        return accepted_artifact, accepted_scope, project

    def accept_sent_artifact_from_record(
        self,
        artifact_id: str,
        *,
        inbound_message_record_id: str,
        correlation_id: str,
        accepted_at: datetime | None = None,
    ) -> tuple[CommercialArtifact, ScopeVersion, ProjectRecord]:
        """Resolve safe dashboard metadata to server-side Gmail evidence."""

        record = self._store.get(
            CollectionName.INBOUND_MESSAGES,
            inbound_message_record_id,
            InboundMessageRecord,
        )
        if record is None:
            raise KeyError(f"Unknown inbound message {inbound_message_record_id}")
        return self.accept_sent_artifact(
            artifact_id,
            acceptance_message_id=record.email.message_id,
            correlation_id=correlation_id,
            accepted_at=accepted_at,
        )

    def _require_acceptance_evidence(
        self,
        project: ProjectRecord,
        *,
        acceptance_message_id: str,
    ) -> InboundMessageRecord:
        record = self._store.find_by_unique_key(
            CollectionName.INBOUND_MESSAGES,
            key_name="gmail_message_id",
            key_value=IdempotencyKeys.gmail_message(acceptance_message_id),
            model_type=InboundMessageRecord,
        )
        if record is None:
            raise ValueError("Client acceptance requires a persisted Gmail message")
        email = record.email
        if (
            email.message_id != acceptance_message_id
            or email.direction != EmailDirection.INBOUND
            or email.thread_id != project.gmail_thread_id
            or email.sender_email.casefold() != project.client_email.casefold()
        ):
            raise ValueError(
                "Client acceptance message is not bound to the project client and thread"
            )
        return record

    def _advance_buffer_events(
        self, buffer: ScopeBufferRecord, target: ScopeEventStatus
    ) -> None:
        path = (
            ScopeEventStatus.CONSOLIDATED,
            ScopeEventStatus.AWAITING_USER_REVIEW,
            ScopeEventStatus.APPROVED,
            ScopeEventStatus.SENT,
            ScopeEventStatus.CLIENT_ACCEPTED,
            ScopeEventStatus.APPLIED,
        )
        for event_id in buffer.event_ids:
            event = self._store.get(
                CollectionName.SCOPE_EVENTS, event_id, ScopeEventRecord
            )
            if event is None or event.status == target:
                continue
            status = event.status
            for candidate in path:
                if status == target:
                    break
                try:
                    status = transition_scope_event(status, candidate)
                except ValueError:
                    continue
            if status != target:
                raise ValueError(
                    f"Cannot advance scope event {event.id} from {event.status} to {target}"
                )
            self._store.replace(
                CollectionName.SCOPE_EVENTS, event.model_copy(update={"status": status})
            )

    def _project_models(self, collection, model_type, project_id: str):
        return tuple(
            model_type.model_validate(document.payload)
            for document in self._repository.list(collection=collection.value)
            if str(document.payload.get("project_id")) == project_id
        )

    def _require_project(self, project_id: str) -> ProjectRecord:
        project = self._store.get(
            CollectionName.PROJECTS, project_id, ProjectRecord
        )
        if project is None:
            raise KeyError(f"Unknown project {project_id}")
        return project

    def _require_buffer(self, buffer_id: str) -> ScopeBufferRecord:
        buffer = self._store.get(
            CollectionName.BUFFERS, buffer_id, ScopeBufferRecord
        )
        if buffer is None:
            raise KeyError(f"Unknown scope buffer {buffer_id}")
        return buffer

    def _audit(
        self,
        project_id: str,
        action: str,
        artifact_id: str,
        checksum: str | None,
        at: datetime,
        correlation_id: str,
        *,
        extra: dict[str, object] | None = None,
    ) -> None:
        payload: dict[str, object] = {
            "artifact_id": artifact_id,
            "artifact_checksum": checksum,
        }
        payload.update(extra or {})
        audit = AuditRecord(
            id=stable_id("audit", project_id, action, correlation_id),
            record_type="SCOPE_REVISION",
            entity_id=project_id,
            action=action,
            actor="application",
            correlation_id=correlation_id,
            payload=payload,
            created_at=at,
        )
        self._store.create(CollectionName.AUDIT_RECORDS, audit)

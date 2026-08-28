"""Complete Day 9 fixture-driven golden-path rehearsal with no UI dependency."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from time import perf_counter

from pydantic import BaseModel

from scopelock.domain.enums import (
    ApprovalStatus,
    ArtifactStatus,
    BufferFinalizationReason,
    ProjectLifecycleStatus,
    ScopeEventClassification,
    ScopeEventStatus,
)
from scopelock.domain.models import (
    ApprovalRecord,
    EvidenceRef,
    ModuleQuantity,
    RequirementAnalysis,
    ScopeVersion,
    SendIntent,
)
from scopelock.domain.state_machines import (
    transition_artifact,
    transition_project,
    transition_scope_event,
)
from scopelock.domain.workflow_models import (
    InboundEmail,
    LocalGoldenPathResult,
    ProjectRecord,
    ScopeDecisionRecord,
    ScopeEventRecord,
    StateTransitionRecord,
)
from scopelock.repositories.contracts import ApplicationRepository
from scopelock.services.approval_policy import InMemorySendStub, decide_artifact
from scopelock.services.commercial_artifact_service import accept_scope_version
from scopelock.services.initial_proposal_workflow import (
    InitialProposalWorkflow,
    stable_id,
)
from scopelock.services.scope_buffer_service import ScopeBufferService
from scopelock.services.sop_service import SOPCatalog


class GoldenPathRehearsal:
    """Rehearse proposal -> acceptance -> scope drift -> approved change order."""

    def __init__(
        self,
        *,
        catalog: SOPCatalog,
        repository: ApplicationRepository,
        artifact_root: str | Path,
        operator_id: str = "demo-operator@example.com",
    ) -> None:
        self._catalog = catalog
        self._repository = repository
        self._artifact_root = artifact_root
        self._operator_id = operator_id
        self._send_stub = InMemorySendStub()

    def run(
        self,
        *,
        email: InboundEmail,
        analysis: RequirementAnalysis,
        followups: dict,
    ) -> LocalGoldenPathResult:
        rehearsal_id = stable_id("rehearsal", email.message_id)
        prior = self._repository.get(
            collection="golden_path_results", document_id=rehearsal_id
        )
        if prior is not None:
            return LocalGoldenPathResult.model_validate(prior.payload)
        started = perf_counter()
        initial = InitialProposalWorkflow(
            catalog=self._catalog,
            repository=self._repository,
            analyzer=lambda _: analysis,
            artifact_root=self._artifact_root,
        ).run(email)
        now = email.received_at

        initial_approved, first_approval = decide_artifact(
            initial.artifact,
            decision=ApprovalStatus.APPROVED,
            approver_id=self._operator_id,
            correlation_id=initial.correlation_id,
            decided_at=now + timedelta(seconds=1),
        )
        self._replace("artifacts", initial_approved)
        self._create(
            "approvals",
            first_approval,
            unique_keys={
                "artifact_approval": (
                    f"{first_approval.artifact_id}:{first_approval.artifact_checksum}"
                )
            },
            immutable=True,
        )
        first_send = self._send_stub.request_send(
            initial_approved,
            first_approval,
            gmail_thread_id=email.thread_id,
            correlation_id=initial.correlation_id,
            created_at=now + timedelta(seconds=2),
        )
        self._create(
            "sends",
            first_send,
            unique_keys={"send_action": first_send.idempotency_key},
            immutable=True,
        )
        initial_sent = self._advance_artifact(
            initial_approved, ArtifactStatus.SENDING, ArtifactStatus.SENT
        )
        initial_accepted = initial_sent.model_copy(
            update={
                "status": transition_artifact(
                    initial_sent.status, ArtifactStatus.ACCEPTED
                )
            }
        )
        self._replace("artifacts", initial_accepted)

        baseline_doc = self._repository.get(
            collection="scope_versions", document_id=initial.scope_version_id
        )
        assert baseline_doc is not None
        accepted_baseline = accept_scope_version(
            ScopeVersion.model_validate(baseline_doc.payload)
        )
        self._repository.compare_and_set(
            collection="scope_versions",
            document_id=accepted_baseline.id,
            expected_revision=baseline_doc.revision,
            payload=accepted_baseline.model_dump(mode="json"),
            make_immutable=True,
        )

        project = initial.project
        for target, reason in (
            (ProjectLifecycleStatus.PROPOSAL_SENT, "approved proposal send intent"),
            (ProjectLifecycleStatus.NEGOTIATING, "proposal delivered to client thread"),
            (ProjectLifecycleStatus.ACCEPTED, "demo fixture accepts proposal"),
            (ProjectLifecycleStatus.ACTIVE_PROJECT, "accepted scope becomes canonical"),
        ):
            project = self._project_transition(project, target, reason, now)
        project = project.model_copy(
            update={
                "baseline_scope_version_id": accepted_baseline.id,
                "active_scope_version_id": accepted_baseline.id,
                "active_proposal_id": initial_accepted.id,
            }
        )
        self._replace("projects", project)

        buffer_service = ScopeBufferService(self._catalog, quiet_window_minutes=20)
        clarification_data = followups["clarification"]
        clarification = ScopeEventRecord(
            id=stable_id("event", clarification_data["message_id"]),
            project_id=project.id,
            gmail_message_id=clarification_data["message_id"],
            baseline_scope_version_id=accepted_baseline.id,
            classification=ScopeEventClassification.NO_CHANGE,
            status=ScopeEventStatus.CLASSIFIED,
            description=clarification_data["text"],
            evidence=(
                EvidenceRef(
                    source_type="gmail",
                    source_id=clarification_data["message_id"],
                    quote_or_rule=clarification_data["text"],
                ),
                EvidenceRef(
                    source_type="scope_version",
                    source_id=accepted_baseline.id,
                    quote_or_rule="Operations dashboard naming is presentation-only.",
                ),
            ),
            correlation_id=stable_id("corr", clarification_data["message_id"]),
            created_at=now + timedelta(minutes=1),
        )
        clarification = buffer_service.record_non_material(clarification)
        self._record_event_and_decision(
            clarification, rationale="Dashboard title does not change implementation work"
        )

        expansion_data = followups["expansion"]
        expansion = ScopeEventRecord(
            id=stable_id("event", expansion_data["message_id"]),
            project_id=project.id,
            gmail_message_id=expansion_data["message_id"],
            baseline_scope_version_id=accepted_baseline.id,
            classification=ScopeEventClassification.EXPANSION,
            status=ScopeEventStatus.CLASSIFIED,
            description=expansion_data["text"],
            additions=(
                ModuleQuantity(module_key="line_notifications", quantity=1),
                ModuleQuantity(module_key="line_approval", quantity=1),
            ),
            evidence=(
                EvidenceRef(
                    source_type="gmail",
                    source_id=expansion_data["message_id"],
                    quote_or_rule=expansion_data["text"],
                ),
                EvidenceRef(
                    source_type="scope_version",
                    source_id=accepted_baseline.id,
                    quote_or_rule="Accepted integrations include Gmail and email only.",
                ),
                EvidenceRef(
                    source_type="sop",
                    source_id="line_notifications",
                    quote_or_rule="LINE notifications are a separate material module.",
                ),
                EvidenceRef(
                    source_type="sop",
                    source_id="line_approval",
                    quote_or_rule="LINE approval is a separate material module.",
                ),
            ),
            correlation_id=stable_id("corr", expansion_data["message_id"]),
            created_at=now + timedelta(minutes=2),
        )
        expansion, buffer = buffer_service.buffer_event(
            baseline=accepted_baseline, event=expansion
        )
        self._record_event_and_decision(
            expansion,
            rationale="LINE alerts and manager approvals add two SOP modules",
        )
        self._create(
            "buffers",
            buffer,
            unique_keys={"baseline_open_buffer": accepted_baseline.id},
        )

        closure_data = followups["closure"]
        closure = ScopeEventRecord(
            id=stable_id("event", closure_data["message_id"]),
            project_id=project.id,
            gmail_message_id=closure_data["message_id"],
            baseline_scope_version_id=accepted_baseline.id,
            classification=ScopeEventClassification.CLOSURE,
            status=ScopeEventStatus.CLASSIFIED,
            description=closure_data["text"],
            evidence=(
                EvidenceRef(
                    source_type="gmail",
                    source_id=closure_data["message_id"],
                    quote_or_rule=closure_data["text"],
                ),
            ),
            correlation_id=stable_id("corr", closure_data["message_id"]),
            created_at=now + timedelta(minutes=3),
        )
        closure = buffer_service.record_non_material(closure)
        self._record_event_and_decision(
            closure,
            rationale="Explicit request for revised proposal finalizes the buffer",
        )
        finalized = buffer_service.finalize(
            buffer_service.mark_ready_on_closure(buffer),
            reason=BufferFinalizationReason.SEMANTIC_CLOSURE,
            finalized_at=closure.created_at,
        )
        self._replace("buffers", finalized)

        change = buffer_service.create_artifact(
            buffer=finalized,
            baseline=accepted_baseline,
            existing_scopes=(accepted_baseline,),
            existing_artifacts=(initial_accepted,),
            created_at=closure.created_at,
        )
        expansion = expansion.model_copy(
            update={
                "status": transition_scope_event(
                    transition_scope_event(
                        expansion.status, ScopeEventStatus.CONSOLIDATED
                    ),
                    ScopeEventStatus.AWAITING_USER_REVIEW,
                )
            }
        )
        self._replace("scope_events", expansion)
        self._create(
            "scope_versions",
            change.proposed_scope,
            unique_keys={
                "artifact_version": f"{project.id}:scope:{change.proposed_scope.version_number}"
            },
        )
        self._create(
            "artifacts",
            change.artifact,
            unique_keys={"artifact_version": f"{project.id}:change-order:1"},
        )
        project = self._project_transition(
            project,
            ProjectLifecycleStatus.AWAITING_USER_REVIEW,
            "change order generated from consolidated buffer",
            closure.created_at,
        ).model_copy(update={"active_proposal_id": change.artifact.id})
        self._replace("projects", project)

        change_approved, second_approval = decide_artifact(
            change.artifact,
            decision=ApprovalStatus.APPROVED,
            approver_id=self._operator_id,
            correlation_id=change.artifact.id,
            decided_at=closure.created_at + timedelta(seconds=1),
        )
        self._replace("artifacts", change_approved)
        self._create(
            "approvals",
            second_approval,
            unique_keys={
                "artifact_approval": (
                    f"{second_approval.artifact_id}:{second_approval.artifact_checksum}"
                )
            },
            immutable=True,
        )
        second_send = self._send_stub.request_send(
            change_approved,
            second_approval,
            gmail_thread_id=email.thread_id,
            correlation_id=change.artifact.id,
            created_at=closure.created_at + timedelta(seconds=2),
        )
        self._create(
            "sends",
            second_send,
            unique_keys={"send_action": second_send.idempotency_key},
            immutable=True,
        )
        change_sent = self._advance_artifact(
            change_approved, ArtifactStatus.SENDING, ArtifactStatus.SENT
        )
        self._replace("artifacts", change_sent)
        expansion = expansion.model_copy(
            update={
                "status": transition_scope_event(
                    transition_scope_event(
                        expansion.status, ScopeEventStatus.APPROVED
                    ),
                    ScopeEventStatus.SENT,
                )
            }
        )
        self._replace("scope_events", expansion)
        project = self._project_transition(
            project,
            ProjectLifecycleStatus.ACTIVE_PROJECT,
            "approved change order send intent created",
            closure.created_at + timedelta(seconds=2),
        )
        self._replace("projects", project)

        elapsed = perf_counter() - started
        result = LocalGoldenPathResult(
            demo_mode="post_acceptance_change_order",
            initial=initial,
            final_project=project,
            accepted_baseline=accepted_baseline,
            scope_events=(clarification, expansion, closure),
            finalized_buffer=finalized,
            proposed_change_scope=change.proposed_scope,
            artifacts=(initial_accepted, change_sent),
            approvals=(first_approval, second_approval),
            send_intents=(first_send, second_send),
            elapsed_seconds=elapsed,
        )
        self._repository.create_or_get(
            collection="golden_path_results",
            document_id=rehearsal_id,
            payload=result.model_dump(mode="json"),
            unique_keys={"fixture_message_id": email.message_id},
            immutable=True,
        )
        return result

    def _record_event_and_decision(
        self, event: ScopeEventRecord, *, rationale: str
    ) -> None:
        self._create(
            "scope_events",
            event,
            unique_keys={"gmail_message_id": event.gmail_message_id},
        )
        decision = ScopeDecisionRecord(
            id=stable_id("decision", event.id),
            project_id=event.project_id,
            gmail_message_id=event.gmail_message_id,
            decision_type=event.classification.value,
            selected_module_keys=tuple(
                item.module_key for item in event.additions
            ),
            rationale=rationale,
            evidence=event.evidence,
            correlation_id=event.correlation_id,
            created_at=event.created_at,
        )
        self._create(
            "scope_decisions",
            decision,
            unique_keys={"gmail_message_id": event.gmail_message_id},
        )

    def _project_transition(
        self,
        project: ProjectRecord,
        target: ProjectLifecycleStatus,
        reason: str,
        at,
    ) -> ProjectRecord:
        source = project.lifecycle_status
        transition_project(source, target)
        transition = StateTransitionRecord(
            id=stable_id("transition", project.id, source.value, target.value, reason),
            entity_type="project",
            entity_id=project.id,
            from_status=source.value,
            to_status=target.value,
            reason=reason,
            correlation_id=project.correlation_id,
            created_at=at,
        )
        self._create("state_transitions", transition)
        return project.model_copy(
            update={"lifecycle_status": target, "updated_at": at}
        )

    @staticmethod
    def _advance_artifact(artifact, *targets):
        current = artifact
        for target in targets:
            current = current.model_copy(
                update={
                    "status": transition_artifact(current.status, target)
                }
            )
        return current

    def _create(
        self,
        collection: str,
        model: BaseModel,
        *,
        unique_keys: dict[str, str] | None = None,
        immutable: bool = False,
    ) -> None:
        self._repository.create_or_get(
            collection=collection,
            document_id=model.id,
            payload=model.model_dump(mode="json"),
            unique_keys=unique_keys,
            immutable=immutable,
        )

    def _replace(self, collection: str, model: BaseModel) -> None:
        current = self._repository.get(collection=collection, document_id=model.id)
        assert current is not None
        self._repository.compare_and_set(
            collection=collection,
            document_id=model.id,
            expected_revision=current.revision,
            payload=model.model_dump(mode="json"),
        )

"""Complete Day 9 fixture-driven golden-path rehearsal with no UI dependency."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from time import perf_counter

from scopelock.domain.enums import (
    ApprovalStatus,
    ArtifactStatus,
    BufferFinalizationReason,
    ProjectLifecycleStatus,
    ScopeEventStatus,
)
from scopelock.domain.models import (
    ApprovalRecord,
    CommercialArtifact,
    RequirementAnalysis,
    ScopeVersion,
    SendIntent,
)
from scopelock.domain.workflow_models import (
    InboundEmail,
    LocalGoldenPathResult,
    LocalInitialProposalResult,
    ProjectRecord,
    ScopeBufferRecord,
    ScopeDecisionRecord,
    ScopeEventRecord,
)
from scopelock.repositories.contracts import ApplicationRepository
from scopelock.repositories.model_store import CollectionName, ModelStore
from scopelock.services.approval_policy import InMemorySendStub, decide_artifact
from scopelock.services.commercial_artifact_service import accept_scope_version
from scopelock.services.initial_proposal_workflow import (
    InitialProposalWorkflow,
)
from scopelock.services.identity import stable_id
from scopelock.services.idempotency_service import IdempotencyKeys
from scopelock.services.golden_path_scenario import (
    FollowupPayload,
    GoldenPathScenarioBuilder,
)
from scopelock.services.scope_buffer_service import ScopeBufferService
from scopelock.services.sop_service import SOPCatalog
from scopelock.services.workflow_state import (
    advance_artifact,
    advance_project,
    advance_scope_event,
)


@dataclass(frozen=True)
class _AcceptedInitialStage:
    project: ProjectRecord
    baseline: ScopeVersion
    artifact: CommercialArtifact
    approval: ApprovalRecord
    send_intent: SendIntent


@dataclass(frozen=True)
class _FollowupStage:
    clarification: ScopeEventRecord
    expansion: ScopeEventRecord
    closure: ScopeEventRecord
    finalized_buffer: ScopeBufferRecord


@dataclass(frozen=True)
class _ApprovedChangeStage:
    project: ProjectRecord
    expansion: ScopeEventRecord
    proposed_scope: ScopeVersion
    artifact: CommercialArtifact
    approval: ApprovalRecord
    send_intent: SendIntent


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
        self._store = ModelStore(repository)
        self._artifact_root = artifact_root
        self._operator_id = operator_id
        self._send_stub = InMemorySendStub()

    def run(
        self,
        *,
        email: InboundEmail,
        analysis: RequirementAnalysis,
        followups: FollowupPayload,
    ) -> LocalGoldenPathResult:
        rehearsal_id = stable_id("rehearsal", email.message_id)
        prior = self._store.get(
            CollectionName.GOLDEN_PATH_RESULTS,
            rehearsal_id,
            LocalGoldenPathResult,
        )
        if prior is not None:
            return prior
        started = perf_counter()
        initial = InitialProposalWorkflow(
            catalog=self._catalog,
            repository=self._repository,
            analyzer=lambda _: analysis,
            artifact_root=self._artifact_root,
        ).run(email)
        accepted = self._approve_and_accept_initial(initial, email)
        followup_stage = self._process_followups(
            project=accepted.project,
            baseline=accepted.baseline,
            followups=followups,
            started_at=email.received_at,
        )
        changed = self._approve_change_order(
            project=accepted.project,
            baseline=accepted.baseline,
            accepted_artifact=accepted.artifact,
            followups=followup_stage,
            gmail_thread_id=email.thread_id,
        )

        elapsed = perf_counter() - started
        result = LocalGoldenPathResult(
            demo_mode="post_acceptance_change_order",
            initial=initial,
            final_project=changed.project,
            accepted_baseline=accepted.baseline,
            scope_events=(
                followup_stage.clarification,
                changed.expansion,
                followup_stage.closure,
            ),
            finalized_buffer=followup_stage.finalized_buffer,
            proposed_change_scope=changed.proposed_scope,
            artifacts=(accepted.artifact, changed.artifact),
            approvals=(accepted.approval, changed.approval),
            send_intents=(accepted.send_intent, changed.send_intent),
            elapsed_seconds=elapsed,
        )
        self._store.create(
            CollectionName.GOLDEN_PATH_RESULTS,
            result,
            document_id=rehearsal_id,
            unique_keys={
                "fixture_message_id": IdempotencyKeys.gmail_message(email.message_id)
            },
            immutable=True,
        )
        return result

    def _approve_and_accept_initial(
        self,
        initial: LocalInitialProposalResult,
        email: InboundEmail,
    ) -> _AcceptedInitialStage:
        approved, approval = decide_artifact(
            initial.artifact,
            decision=ApprovalStatus.APPROVED,
            approver_id=self._operator_id,
            correlation_id=initial.correlation_id,
            decided_at=email.received_at + timedelta(seconds=1),
        )
        self._store.replace(CollectionName.ARTIFACTS, approved)
        self._persist_approval(approval)
        send_intent = self._send_stub.request_send(
            approved,
            approval,
            gmail_thread_id=email.thread_id,
            correlation_id=initial.correlation_id,
            created_at=email.received_at + timedelta(seconds=2),
        )
        self._persist_send(send_intent)
        accepted_artifact = advance_artifact(
            approved,
            ArtifactStatus.SENDING,
            ArtifactStatus.SENT,
            ArtifactStatus.ACCEPTED,
        )
        self._store.replace(CollectionName.ARTIFACTS, accepted_artifact)

        baseline = self._store.get(
            CollectionName.SCOPE_VERSIONS,
            initial.scope_version_id,
            ScopeVersion,
        )
        if baseline is None:
            raise RuntimeError("Initial workflow did not persist its scope version")
        accepted_baseline = accept_scope_version(baseline)
        self._store.replace(
            CollectionName.SCOPE_VERSIONS,
            accepted_baseline,
            make_immutable=True,
        )

        project = initial.project
        for target, reason in (
            (ProjectLifecycleStatus.PROPOSAL_SENT, "approved proposal send intent"),
            (ProjectLifecycleStatus.NEGOTIATING, "proposal delivered to client thread"),
            (ProjectLifecycleStatus.ACCEPTED, "demo fixture accepts proposal"),
            (ProjectLifecycleStatus.ACTIVE_PROJECT, "accepted scope becomes canonical"),
        ):
            project = self._advance_project(
                project, target, reason, email.received_at
            )
        project = project.model_copy(
            update={
                "baseline_scope_version_id": accepted_baseline.id,
                "active_scope_version_id": accepted_baseline.id,
                "active_proposal_id": accepted_artifact.id,
            }
        )
        self._store.replace(CollectionName.PROJECTS, project)
        return _AcceptedInitialStage(
            project=project,
            baseline=accepted_baseline,
            artifact=accepted_artifact,
            approval=approval,
            send_intent=send_intent,
        )

    def _process_followups(
        self,
        *,
        project: ProjectRecord,
        baseline: ScopeVersion,
        followups: FollowupPayload,
        started_at: datetime,
    ) -> _FollowupStage:
        buffer_service = ScopeBufferService(self._catalog, quiet_window_minutes=20)
        events = GoldenPathScenarioBuilder.build(
            project=project,
            baseline=baseline,
            followups=followups,
            started_at=started_at,
        )
        clarification = buffer_service.record_non_material(
            events.clarification
        )
        self._record_event_and_decision(
            clarification,
            rationale="Dashboard title does not change implementation work",
        )

        expansion, buffer = buffer_service.buffer_event(
            baseline=baseline,
            event=events.expansion,
        )
        self._record_event_and_decision(
            expansion,
            rationale="LINE alerts and manager approvals add two SOP modules",
        )
        self._store.create(
            CollectionName.BUFFERS,
            buffer,
            unique_keys={"baseline_open_buffer": baseline.id},
        )

        closure = buffer_service.record_non_material(
            events.closure
        )
        self._record_event_and_decision(
            closure,
            rationale="Explicit request for revised proposal finalizes the buffer",
        )
        finalized = buffer_service.finalize(
            buffer_service.mark_ready_on_closure(buffer),
            reason=BufferFinalizationReason.SEMANTIC_CLOSURE,
            finalized_at=closure.created_at,
        )
        self._store.replace(CollectionName.BUFFERS, finalized)
        return _FollowupStage(
            clarification=clarification,
            expansion=expansion,
            closure=closure,
            finalized_buffer=finalized,
        )

    def _approve_change_order(
        self,
        *,
        project: ProjectRecord,
        baseline: ScopeVersion,
        accepted_artifact: CommercialArtifact,
        followups: _FollowupStage,
        gmail_thread_id: str,
    ) -> _ApprovedChangeStage:
        buffer_service = ScopeBufferService(self._catalog, quiet_window_minutes=20)
        change = buffer_service.create_artifact(
            buffer=followups.finalized_buffer,
            baseline=baseline,
            existing_scopes=(baseline,),
            existing_artifacts=(accepted_artifact,),
            created_at=followups.closure.created_at,
        )
        expansion = advance_scope_event(
            followups.expansion,
            ScopeEventStatus.CONSOLIDATED,
            ScopeEventStatus.AWAITING_USER_REVIEW,
        )
        self._store.replace(CollectionName.SCOPE_EVENTS, expansion)
        self._store.create(
            CollectionName.SCOPE_VERSIONS,
            change.proposed_scope,
            unique_keys={
                "artifact_version": (
                    f"{project.id}:scope:{change.proposed_scope.version_number}"
                )
            },
        )
        self._store.create(
            CollectionName.ARTIFACTS,
            change.artifact,
            unique_keys={"artifact_version": f"{project.id}:change-order:1"},
        )
        project = self._advance_project(
            project,
            ProjectLifecycleStatus.AWAITING_USER_REVIEW,
            "change order generated from consolidated buffer",
            followups.closure.created_at,
        ).model_copy(update={"active_proposal_id": change.artifact.id})
        self._store.replace(CollectionName.PROJECTS, project)

        approved, approval = decide_artifact(
            change.artifact,
            decision=ApprovalStatus.APPROVED,
            approver_id=self._operator_id,
            correlation_id=change.artifact.id,
            decided_at=followups.closure.created_at + timedelta(seconds=1),
        )
        self._store.replace(CollectionName.ARTIFACTS, approved)
        self._persist_approval(approval)
        send_intent = self._send_stub.request_send(
            approved,
            approval,
            gmail_thread_id=gmail_thread_id,
            correlation_id=change.artifact.id,
            created_at=followups.closure.created_at + timedelta(seconds=2),
        )
        self._persist_send(send_intent)
        sent = advance_artifact(
            approved, ArtifactStatus.SENDING, ArtifactStatus.SENT
        )
        self._store.replace(CollectionName.ARTIFACTS, sent)
        expansion = advance_scope_event(
            expansion,
            ScopeEventStatus.APPROVED,
            ScopeEventStatus.SENT,
        )
        self._store.replace(CollectionName.SCOPE_EVENTS, expansion)
        project = self._advance_project(
            project,
            ProjectLifecycleStatus.ACTIVE_PROJECT,
            "approved change order send intent created",
            followups.closure.created_at + timedelta(seconds=2),
        )
        self._store.replace(CollectionName.PROJECTS, project)
        return _ApprovedChangeStage(
            project=project,
            expansion=expansion,
            proposed_scope=change.proposed_scope,
            artifact=sent,
            approval=approval,
            send_intent=send_intent,
        )

    def _persist_approval(self, approval: ApprovalRecord) -> None:
        self._store.create(
            CollectionName.APPROVALS,
            approval,
            unique_keys={
                "artifact_approval": IdempotencyKeys.approval(
                    approval.artifact_id,
                    approval.artifact_version,
                    approval.artifact_checksum,
                )
            },
            immutable=True,
        )

    def _persist_send(self, send_intent: SendIntent) -> None:
        self._store.create(
            CollectionName.SENDS,
            send_intent,
            unique_keys={
                "send_action": IdempotencyKeys.send_action(
                    send_intent.artifact_id,
                    send_intent.artifact_version,
                    send_intent.artifact_checksum,
                    send_intent.gmail_thread_id,
                )
            },
            immutable=True,
        )

    def _record_event_and_decision(
        self, event: ScopeEventRecord, *, rationale: str
    ) -> None:
        self._store.create(
            CollectionName.SCOPE_EVENTS,
            event,
            unique_keys={
                "gmail_message_id": IdempotencyKeys.gmail_message(
                    event.gmail_message_id
                )
            },
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
        self._store.create(
            CollectionName.SCOPE_DECISIONS,
            decision,
            unique_keys={
                "gmail_message_id": IdempotencyKeys.gmail_message(
                    event.gmail_message_id
                )
            },
        )

    def _advance_project(
        self,
        project: ProjectRecord,
        target: ProjectLifecycleStatus,
        reason: str,
        at: datetime,
    ) -> ProjectRecord:
        updated, transition = advance_project(
            project,
            target,
            reason=reason,
            at=at,
        )
        self._store.create(CollectionName.STATE_TRANSITIONS, transition)
        return updated

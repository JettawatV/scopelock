"""Application-owned orchestration for normalized inbound Gmail messages."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from scopelock.domain.enums import (
    AgentRoute,
    InboundProcessingStatus,
    ProjectLifecycleStatus,
    ScopeAnalysisStatus,
    ScopeBufferStatus,
    ScopeEventClassification,
    ScopeEventStatus,
)
from scopelock.domain.models import (
    AgentRun,
    AgentRunStatus,
    EvidenceRef,
    ModuleQuantity,
    RequirementAnalysis,
    ScopeAnalysis,
    ScopeVersion,
)
from scopelock.domain.workflow_models import (
    AnalysisContext,
    InboundEmail,
    InboundMessageRecord,
    InboundProcessingResult,
    ModuleReplacement,
    ProjectRecord,
    ScopeBufferRecord,
    ScopeDecisionRecord,
    ScopeEventRecord,
    ThreadMessageContext,
)
from scopelock.repositories.contracts import ApplicationRepository
from scopelock.repositories.model_store import CollectionName, ModelStore
from scopelock.services.adk_agent_gateway import AdkAgentGateway
from scopelock.services.idempotency_service import IdempotencyKeys
from scopelock.services.identity import stable_hash, stable_id
from scopelock.services.inbound_router import InboundMessageRouter
from scopelock.services.initial_proposal_workflow import InitialProposalWorkflow
from scopelock.services.scope_analysis_policy import ScopeAnalysisPolicy
from scopelock.services.scope_buffer_service import ScopeBufferService
from scopelock.services.sop_service import SOPCatalog
from scopelock.services.workflow_state import advance_project, advance_scope_event


class InboundProcessingWorkflow:
    """Route first, invoke one bounded agent, then run deterministic services."""

    def __init__(
        self,
        *,
        catalog: SOPCatalog,
        repository: ApplicationRepository,
        artifact_root: str | Path,
        gateway: AdkAgentGateway | None = None,
    ) -> None:
        self._catalog = catalog
        self._repository = repository
        self._store = ModelStore(repository, use_boundaries=True)
        self._router = InboundMessageRouter(repository)
        self._gateway = gateway or AdkAgentGateway(catalog)
        self._artifact_root = Path(artifact_root)

    async def process(
        self,
        email: InboundEmail,
        *,
        prior_messages: Iterable[ThreadMessageContext] = (),
    ) -> InboundProcessingResult:
        idempotency_key = stable_hash(
            "inbound-processing",
            email.message_id,
            email.raw_content_hash or stable_hash(email.subject, email.body),
            self._catalog.version,
        )
        prior_result = self._store.find_by_unique_key(
            CollectionName.INBOUND_RESULTS,
            key_name="gmail_message_id",
            key_value=IdempotencyKeys.gmail_message(email.message_id),
            model_type=InboundProcessingResult,
        )
        if prior_result is not None:
            return prior_result.model_copy(update={"replayed": True})

        decision = self._router.route(email)
        correlation_id = stable_id("correlation", idempotency_key)
        self._persist_inbound(email, correlation_id)
        if decision.route == AgentRoute.IGNORE:
            status = (
                InboundProcessingStatus.DUPLICATE
                if decision.duplicate
                else InboundProcessingStatus.IGNORED
            )
            return self._persist_result(
                InboundProcessingResult(
                    idempotency_key=idempotency_key,
                    correlation_id=correlation_id,
                    status=status,
                    route=decision.route,
                    message_id=email.message_id,
                    thread_id=email.thread_id,
                    project_id=decision.project_id,
                )
            )

        project = self._load_project(decision.project_id)
        current_scope = None
        if project is not None and project.active_scope_version_id is not None:
            current_scope = self._store.get(
                CollectionName.SCOPE_VERSIONS,
                project.active_scope_version_id,
                ScopeVersion,
            )
            if current_scope is None:
                return self._persist_result(
                    self._failed_result(
                        idempotency_key,
                        correlation_id,
                        decision.route,
                        email,
                        project.id,
                        "Project active scope is missing",
                    )
                )

        context = AnalysisContext(
            current_email=email,
            prior_messages=tuple(
                message.model_copy(update={"body": message.body[:4_000]})
                for message in tuple(prior_messages)[-5:]
            ),
            current_scope=current_scope,
            semantic_sop=self._catalog.semantic_view(),
            sop_version=self._catalog.version,
        )
        if decision.route == AgentRoute.REQUIREMENT_ANALYSIS:
            return await self._process_requirements(
                context,
                project=project,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            )
        return await self._process_scope(
            context,
            project=project,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
        )

    async def _process_requirements(
        self,
        context: AnalysisContext,
        *,
        project: ProjectRecord | None,
        idempotency_key: str,
        correlation_id: str,
    ) -> InboundProcessingResult:
        email = context.current_email
        run = await self._gateway.analyze_requirements(
            context,
            correlation_id=correlation_id,
        )
        analysis = run.output if isinstance(run.output, RequirementAnalysis) else None
        if run.status != AgentRunStatus.COMPLETED or analysis is None:
            self._persist_run(run)
            status = (
                InboundProcessingStatus.NEEDS_REVIEW
                if run.status == AgentRunStatus.NEEDS_REVIEW
                else InboundProcessingStatus.FAILED
            )
            return self._persist_result(
                InboundProcessingResult(
                    idempotency_key=idempotency_key,
                    correlation_id=correlation_id,
                    status=status,
                    route=AgentRoute.REQUIREMENT_ANALYSIS,
                    message_id=email.message_id,
                    thread_id=email.thread_id,
                    project_id=project.id if project else None,
                    agent_run_id=run.id,
                    error=run.error.message if run.error else None,
                )
            )

        if not analysis.is_project_request:
            self._persist_run(run)
            return self._persist_result(
                InboundProcessingResult(
                    idempotency_key=idempotency_key,
                    correlation_id=correlation_id,
                    status=InboundProcessingStatus.IGNORED,
                    route=AgentRoute.REQUIREMENT_ANALYSIS,
                    message_id=email.message_id,
                    thread_id=email.thread_id,
                    agent_run_id=run.id,
                )
            )

        if not analysis.proposal_ready:
            project = self._ensure_needs_clarification_project(
                email,
                project=project,
                correlation_id=correlation_id,
            )
            run = run.model_copy(update={"project_id": project.id})
            self._persist_run(run)
            self._persist_requirement_decision(
                email,
                project,
                analysis,
                correlation_id=correlation_id,
                idempotency_key=idempotency_key,
            )
            return self._persist_result(
                InboundProcessingResult(
                    idempotency_key=idempotency_key,
                    correlation_id=correlation_id,
                    status=InboundProcessingStatus.NEEDS_REVIEW,
                    route=AgentRoute.REQUIREMENT_ANALYSIS,
                    message_id=email.message_id,
                    thread_id=email.thread_id,
                    project_id=project.id,
                    agent_run_id=run.id,
                )
            )

        workflow = InitialProposalWorkflow(
            catalog=self._catalog,
            repository=self._repository,
            analyzer=lambda _: analysis,
            artifact_root=self._artifact_root,
            model_name=run.model,
            prompt_version=run.prompt_version,
            bounded_persistence=True,
        )
        proposal = workflow.run(email, analysis=analysis, agent_run=run)
        return self._persist_result(
            InboundProcessingResult(
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
                status=InboundProcessingStatus.PROPOSAL_CREATED,
                route=AgentRoute.REQUIREMENT_ANALYSIS,
                message_id=email.message_id,
                thread_id=email.thread_id,
                project_id=proposal.project.id,
                agent_run_id=proposal.agent_run_id,
                scope_version_id=proposal.scope_version_id,
                artifact_id=proposal.artifact.id,
            )
        )

    async def _process_scope(
        self,
        context: AnalysisContext,
        *,
        project: ProjectRecord | None,
        idempotency_key: str,
        correlation_id: str,
    ) -> InboundProcessingResult:
        if project is None or context.current_scope is None:
            return self._persist_result(
                self._failed_result(
                    idempotency_key,
                    correlation_id,
                    AgentRoute.SCOPE_ANALYSIS,
                    context.current_email,
                    project.id if project else None,
                    "Scope route requires a project and active ScopeVersion",
                )
            )
        run = await self._gateway.analyze_scope(
            context,
            correlation_id=correlation_id,
        )
        run = run.model_copy(update={"project_id": project.id})
        self._persist_run(run)
        analysis = run.output if isinstance(run.output, ScopeAnalysis) else None
        if run.status != AgentRunStatus.COMPLETED or analysis is None:
            status = (
                InboundProcessingStatus.NEEDS_REVIEW
                if run.status == AgentRunStatus.NEEDS_REVIEW
                else InboundProcessingStatus.FAILED
            )
            return self._persist_result(
                InboundProcessingResult(
                    idempotency_key=idempotency_key,
                    correlation_id=correlation_id,
                    status=status,
                    route=AgentRoute.SCOPE_ANALYSIS,
                    message_id=context.current_email.message_id,
                    thread_id=context.current_email.thread_id,
                    project_id=project.id,
                    agent_run_id=run.id,
                    error=run.error.message if run.error else None,
                )
            )

        policy = ScopeAnalysisPolicy(
            valid_module_keys={module.key for module in self._catalog.modules},
            quantity_limits={
                module.key: (module.quantity.minimum, module.quantity.maximum)
                for module in self._catalog.modules
            },
        )
        policy_decision = policy.evaluate(
            analysis,
            expected_message_id=context.current_email.message_id,
            normalized_message_body=context.current_email.body,
            expected_scope_version_id=context.current_scope.id,
            baseline_texts=tuple(
                requirement.description for requirement in context.current_scope.requirements
            ),
            expected_sop_version=self._catalog.version,
        )
        scope_event_ids = self._persist_scope_events(
            analysis,
            project=project,
            baseline=context.current_scope,
            authoritative_message_id=context.current_email.message_id,
            recorded_at=context.current_email.received_at,
            correlation_id=correlation_id,
            needs_review=policy_decision.review_required,
        )
        decision = ScopeDecisionRecord(
            id=stable_id("scope-decision", idempotency_key),
            project_id=project.id,
            gmail_message_id=context.current_email.message_id,
            decision_type="SCOPE_ANALYSIS",
            selected_module_keys=tuple(
                sorted(
                    {
                        key
                        for event in analysis.events
                        for key in event.sop_module_keys
                    }
                )
            ),
            rationale="; ".join(policy_decision.reasons) or "Validated atomic scope analysis",
            evidence=self._deduplicate_evidence(
                evidence
                for event in analysis.events
                for evidence in event.evidence
            ),
            correlation_id=correlation_id,
            created_at=context.current_email.received_at,
        )
        self._store.create(CollectionName.SCOPE_DECISIONS, decision)
        return self._persist_result(
            InboundProcessingResult(
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
                status=(
                    InboundProcessingStatus.NEEDS_REVIEW
                    if policy_decision.review_required
                    else InboundProcessingStatus.SCOPE_EVENTS_RECORDED
                ),
                route=AgentRoute.SCOPE_ANALYSIS,
                message_id=context.current_email.message_id,
                thread_id=context.current_email.thread_id,
                project_id=project.id,
                agent_run_id=run.id,
                scope_event_ids=scope_event_ids,
            )
        )

    def _persist_scope_events(
        self,
        analysis: ScopeAnalysis,
        *,
        project: ProjectRecord,
        baseline: ScopeVersion,
        authoritative_message_id: str,
        recorded_at: datetime,
        correlation_id: str,
        needs_review: bool,
    ) -> tuple[str, ...]:
        needs_review = needs_review or any(
            proposal.classification == ScopeEventClassification.REPLACEMENT
            and not (
                len(
                    set(proposal.sop_module_keys)
                    - {item.module_key for item in proposal.quantities}
                )
                == 1
                and len(proposal.quantities) == 1
            )
            for proposal in analysis.events
        )
        buffer_service = ScopeBufferService(self._catalog)
        existing_buffer = (
            self._store.get(
                CollectionName.BUFFERS,
                project.scope_buffer_id,
                ScopeBufferRecord,
            )
            if project.scope_buffer_id
            else None
        )
        persisted_ids: list[str] = []
        final_buffer = existing_buffer
        for index, proposal in enumerate(analysis.events, start=1):
            added_keys = {item.module_key for item in proposal.quantities}
            removed_keys = [
                key for key in proposal.sop_module_keys if key not in added_keys
            ]
            replacements: tuple[ModuleReplacement, ...] = ()
            if proposal.classification == ScopeEventClassification.REPLACEMENT:
                if len(removed_keys) == 1 and len(proposal.quantities) == 1:
                    replacements = (
                        ModuleReplacement(
                            remove=ModuleQuantity(
                                module_key=removed_keys[0], quantity=1
                            ),
                            add=proposal.quantities[0],
                        ),
                    )
                else:
                    needs_review = True
            event = ScopeEventRecord(
                id=stable_id(
                    "scope-event",
                    project.id,
                    baseline.id,
                    authoritative_message_id,
                    str(index),
                    proposal.classification.value,
                    proposal.description,
                ),
                project_id=project.id,
                gmail_message_id=authoritative_message_id,
                baseline_scope_version_id=baseline.id,
                classification=proposal.classification,
                status=ScopeEventStatus.CLASSIFIED,
                description=proposal.description,
                additions=(
                    tuple(proposal.quantities)
                    if proposal.classification == ScopeEventClassification.EXPANSION
                    else ()
                ),
                reductions=(
                    tuple(
                        ModuleQuantity(module_key=key, quantity=1)
                        for key in proposal.sop_module_keys
                    )
                    if proposal.classification == ScopeEventClassification.REDUCTION
                    else ()
                ),
                replacements=replacements,
                evidence=tuple(proposal.evidence),
                unsupported_requirements=tuple(proposal.unsupported_requirements),
                review_required=needs_review,
                correlation_id=correlation_id,
                created_at=recorded_at,
            )
            if needs_review:
                event = advance_scope_event(event, ScopeEventStatus.NEEDS_REVIEW)
            elif event.is_material:
                event, final_buffer = buffer_service.buffer_event(
                    baseline=baseline,
                    event=event,
                    existing=final_buffer,
                )
            else:
                event = buffer_service.record_non_material(event)
                if (
                    proposal.classification == ScopeEventClassification.CLOSURE
                    and final_buffer is not None
                ):
                    final_buffer = buffer_service.mark_ready_on_closure(final_buffer)
            self._store.create(CollectionName.SCOPE_EVENTS, event)
            persisted_ids.append(event.id)

        if (
            final_buffer is not None
            and analysis.conversation_closure
            and not needs_review
            and final_buffer.status == ScopeBufferStatus.OPEN
        ):
            final_buffer = buffer_service.mark_ready_on_closure(final_buffer)

        if final_buffer is not None and not needs_review:
            self._store.create(CollectionName.BUFFERS, final_buffer)
            if project.scope_buffer_id != final_buffer.id:
                project = project.model_copy(
                    update={
                        "scope_buffer_id": final_buffer.id,
                        "updated_at": final_buffer.updated_at,
                    }
                )
                self._store.replace(CollectionName.PROJECTS, project)
        return tuple(persisted_ids)

    def _ensure_needs_clarification_project(
        self,
        email: InboundEmail,
        *,
        project: ProjectRecord | None,
        correlation_id: str,
    ) -> ProjectRecord:
        if project is None:
            project = ProjectRecord(
                id=stable_id("project", email.thread_id),
                client_name=email.sender_name,
                client_email=email.sender_email,
                gmail_thread_id=email.thread_id,
                title=email.subject,
                lifecycle_status=ProjectLifecycleStatus.NEW,
                correlation_id=correlation_id,
                created_at=email.received_at,
                updated_at=email.received_at,
            )
            self._store.create(
                CollectionName.PROJECTS,
                project,
                unique_keys={
                    "gmail_thread_id": IdempotencyKeys.gmail_thread(email.thread_id)
                },
            )
        if project.lifecycle_status in {
            ProjectLifecycleStatus.NEW,
            ProjectLifecycleStatus.NEEDS_CLARIFICATION,
        }:
            project, transition = advance_project(
                project,
                ProjectLifecycleStatus.ANALYZING_REQUIREMENTS,
                reason="inbound project requirements need semantic analysis",
                at=email.received_at,
            )
            self._store.replace(CollectionName.PROJECTS, project)
            self._store.create(CollectionName.STATE_TRANSITIONS, transition)
        if project.lifecycle_status == ProjectLifecycleStatus.ANALYZING_REQUIREMENTS:
            project, transition = advance_project(
                project,
                ProjectLifecycleStatus.NEEDS_CLARIFICATION,
                reason="requirements require operator clarification",
                at=email.received_at,
            )
            self._store.replace(CollectionName.PROJECTS, project)
            self._store.create(CollectionName.STATE_TRANSITIONS, transition)
        return project

    def _persist_requirement_decision(
        self,
        email: InboundEmail,
        project: ProjectRecord,
        analysis: RequirementAnalysis,
        *,
        correlation_id: str,
        idempotency_key: str,
    ) -> None:
        decision = ScopeDecisionRecord(
            id=stable_id("decision", idempotency_key),
            project_id=project.id,
            gmail_message_id=email.message_id,
            decision_type="INITIAL_REQUIREMENTS_NEED_REVIEW",
            selected_module_keys=tuple(
                item.module_key for item in analysis.selected_sop_modules
            ),
            rationale="Supported mappings retained; commercial creation blocked pending review",
            evidence=self._deduplicate_evidence(
                evidence
                for selection in analysis.selected_sop_modules
                for evidence in selection.evidence
            ),
            correlation_id=correlation_id,
            created_at=email.received_at,
        )
        self._store.create(CollectionName.SCOPE_DECISIONS, decision)

    def _persist_inbound(self, email: InboundEmail, correlation_id: str) -> None:
        record = InboundMessageRecord(
            id=stable_id("inbound-message", email.message_id),
            email=email,
            correlation_id=correlation_id,
            created_at=email.received_at,
        )
        self._store.create(
            CollectionName.INBOUND_MESSAGES,
            record,
            unique_keys={
                "gmail_message_id": IdempotencyKeys.gmail_message(email.message_id)
            },
            immutable=True,
        )

    def _persist_run(self, run: AgentRun) -> None:
        self._store.create(
            CollectionName.AGENT_RUNS,
            run,
            unique_keys={
                "trigger_agent": f"{run.trigger_ref}:{run.prompt_version}"
            },
        )
        for action in run.tool_trajectory:
            self._store.create(CollectionName.TOOL_ACTIONS, action)

    def _persist_result(
        self,
        result: InboundProcessingResult,
    ) -> InboundProcessingResult:
        self._store.create(
            CollectionName.INBOUND_RESULTS,
            result,
            document_id=result.idempotency_key,
            unique_keys={
                "gmail_message_id": IdempotencyKeys.gmail_message(result.message_id)
            },
            immutable=True,
        )
        return result

    def _load_project(self, project_id: str | None) -> ProjectRecord | None:
        if project_id is None:
            return None
        return self._store.get(CollectionName.PROJECTS, project_id, ProjectRecord)

    @staticmethod
    def _deduplicate_evidence(
        evidence: Iterable[EvidenceRef],
    ) -> tuple[EvidenceRef, ...]:
        unique: dict[tuple[str, str, str, str | None], EvidenceRef] = {}
        for item in evidence:
            unique[
                (
                    item.source_type,
                    item.source_id,
                    item.quote_or_rule,
                    item.source_version,
                )
            ] = item
        return tuple(unique.values())

    @staticmethod
    def _failed_result(
        idempotency_key: str,
        correlation_id: str,
        route: AgentRoute,
        email: InboundEmail,
        project_id: str | None,
        error: str,
    ) -> InboundProcessingResult:
        return InboundProcessingResult(
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            status=InboundProcessingStatus.FAILED,
            route=route,
            message_id=email.message_id,
            thread_id=email.thread_id,
            project_id=project_id,
            error=error,
        )

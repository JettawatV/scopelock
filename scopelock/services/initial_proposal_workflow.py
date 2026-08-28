"""Day 7 local initial-proposal vertical path."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from scopelock.domain.enums import ArtifactStatus, ProjectLifecycleStatus
from scopelock.domain.models import (
    AgentRun,
    AgentRunError,
    AgentRunStatus,
    CommercialArtifact,
    EvidenceRef,
    ModuleQuantity,
    RequirementAnalysis,
    ScopeVersion,
    ScopeRequirementSnapshot,
    ToolAction,
    ToolActionPhase,
    ToolActionStatus,
)
from scopelock.domain.workflow_models import (
    ArtifactEventRecord,
    AuditRecord,
    InboundEmail,
    LocalInitialProposalResult,
    ProjectRecord,
    ProposalData,
    RenderedProposal,
    ScopeDecisionRecord,
    StateTransitionRecord,
)
from scopelock.repositories.contracts import ApplicationRepository
from scopelock.repositories.model_store import CollectionName, ModelStore
from scopelock.services.approval_policy import seal_artifact_for_review
from scopelock.services.commercial_artifact_service import (
    create_next_commercial_artifact,
    create_scope_version,
)
from scopelock.services.pricing_engine import PricingEngine
from scopelock.services.proposal_service import ProposalRenderer
from scopelock.services.sop_service import SOPCatalog
from scopelock.services.timeline_engine import TimelineEngine
from scopelock.services.identity import stable_hash, stable_id
from scopelock.services.idempotency_service import IdempotencyKeys
from scopelock.services.semantic_contracts import (
    SemanticContractViolation,
    validate_requirement_analysis,
)
from scopelock.services.workflow_state import advance_project


RequirementAnalyzer = Callable[[InboundEmail], RequirementAnalysis]


@dataclass(frozen=True)
class _SemanticStage:
    analysis: RequirementAnalysis
    selections: tuple[ModuleQuantity, ...]
    agent_run: AgentRun
    decision: ScopeDecisionRecord


@dataclass(frozen=True)
class _CommercialStage:
    scope: ScopeVersion
    artifact: CommercialArtifact
    proposal: ProposalData
    rendered: RenderedProposal
    audit: tuple[AuditRecord, ...]


class InitialProposalWorkflow:
    def __init__(
        self,
        *,
        catalog: SOPCatalog,
        repository: ApplicationRepository,
        analyzer: RequirementAnalyzer,
        artifact_root: str | Path,
        model_name: str = "gemini-3.5-flash",
        prompt_version: str = "requirement_analyzer_v5",
        bounded_persistence: bool = False,
    ) -> None:
        self._catalog = catalog
        self._store = ModelStore(repository, use_boundaries=bounded_persistence)
        self._analyzer = analyzer
        self._renderer = ProposalRenderer(artifact_root)
        self._model_name = model_name
        self._prompt_version = prompt_version

    def run(
        self,
        email: InboundEmail,
        *,
        analysis: RequirementAnalysis | None = None,
        agent_run: AgentRun | None = None,
    ) -> LocalInitialProposalResult:
        input_hash = stable_hash(email.subject, email.body)
        idempotency_key = stable_hash(
            "initial-proposal",
            email.message_id,
            input_hash,
            self._catalog.version,
            self._prompt_version,
        )
        prior = self._store.get(
            CollectionName.WORKFLOW_RESULTS,
            idempotency_key,
            LocalInitialProposalResult,
        )
        if prior is not None:
            return prior.model_copy(update={"replayed": True})

        correlation_id = (
            agent_run.correlation_id
            if agent_run is not None
            else stable_id("corr", idempotency_key)
        )
        project_id = stable_id("project", email.thread_id)
        run_id = agent_run.id if agent_run is not None else stable_id("run", idempotency_key)
        project = self._create_project(email, project_id, correlation_id)
        project, analyzing_transition = advance_project(
            project,
            ProjectLifecycleStatus.ANALYZING_REQUIREMENTS,
            reason="inbound project email",
            at=email.received_at,
        )
        semantic = self._run_semantic_stage(
            email=email,
            project_id=project_id,
            run_id=run_id,
            input_hash=input_hash,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            provided_analysis=analysis,
            provided_agent_run=agent_run,
        )
        commercial = self._run_commercial_stage(
            email=email,
            project_id=project_id,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            semantic=semantic,
        )
        project = project.model_copy(
            update={
                "active_scope_version_id": commercial.scope.id,
                "active_proposal_id": commercial.artifact.id,
                "current_price_usd": commercial.proposal.total_usd,
                "current_timeline_days": commercial.proposal.timeline.total_days,
            }
        )
        project, review_transition = advance_project(
            project,
            ProjectLifecycleStatus.AWAITING_USER_REVIEW,
            reason="deterministic proposal sealed for review",
            at=email.received_at,
        )
        self._store.replace(CollectionName.PROJECTS, project)
        self._record_completion(
            artifact=commercial.artifact,
            transitions=(analyzing_transition, review_transition),
            audit=commercial.audit,
            correlation_id=correlation_id,
            recorded_at=email.received_at,
        )

        result = LocalInitialProposalResult(
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            project=project,
            scope_version_id=commercial.scope.id,
            artifact=commercial.artifact,
            proposal=commercial.proposal,
            rendered_proposal=commercial.rendered,
            agent_run_id=semantic.agent_run.id,
            scope_decision_id=semantic.decision.id,
            audit_record_ids=tuple(record.id for record in commercial.audit),
        )
        self._store.create(
            CollectionName.WORKFLOW_RESULTS,
            result,
            document_id=idempotency_key,
            unique_keys={
                "gmail_message_id": IdempotencyKeys.gmail_message(email.message_id)
            },
            immutable=True,
        )
        return result

    def _create_project(
        self,
        email: InboundEmail,
        project_id: str,
        correlation_id: str,
    ) -> ProjectRecord:
        existing = self._store.find_by_unique_key(
            CollectionName.PROJECTS,
            key_name="gmail_thread_id",
            key_value=IdempotencyKeys.gmail_thread(email.thread_id),
            model_type=ProjectRecord,
        )
        if existing is not None:
            return existing
        project = ProjectRecord(
            id=project_id,
            client_name=email.sender_name,
            client_email=email.sender_email,
            gmail_thread_id=email.thread_id,
            title=email.subject,
            lifecycle_status=ProjectLifecycleStatus.NEW,
            correlation_id=correlation_id,
            created_at=email.received_at,
            updated_at=email.received_at,
        )
        stored = self._store.create(
            CollectionName.PROJECTS,
            project,
            unique_keys={
                "gmail_thread_id": IdempotencyKeys.gmail_thread(email.thread_id)
            },
        )
        return ProjectRecord.model_validate(stored.payload)

    def _run_semantic_stage(
        self,
        *,
        email: InboundEmail,
        project_id: str,
        run_id: str,
        input_hash: str,
        idempotency_key: str,
        correlation_id: str,
        provided_analysis: RequirementAnalysis | None = None,
        provided_agent_run: AgentRun | None = None,
    ) -> _SemanticStage:
        try:
            analysis = provided_analysis or self._analyzer(email)
            validate_requirement_analysis(
                analysis,
                valid_module_keys={module.key for module in self._catalog.modules},
                expected_message_id=email.message_id,
                normalized_message_body=email.body,
                expected_sop_version=self._catalog.version,
                quantity_limits={
                    module.key: (module.quantity.minimum, module.quantity.maximum)
                    for module in self._catalog.modules
                },
            )
            if not analysis.is_project_request or not analysis.proposal_ready:
                raise SemanticContractViolation(
                    "Initial proposal workflow requires proposal-ready analysis"
                )
        except Exception as exc:
            if provided_agent_run is not None:
                failed_run = provided_agent_run.model_copy(
                    update={
                        "project_id": project_id,
                        "completed_at": email.received_at,
                        "status": (
                            AgentRunStatus.NEEDS_REVIEW
                            if isinstance(exc, SemanticContractViolation)
                            else AgentRunStatus.FAILED
                        ),
                        "output": None,
                        "error": AgentRunError(
                            category=type(exc).__name__,
                            message=str(exc),
                            retryable=False,
                        ),
                    }
                )
            else:
                failed_run = AgentRun(
                    id=run_id,
                    correlation_id=correlation_id,
                    project_id=project_id,
                    trigger_type="gmail_message",
                    trigger_ref=email.message_id,
                    agent_name="requirement_analyzer",
                    model=self._model_name,
                    prompt_version=self._prompt_version,
                    started_at=email.received_at,
                    completed_at=email.received_at,
                    status=(
                        AgentRunStatus.NEEDS_REVIEW
                        if isinstance(exc, SemanticContractViolation)
                        else AgentRunStatus.FAILED
                    ),
                    input_hash=input_hash,
                    error=AgentRunError(
                        category=type(exc).__name__,
                        message=str(exc),
                        retryable=False,
                    ),
                )
            self._store.create(
                CollectionName.AGENT_RUNS,
                failed_run,
                unique_keys={
                    "trigger_agent": f"{email.message_id}:{self._prompt_version}"
                },
            )
            raise
        selected = tuple(
            ModuleQuantity(module_key=item.module_key, quantity=item.quantity)
            for item in analysis.selected_sop_modules
        )
        if not selected:
            raise ValueError("Proposal-ready analysis must select SOP modules")
        for selection in selected:
            self._catalog.module(selection.module_key)

        if provided_agent_run is not None:
            tool_actions = tuple(provided_agent_run.tool_trajectory)
            agent_run = provided_agent_run.model_copy(
                update={
                    "project_id": project_id,
                    "status": AgentRunStatus.COMPLETED,
                    "output": analysis,
                    "error": None,
                }
            )
        else:
            tool_actions = self._tool_actions(run_id, email.received_at)
            agent_run = AgentRun(
                id=run_id,
                correlation_id=correlation_id,
                project_id=project_id,
                trigger_type="gmail_message",
                trigger_ref=email.message_id,
                agent_name="requirement_analyzer",
                model=self._model_name,
                prompt_version=self._prompt_version,
                started_at=email.received_at,
                completed_at=email.received_at,
                status=AgentRunStatus.COMPLETED,
                input_hash=input_hash,
                output=analysis,
                tool_trajectory=list(tool_actions),
            )
        self._store.create(
            CollectionName.AGENT_RUNS,
            agent_run,
            unique_keys={"trigger_agent": f"{email.message_id}:{self._prompt_version}"},
        )
        for action in tool_actions:
            self._store.create(CollectionName.TOOL_ACTIONS, action)

        decision = ScopeDecisionRecord(
            id=stable_id("decision", idempotency_key),
            project_id=project_id,
            gmail_message_id=email.message_id,
            decision_type="INITIAL_REQUIREMENT_MAPPING",
            selected_module_keys=tuple(item.module_key for item in selected),
            rationale="Validated proposal-ready semantic mapping to the loaded SOP",
            evidence=self._deduplicate_evidence(analysis),
            correlation_id=correlation_id,
            created_at=email.received_at,
        )
        self._store.create(
            CollectionName.SCOPE_DECISIONS,
            decision,
            unique_keys={
                "gmail_message_id": IdempotencyKeys.gmail_message(email.message_id)
            },
        )
        return _SemanticStage(
            analysis=analysis,
            selections=selected,
            agent_run=agent_run,
            decision=decision,
        )

    def _run_commercial_stage(
        self,
        *,
        email: InboundEmail,
        project_id: str,
        idempotency_key: str,
        correlation_id: str,
        semantic: _SemanticStage,
    ) -> _CommercialStage:
        analysis = semantic.analysis
        pricing = PricingEngine(self._catalog).calculate(semantic.selections)
        timeline = TimelineEngine(self._catalog).calculate(semantic.selections)
        requirements = tuple(
            ScopeRequirementSnapshot(
                requirement_id=item.requirement_id,
                category=item.category,
                description=item.description,
                normalized_key=item.normalized_key,
                source_message_id=email.message_id,
                source_quote=item.source_quote,
            )
            for item in analysis.requirements
        )
        scope_id = stable_id("scope", idempotency_key, "1")
        scope = create_scope_version(
            project_id=project_id,
            existing=(),
            requirements=requirements,
            module_selections=timeline.calculation_inputs,
            pricing_result=pricing,
            timeline_result=timeline,
            assumptions=analysis.assumptions,
            exclusions=analysis.exclusions_to_surface,
            scope_version_id=scope_id,
            created_at=email.received_at,
        )
        self._store.create(
            CollectionName.SCOPE_VERSIONS,
            scope,
            unique_keys={"artifact_version": f"{project_id}:scope:1"},
        )

        artifact_id = stable_id("artifact", idempotency_key, "proposal:1")
        draft = create_next_commercial_artifact(
            project_id=project_id,
            proposed_scope=scope,
            existing=(),
            artifact_id=artifact_id,
            created_at=email.received_at,
        )
        artifact = seal_artifact_for_review(draft)
        self._store.create(
            CollectionName.ARTIFACTS,
            artifact,
            unique_keys={"artifact_version": f"{project_id}:proposal:1"},
        )

        proposal = ProposalData(
            project_id=project_id,
            project_title=analysis.project_title,
            client_name=email.sender_name,
            client_email=email.sender_email,
            objective=analysis.objective,
            requirements=requirements,
            selected_modules=timeline.calculation_inputs,
            line_items=pricing.line_items,
            total_usd=pricing.total_usd,
            currency=pricing.currency,
            timeline=timeline,
            assumptions=tuple(analysis.assumptions),
            exclusions=tuple(analysis.exclusions_to_surface),
            evidence=self._deduplicate_evidence(analysis),
            validity_days=self._catalog.business.proposal_valid_days,
            source_message_id=email.message_id,
            source_scope_version_id=scope.id,
            source_scope_version_number=scope.version_number,
            sop_version=self._catalog.version,
            generated_at=email.received_at,
        )
        rendered = self._renderer.render(
            proposal,
            commercial_artifact_id=artifact.id,
            artifact_version=artifact.version_number,
        )

        audit = (
            self._audit(
                "deterministic_pricing",
                artifact.id,
                "calculate_price",
                correlation_id,
                email.received_at,
                {"currency": pricing.currency, "total_usd": pricing.total_usd},
            ),
            self._audit(
                "deterministic_timeline",
                artifact.id,
                "calculate_timeline",
                correlation_id,
                email.received_at,
                {"total_days": timeline.total_days},
            ),
            self._audit(
                "proposal_artifact",
                artifact.id,
                "render_fixed_template",
                correlation_id,
                email.received_at,
                {
                    "proposal_checksum": rendered.content_checksum,
                    "scope_version_id": scope.id,
                    "sop_version": scope.sop_version,
                },
            ),
        )
        return _CommercialStage(
            scope=scope,
            artifact=artifact,
            proposal=proposal,
            rendered=rendered,
            audit=audit,
        )

    def _record_completion(
        self,
        *,
        artifact: CommercialArtifact,
        transitions: tuple[StateTransitionRecord, ...],
        audit: tuple[AuditRecord, ...],
        correlation_id: str,
        recorded_at: datetime,
    ) -> None:
        artifact_event = ArtifactEventRecord(
            id=stable_id("artifact-event", artifact.id, "awaiting-review"),
            artifact_id=artifact.id,
            artifact_version=artifact.version_number,
            status=ArtifactStatus.AWAITING_USER_REVIEW,
            action="SEALED_FOR_USER_REVIEW",
            checksum=artifact.checksum,
            correlation_id=correlation_id,
            created_at=recorded_at,
        )
        self._store.create(CollectionName.ARTIFACT_EVENTS, artifact_event)
        for transition in transitions:
            self._store.create(CollectionName.STATE_TRANSITIONS, transition)
        for record in audit:
            self._store.create(CollectionName.AUDIT_RECORDS, record)

    @staticmethod
    def _deduplicate_evidence(analysis: RequirementAnalysis) -> tuple[EvidenceRef, ...]:
        evidence = [*analysis.evidence]
        for selection in analysis.selected_sop_modules:
            evidence.extend(selection.evidence)
        seen: set[tuple[str, str, str]] = set()
        result: list[EvidenceRef] = []
        for item in evidence:
            key = (item.source_type, item.source_id, item.quote_or_rule)
            if key not in seen:
                seen.add(key)
                result.append(item)
        return tuple(result)

    @staticmethod
    def _tool_actions(run_id: str, now: datetime) -> tuple[ToolAction, ...]:
        call_id = stable_id("call", run_id, "get_sop_catalog")
        return (
            ToolAction(
                id=stable_id("tool", call_id, "call"),
                agent_run_id=run_id,
                sequence=1,
                call_id=call_id,
                tool_name="get_sop_catalog",
                phase=ToolActionPhase.CALL,
                status=ToolActionStatus.REQUESTED,
                recorded_at=now,
            ),
            ToolAction(
                id=stable_id("tool", call_id, "result"),
                agent_run_id=run_id,
                sequence=2,
                call_id=call_id,
                tool_name="get_sop_catalog",
                phase=ToolActionPhase.RESULT,
                status=ToolActionStatus.COMPLETED,
                payload={"access": "read_only", "validated": True},
                recorded_at=now,
            ),
        )

    @staticmethod
    def _audit(
        record_type: str,
        entity_id: str,
        action: str,
        correlation_id: str,
        now: datetime,
        payload: dict[str, Any],
    ) -> AuditRecord:
        return AuditRecord(
            id=stable_id("audit", entity_id, action),
            record_type=record_type,
            entity_id=entity_id,
            action=action,
            actor="application",
            correlation_id=correlation_id,
            payload=payload,
            created_at=now,
        )

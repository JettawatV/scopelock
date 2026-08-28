"""Day 7 local initial-proposal vertical path."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from scopelock.domain.enums import ArtifactStatus, ProjectLifecycleStatus
from scopelock.domain.models import (
    AgentRun,
    AgentRunStatus,
    EvidenceRef,
    ModuleQuantity,
    RequirementAnalysis,
    ScopeRequirementSnapshot,
    ToolAction,
    ToolActionPhase,
    ToolActionStatus,
)
from scopelock.domain.state_machines import transition_project
from scopelock.domain.workflow_models import (
    ArtifactEventRecord,
    AuditRecord,
    InboundEmail,
    LocalInitialProposalResult,
    ProjectRecord,
    ProposalData,
    ScopeDecisionRecord,
    StateTransitionRecord,
)
from scopelock.repositories.contracts import ApplicationRepository
from scopelock.services.approval_policy import seal_artifact_for_review
from scopelock.services.commercial_artifact_service import (
    create_next_commercial_artifact,
    create_scope_version,
)
from scopelock.services.pricing_engine import PricingEngine
from scopelock.services.proposal_service import ProposalRenderer
from scopelock.services.sop_service import SOPCatalog
from scopelock.services.timeline_engine import TimelineEngine


RequirementAnalyzer = Callable[[InboundEmail], RequirementAnalysis]


def stable_hash(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def stable_id(prefix: str, *parts: str) -> str:
    return f"{prefix}-{stable_hash(*parts)[:24]}"


def _save_model(
    repository: ApplicationRepository,
    collection: str,
    model: BaseModel,
    *,
    unique_keys: dict[str, str] | None = None,
    immutable: bool = False,
) -> None:
    repository.create_or_get(
        collection=collection,
        document_id=str(getattr(model, "id")),
        payload=model.model_dump(mode="json"),
        unique_keys=unique_keys,
        immutable=immutable,
    )


class InitialProposalWorkflow:
    def __init__(
        self,
        *,
        catalog: SOPCatalog,
        repository: ApplicationRepository,
        analyzer: RequirementAnalyzer,
        artifact_root: str | Path,
        model_name: str = "gemini-3.5-flash",
        prompt_version: str = "requirement_analyzer_v2",
    ) -> None:
        self._catalog = catalog
        self._repository = repository
        self._analyzer = analyzer
        self._renderer = ProposalRenderer(artifact_root)
        self._model_name = model_name
        self._prompt_version = prompt_version

    def run(self, email: InboundEmail) -> LocalInitialProposalResult:
        input_hash = stable_hash(email.subject, email.body)
        idempotency_key = stable_hash(
            "initial-proposal",
            email.message_id,
            input_hash,
            self._catalog.version,
            self._prompt_version,
        )
        prior = self._repository.get(
            collection="workflow_results", document_id=idempotency_key
        )
        if prior is not None:
            return LocalInitialProposalResult.model_validate(prior.payload).model_copy(
                update={"replayed": True}
            )

        correlation_id = stable_id("corr", idempotency_key)
        project_id = stable_id("project", email.thread_id)
        run_id = stable_id("run", idempotency_key)
        now = email.received_at
        project = ProjectRecord(
            id=project_id,
            client_name=email.sender_name,
            client_email=email.sender_email,
            gmail_thread_id=email.thread_id,
            title=email.subject,
            lifecycle_status=ProjectLifecycleStatus.NEW,
            correlation_id=correlation_id,
            created_at=now,
            updated_at=now,
        )
        _save_model(
            self._repository,
            "projects",
            project,
            unique_keys={"gmail_thread_id": email.thread_id},
        )

        transitions: list[StateTransitionRecord] = []
        audit: list[AuditRecord] = []
        project = self._transition_project(
            project,
            ProjectLifecycleStatus.ANALYZING_REQUIREMENTS,
            reason="inbound project email",
            now=now,
            transitions=transitions,
        )

        analysis = self._analyzer(email)
        if not analysis.is_project_request or not analysis.proposal_ready:
            raise ValueError("Initial proposal workflow requires proposal-ready analysis")
        selected = tuple(
            ModuleQuantity(module_key=item.module_key, quantity=item.quantity)
            for item in analysis.selected_sop_modules
        )
        if not selected:
            raise ValueError("Proposal-ready analysis must select SOP modules")
        for selection in selected:
            self._catalog.module(selection.module_key)

        tool_actions = self._tool_actions(run_id, now)
        agent_run = AgentRun(
            id=run_id,
            correlation_id=correlation_id,
            project_id=project_id,
            trigger_type="gmail_message",
            trigger_ref=email.message_id,
            agent_name="requirement_analyzer",
            model=self._model_name,
            prompt_version=self._prompt_version,
            started_at=now,
            completed_at=now,
            status=AgentRunStatus.COMPLETED,
            input_hash=input_hash,
            output=analysis,
            tool_trajectory=list(tool_actions),
        )
        _save_model(
            self._repository,
            "agent_runs",
            agent_run,
            unique_keys={"trigger_agent": f"{email.message_id}:{self._prompt_version}"},
        )
        for action in tool_actions:
            _save_model(self._repository, "tool_actions", action)

        decision = ScopeDecisionRecord(
            id=stable_id("decision", idempotency_key),
            project_id=project_id,
            gmail_message_id=email.message_id,
            decision_type="INITIAL_REQUIREMENT_MAPPING",
            selected_module_keys=tuple(item.module_key for item in selected),
            rationale="Validated proposal-ready semantic mapping to the loaded SOP",
            evidence=self._deduplicate_evidence(analysis),
            correlation_id=correlation_id,
            created_at=now,
        )
        _save_model(
            self._repository,
            "scope_decisions",
            decision,
            unique_keys={"gmail_message_id": email.message_id},
        )

        pricing = PricingEngine(self._catalog).calculate(selected)
        timeline = TimelineEngine(self._catalog).calculate(selected)
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
            created_at=now,
        )
        _save_model(
            self._repository,
            "scope_versions",
            scope,
            unique_keys={"artifact_version": f"{project_id}:scope:1"},
        )

        artifact_id = stable_id("artifact", idempotency_key, "proposal:1")
        draft = create_next_commercial_artifact(
            project_id=project_id,
            proposed_scope=scope,
            existing=(),
            artifact_id=artifact_id,
            created_at=now,
        )
        artifact = seal_artifact_for_review(draft)
        _save_model(
            self._repository,
            "artifacts",
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
            generated_at=now,
        )
        rendered = self._renderer.render(
            proposal,
            commercial_artifact_id=artifact.id,
            artifact_version=artifact.version_number,
        )

        audit.extend(
            (
                self._audit(
                    "deterministic_pricing",
                    artifact.id,
                    "calculate_price",
                    correlation_id,
                    now,
                    {"currency": pricing.currency, "total_usd": pricing.total_usd},
                ),
                self._audit(
                    "deterministic_timeline",
                    artifact.id,
                    "calculate_timeline",
                    correlation_id,
                    now,
                    {"total_days": timeline.total_days},
                ),
                self._audit(
                    "proposal_artifact",
                    artifact.id,
                    "render_fixed_template",
                    correlation_id,
                    now,
                    {
                        "proposal_checksum": rendered.content_checksum,
                        "scope_version_id": scope.id,
                        "sop_version": scope.sop_version,
                    },
                ),
            )
        )
        project = project.model_copy(
            update={
                "active_scope_version_id": scope.id,
                "active_proposal_id": artifact.id,
                "current_price_usd": pricing.total_usd,
                "current_timeline_days": timeline.total_days,
            }
        )
        project = self._transition_project(
            project,
            ProjectLifecycleStatus.AWAITING_USER_REVIEW,
            reason="deterministic proposal sealed for review",
            now=now,
            transitions=transitions,
        )
        project_document = self._repository.get(
            collection="projects", document_id=project.id
        )
        assert project_document is not None
        self._repository.compare_and_set(
            collection="projects",
            document_id=project.id,
            expected_revision=project_document.revision,
            payload=project.model_dump(mode="json"),
        )

        artifact_event = ArtifactEventRecord(
            id=stable_id("artifact-event", artifact.id, "awaiting-review"),
            artifact_id=artifact.id,
            artifact_version=artifact.version_number,
            status=ArtifactStatus.AWAITING_USER_REVIEW,
            action="SEALED_FOR_USER_REVIEW",
            checksum=artifact.checksum,
            correlation_id=correlation_id,
            created_at=now,
        )
        _save_model(self._repository, "artifact_events", artifact_event)
        for transition in transitions:
            _save_model(self._repository, "state_transitions", transition)
        for record in audit:
            _save_model(self._repository, "audit_records", record)

        result = LocalInitialProposalResult(
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            project=project,
            scope_version_id=scope.id,
            artifact=artifact,
            proposal=proposal,
            rendered_proposal=rendered,
            agent_run_id=agent_run.id,
            scope_decision_id=decision.id,
            audit_record_ids=tuple(record.id for record in audit),
        )
        self._repository.create_or_get(
            collection="workflow_results",
            document_id=idempotency_key,
            payload=result.model_dump(mode="json"),
            unique_keys={"gmail_message_id": email.message_id},
            immutable=True,
        )
        return result

    def _transition_project(
        self,
        project: ProjectRecord,
        target: ProjectLifecycleStatus,
        *,
        reason: str,
        now: datetime,
        transitions: list[StateTransitionRecord],
    ) -> ProjectRecord:
        source = project.lifecycle_status
        transition_project(source, target)
        transitions.append(
            StateTransitionRecord(
                id=stable_id("transition", project.id, source.value, target.value),
                entity_type="project",
                entity_id=project.id,
                from_status=source.value,
                to_status=target.value,
                reason=reason,
                correlation_id=project.correlation_id,
                created_at=now,
            )
        )
        return project.model_copy(update={"lifecycle_status": target, "updated_at": now})

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

"""Deterministic routing for normalized inbound Gmail messages."""

from scopelock.domain.enums import AgentRoute, EmailDirection
from scopelock.domain.workflow_models import InboundEmail, ProjectRecord, RouteDecision
from scopelock.repositories.contracts import ApplicationRepository
from scopelock.repositories.model_store import CollectionName
from scopelock.services.idempotency_service import IdempotencyKeys
from scopelock.services.execution_boundaries import WorkflowExecutionBoundaries


class InboundMessageRouter:
    def __init__(self, repository: ApplicationRepository) -> None:
        self._repository = repository

    def route(self, email: InboundEmail) -> RouteDecision:
        if email.direction != EmailDirection.INBOUND:
            return RouteDecision(
                route=AgentRoute.IGNORE,
                reason=f"Message direction is {email.direction.value}",
            )
        if not email.message_id or not email.thread_id or not email.body.strip():
            return RouteDecision(
                route=AgentRoute.IGNORE,
                reason="Message has no usable inbound text or Gmail identity",
            )

        duplicate = WorkflowExecutionBoundaries.persistence(
            lambda: self._repository.find_by_unique_key(
                collection=CollectionName.INBOUND_RESULTS.value,
                key_name="gmail_message_id",
                key_value=IdempotencyKeys.gmail_message(email.message_id),
            )
        )
        if duplicate is not None:
            return RouteDecision(
                route=AgentRoute.IGNORE,
                reason="Gmail message was already persisted",
                duplicate=True,
            )

        project_document = WorkflowExecutionBoundaries.persistence(
            lambda: self._repository.find_by_unique_key(
                collection=CollectionName.PROJECTS.value,
                key_name="gmail_thread_id",
                key_value=IdempotencyKeys.gmail_thread(email.thread_id),
            )
        )
        if project_document is None:
            return RouteDecision(
                route=AgentRoute.REQUIREMENT_ANALYSIS,
                reason="Unknown Gmail thread has no project",
            )

        project = ProjectRecord.model_validate(project_document.payload)
        if project.active_scope_version_id is None:
            return RouteDecision(
                route=AgentRoute.REQUIREMENT_ANALYSIS,
                reason="Known intake has no authoritative proposed or accepted scope",
                project_id=project.id,
            )
        return RouteDecision(
            route=AgentRoute.SCOPE_ANALYSIS,
            reason="Known project has an active authoritative scope",
            project_id=project.id,
        )

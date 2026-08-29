"""Application-owned direct ADK invocation for bounded semantic agents."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from google.adk.events import Event
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import ValidationError

from app.agent import build_direct_app
from app.sub_agents.requirement_analyzer import PROMPT_VERSION as REQUIREMENT_PROMPT
from app.sub_agents.scope_analyzer import PROMPT_VERSION as SCOPE_PROMPT
from scopelock.domain.enums import AgentRoute, ScopeAnalysisStatus
from scopelock.domain.models import (
    AgentRun,
    AgentRunError,
    AgentRunStatus,
    RequirementAnalysis,
    ScopeAnalysis,
)
from scopelock.domain.workflow_models import AnalysisContext
from scopelock.services.adk_runtime import (
    extract_redacted_tool_actions,
    final_text_from_events,
)
from scopelock.services.execution_boundaries import WorkflowExecutionBoundaries
from scopelock.services.scope_analysis_policy import ScopeAnalysisPolicy
from scopelock.services.semantic_contracts import (
    SemanticContractViolation,
    validate_requirement_analysis,
)
from scopelock.services.sop_service import SOPCatalog
from scopelock.settings import model_name, project_id


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AdkAgentGateway:
    def __init__(self, catalog: SOPCatalog) -> None:
        self._catalog = catalog

    async def analyze_requirements(
        self,
        context: AnalysisContext,
        *,
        user_id: str = "scopelock-runtime",
        correlation_id: str | None = None,
    ) -> AgentRun:
        return await self._invoke(
            AgentRoute.REQUIREMENT_ANALYSIS,
            context,
            user_id=user_id,
            correlation_id=correlation_id,
        )

    async def analyze_scope(
        self,
        context: AnalysisContext,
        *,
        user_id: str = "scopelock-runtime",
        correlation_id: str | None = None,
    ) -> AgentRun:
        if context.current_scope is None:
            raise ValueError("Scope analysis requires an authoritative ScopeVersion")
        return await self._invoke(
            AgentRoute.SCOPE_ANALYSIS,
            context,
            user_id=user_id,
            correlation_id=correlation_id,
        )

    async def _invoke(
        self,
        route: AgentRoute,
        context: AnalysisContext,
        *,
        user_id: str,
        correlation_id: str | None,
    ) -> AgentRun:
        project_id()
        prompt_version = (
            REQUIREMENT_PROMPT
            if route == AgentRoute.REQUIREMENT_ANALYSIS
            else SCOPE_PROMPT
        )
        agent_name = (
            "requirement_analyzer"
            if route == AgentRoute.REQUIREMENT_ANALYSIS
            else "scope_analyzer"
        )
        run = AgentRun(
            id=str(uuid4()),
            correlation_id=correlation_id or str(uuid4()),
            project_id=(
                context.current_scope.project_id if context.current_scope else None
            ),
            trigger_type="gmail_message",
            trigger_ref=context.current_email.message_id,
            agent_name=agent_name,
            model=model_name(),
            prompt_version=prompt_version,
            started_at=_utc_now(),
            status=AgentRunStatus.RUNNING,
            input_hash=hashlib.sha256(
                json.dumps(
                    context.model_dump(mode="json"),
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
        )

        async def operation() -> tuple[list[Event], str | None]:
            direct_app = build_direct_app(route)
            session_service = InMemorySessionService()
            state = {
                "analysis_context": context.model_dump(mode="json"),
                "semantic_sop": context.semantic_sop,
            }
            session = await session_service.create_session(
                app_name=direct_app.name,
                user_id=user_id,
                state=state,
                session_id=run.correlation_id,
            )
            runner = Runner(app=direct_app, session_service=session_service)
            message = types.Content(
                role="user",
                parts=[types.Part(text=self._input_text(route, context))],
            )
            events: list[Event] = []
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session.id,
                new_message=message,
            ):
                events.append(event)
            return events, final_text_from_events(events)

        try:
            events, raw_output = await WorkflowExecutionBoundaries.model_async(operation)
            if raw_output is None:
                raise SemanticContractViolation("ADK returned no final structured output")
            output = self._validate(route, raw_output, context)
            return run.model_copy(
                update={
                    "completed_at": _utc_now(),
                    "status": AgentRunStatus.COMPLETED,
                    "output": output,
                    "tool_trajectory": extract_redacted_tool_actions(
                        events,
                        agent_run_id=run.id,
                    ),
                }
            )
        except (ValidationError, SemanticContractViolation, ValueError) as error:
            return run.model_copy(
                update={
                    "completed_at": _utc_now(),
                    "status": AgentRunStatus.NEEDS_REVIEW,
                    "error": AgentRunError(
                        category="INVALID_AGENT_OUTPUT",
                        message=str(error),
                        retryable=False,
                    ),
                }
            )
        except Exception as error:
            return run.model_copy(
                update={
                    "completed_at": _utc_now(),
                    "status": AgentRunStatus.FAILED,
                    "error": AgentRunError(
                        category=type(error).__name__,
                        message=str(error),
                        retryable=False,
                    ),
                }
            )

    def _validate(
        self,
        route: AgentRoute,
        raw_output: str,
        context: AnalysisContext,
    ) -> RequirementAnalysis | ScopeAnalysis:
        if route == AgentRoute.REQUIREMENT_ANALYSIS:
            analysis = RequirementAnalysis.model_validate_json(raw_output)
            validate_requirement_analysis(
                analysis,
                valid_module_keys={module.key for module in self._catalog.modules},
                expected_message_id=context.current_email.message_id,
                normalized_message_body=context.current_email.body,
                expected_sop_version=self._catalog.version,
                quantity_limits={
                    module.key: (module.quantity.minimum, module.quantity.maximum)
                    for module in self._catalog.modules
                },
            )
            return analysis

        analysis = ScopeAnalysis.model_validate_json(raw_output)
        scope = context.current_scope
        if scope is None:
            raise ValueError("Scope analysis requires authoritative context")
        decision = ScopeAnalysisPolicy(
            valid_module_keys={module.key for module in self._catalog.modules},
            quantity_limits={
                module.key: (module.quantity.minimum, module.quantity.maximum)
                for module in self._catalog.modules
            },
        ).evaluate(
            analysis,
            expected_message_id=context.current_email.message_id,
            normalized_message_body=context.current_email.body,
            expected_scope_version_id=scope.id,
            baseline_texts=tuple(item.description for item in scope.requirements),
            expected_sop_version=self._catalog.version,
        )
        if decision.status == ScopeAnalysisStatus.NEEDS_REVIEW:
            raise SemanticContractViolation(
                "Scope output failed application policy: "
                + "; ".join(decision.reasons)
            )
        return analysis

    @staticmethod
    def _input_text(route: AgentRoute, context: AnalysisContext) -> str:
        if route == AgentRoute.SCOPE_ANALYSIS:
            if context.current_scope is None:
                raise SemanticContractViolation(
                    "Scope analysis requires an active immutable scope"
                )
            return (
                f"CURRENT_MESSAGE_ID: {context.current_email.message_id}\n"
                f"PROJECT_ID: {context.current_scope.project_id}\n"
                "Analyze the immutable application-owned session context."
            )
        prior = [message.model_dump(mode="json") for message in context.prior_messages]
        return (
            f"CURRENT_MESSAGE_ID: {context.current_email.message_id}\n"
            f"SUBJECT: {context.current_email.subject}\n"
            f"BODY:\n{context.current_email.body}\n"
            "PRIOR_THREAD_CONTEXT_JSON:\n"
            + json.dumps(prior, ensure_ascii=False, separators=(",", ":"))
        )

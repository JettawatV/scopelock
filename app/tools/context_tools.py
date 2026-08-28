"""Read-only project-context tools, backed by fixtures during ADK development."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from google.adk.tools import ToolContext

from scopelock.domain.workflow_models import AnalysisContext


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCOPE_FIXTURE_PATH = (
    PROJECT_ROOT / "tests" / "fixtures" / "scope_analyzer_cases.json"
)


@lru_cache(maxsize=1)
def _scope_cases() -> dict[str, dict[str, Any]]:
    if not SCOPE_FIXTURE_PATH.exists():
        return {}
    payload = json.loads(SCOPE_FIXTURE_PATH.read_text(encoding="utf-8"))
    return {case["project_id"]: case for case in payload["cases"]}


def _session_context(tool_context: ToolContext) -> AnalysisContext | None:
    payload = tool_context.state.get("analysis_context")
    if not isinstance(payload, dict):
        return None
    return AnalysisContext.model_validate(payload)


def get_current_scope(project_id: str, tool_context: ToolContext) -> dict[str, Any]:
    """Return the authoritative per-run scope, with fixture fallback for ADK web."""
    context = _session_context(tool_context)
    if context is not None and context.current_scope is not None:
        scope = context.current_scope
        if scope.project_id != project_id:
            return {
                "project_id": project_id,
                "status": "context_mismatch",
                "scope_version": None,
            }
        return {
            "project_id": project_id,
            "status": scope.status.value,
            "scope_version_id": scope.id,
            "requirements": [
                {
                    "requirement_id": requirement.requirement_id,
                    "description": requirement.description,
                }
                for requirement in scope.requirements
            ],
            "module_selections": [
                item.model_dump(mode="json") for item in scope.module_selections
            ],
        }
    case = _scope_cases().get(project_id)
    if case is not None:
        baseline = case["baseline"]
        return {
            "project_id": project_id,
            "status": baseline["status"],
            "scope_version_id": baseline["scope_version_id"],
            "requirements": [
                {
                    "requirement_id": baseline["requirement_id"],
                    "description": baseline["text"],
                }
            ],
        }
    return {
        "project_id": project_id,
        "status": "fixture_only",
        "scope_version": None,
        "message": "No persisted project scope is available during local ADK development.",
    }


def get_recent_thread_context(
    project_id: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Return bounded per-run Gmail context, with fixture fallback for ADK web."""
    context = _session_context(tool_context)
    if context is not None:
        messages = [
            {
                "message_id": message.message_id,
                "direction": message.direction.value.casefold(),
                "sender_email": message.sender_email,
                "subject": message.subject,
                "text": message.body,
            }
            for message in context.prior_messages
        ]
        messages.append(
            {
                "message_id": context.current_email.message_id,
                "direction": context.current_email.direction.value.casefold(),
                "sender_email": context.current_email.sender_email,
                "subject": context.current_email.subject,
                "text": context.current_email.body,
            }
        )
        return {
            "project_id": project_id,
            "status": "session_context",
            "messages": messages,
        }
    case = _scope_cases().get(project_id)
    if case is not None:
        message = case["current_message"]
        return {
            "project_id": project_id,
            "status": "fixture_only",
            "messages": [
                {
                    "message_id": message["message_id"],
                    "direction": "inbound",
                    "text": message["text"],
                }
            ],
        }
    return {
        "project_id": project_id,
        "status": "fixture_only",
        "messages": [],
        "message": "No persisted Gmail thread is available during local ADK development.",
    }

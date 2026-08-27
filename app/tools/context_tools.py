"""Read-only project-context tools, backed by fixtures during ADK development."""

from typing import Any


def get_current_scope(project_id: str) -> dict[str, Any]:
    """Return scope context for a project; Phase 0 returns no persisted scope."""
    return {
        "project_id": project_id,
        "status": "fixture_only",
        "scope_version": None,
        "message": "No persisted project scope is available during local ADK development.",
    }


def get_recent_thread_context(project_id: str) -> dict[str, Any]:
    """Return Gmail thread context for a project; Phase 0 returns no messages."""
    return {
        "project_id": project_id,
        "status": "fixture_only",
        "messages": [],
        "message": "No persisted Gmail thread is available during local ADK development.",
    }


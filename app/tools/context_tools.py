"""Read-only project-context tools, backed by fixtures during ADK development."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


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


def get_current_scope(project_id: str) -> dict[str, Any]:
    """Return the accepted scope fixture for one local-development project."""
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


def get_recent_thread_context(project_id: str) -> dict[str, Any]:
    """Return the current Gmail fixture message for a local project."""
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

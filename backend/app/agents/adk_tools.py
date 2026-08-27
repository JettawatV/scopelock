"""Narrow, read-only tools exposed to ScopeLock agents during Phase 0/1."""

import os
from pathlib import Path
from typing import Any

from backend.app.services.sop_service import load_sop


def get_sop_catalog() -> dict[str, Any]:
    """Return the validated SOP catalog; never return secrets or credentials."""
    path = os.getenv("SCOPELOCK_SOP_PATH", "config/jvl_sop.example.yaml")
    return load_sop(path).model_dump(mode="json")


def get_current_scope(project_id: str) -> dict[str, Any]:
    """Return fixture scope context until Firestore repositories are implemented."""
    return {
        "project_id": project_id,
        "status": "fixture_only",
        "scope_version": None,
        "message": "No persisted project scope is available during local ADK development.",
    }


def get_recent_thread_context(project_id: str) -> dict[str, Any]:
    """Return fixture thread context until Gmail/Firestore integration is implemented."""
    return {
        "project_id": project_id,
        "status": "fixture_only",
        "messages": [],
        "message": "No persisted Gmail thread is available during local ADK development.",
    }


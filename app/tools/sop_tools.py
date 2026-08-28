"""Read-only SOP tools for ScopeLock agents."""

import os
from pathlib import Path
from typing import Any

from google.adk.tools import ToolContext

from scopelock.services.sop_service import load_sop


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def get_sop_catalog(tool_context: ToolContext) -> dict[str, Any]:
    """Return the validated service catalog used for requirement mapping.

    This semantic projection intentionally excludes all price and duration
    rules. Commerce remains application-owned deterministic code.
    """
    session_catalog = tool_context.state.get("semantic_sop")
    if isinstance(session_catalog, dict):
        return session_catalog
    configured_path = os.getenv("SCOPELOCK_SOP_PATH")
    path = Path(configured_path) if configured_path else PROJECT_ROOT / "config" / "jvl_sop.example.yaml"
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return load_sop(path).semantic_view()

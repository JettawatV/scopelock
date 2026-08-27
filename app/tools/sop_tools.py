"""Read-only SOP tools for ScopeLock agents."""

import os
from pathlib import Path
from typing import Any

from scopelock.services.sop_service import load_sop


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def get_sop_catalog() -> dict[str, Any]:
    """Return the validated service catalog used for requirement mapping.

    The catalog includes module keys, included/excluded work, price rules, and
    duration rules. Agents may use it for semantic mapping but must never
    calculate prices or timelines.
    """
    configured_path = os.getenv("SCOPELOCK_SOP_PATH")
    path = Path(configured_path) if configured_path else PROJECT_ROOT / "config" / "jvl_sop.example.yaml"
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return load_sop(path).model_dump(mode="json")


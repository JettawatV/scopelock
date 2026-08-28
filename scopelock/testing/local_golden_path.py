"""Reviewed local fixture loader used by the deterministic vertical rehearsal."""

import json
from pathlib import Path
from typing import Any

from scopelock.domain.models import RequirementAnalysis
from scopelock.domain.workflow_models import InboundEmail


DEFAULT_FIXTURE_PATH = Path("tests/fixtures/local_golden_path.json")


def load_local_golden_fixture(
    path: str | Path = DEFAULT_FIXTURE_PATH,
) -> tuple[InboundEmail, RequirementAnalysis, dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return (
        InboundEmail.model_validate(payload["initial_email"]),
        RequirementAnalysis.model_validate(payload["requirement_analysis"]),
        payload["followups"],
    )

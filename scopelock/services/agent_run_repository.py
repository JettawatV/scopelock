"""Application-owned local persistence for agent-run audit records."""

from pathlib import Path

from scopelock.domain.models import AgentRun
from scopelock.settings import PROJECT_ROOT


class JsonAgentRunRepository:
    """Persist one run bundle without relying on ADK's internal session format."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root is not None else PROJECT_ROOT / "artifacts" / "agent_runs"

    def save(self, run: AgentRun) -> Path:
        run_directory = self.root / run.id
        run_directory.mkdir(parents=True, exist_ok=True)

        run_path = run_directory / "agent_run.json"
        run_temp_path = run_directory / "agent_run.json.tmp"
        run_temp_path.write_text(run.model_dump_json(indent=2), encoding="utf-8")
        run_temp_path.replace(run_path)

        actions_path = run_directory / "tool_actions.jsonl"
        actions_temp_path = run_directory / "tool_actions.jsonl.tmp"
        actions_temp_path.write_text(
            "".join(f"{action.model_dump_json()}\n" for action in run.tool_trajectory),
            encoding="utf-8",
        )
        actions_temp_path.replace(actions_path)
        return run_path

"""Validated ADK execution with application-owned run and tool records."""

import argparse
import asyncio
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from google.adk.events import Event
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import ValidationError

from app.agent import app
from app.sub_agents.requirement_analyzer import PROMPT_VERSION
from scopelock.domain.models import (
    AgentRun,
    AgentRunError,
    AgentRunStatus,
    RequirementAnalysis,
    ToolAction,
    ToolActionPhase,
    ToolActionStatus,
)
from scopelock.services.agent_run_repository import JsonAgentRunRepository
from scopelock.services.adk_runtime import (
    extract_redacted_tool_actions,
    final_text_from_events as _final_text_from_events,
)
from scopelock.services.semantic_contracts import (
    SemanticContractViolation,
    validate_requirement_analysis,
)
from scopelock.services.sop_service import load_sop
from scopelock.settings import PROJECT_ROOT, model_name, project_id


class InvalidRequirementOutput(ValueError):
    """The model completed, but its business-critical output is not safe to use."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def configure_utf8_stdout(stream=None) -> None:
    """Make Windows CLI output safe for Thai and other Unicode text."""

    target = stream or sys.stdout
    if hasattr(target, "reconfigure"):
        target.reconfigure(encoding="utf-8", errors="replace")


def create_agent_run(
    email_text: str,
    *,
    trigger_type: str = "phase_zero_cli",
    trigger_ref: str = "current_email",
) -> AgentRun:
    return AgentRun(
        id=str(uuid4()),
        correlation_id=str(uuid4()),
        trigger_type=trigger_type,
        trigger_ref=trigger_ref,
        agent_name="requirement_analyzer",
        model=model_name(),
        prompt_version=PROMPT_VERSION,
        started_at=utc_now(),
        status=AgentRunStatus.RUNNING,
        input_hash=hashlib.sha256(email_text.encode("utf-8")).hexdigest(),
    )


def validate_requirement_output(
    raw_output: str,
    *,
    valid_module_keys: set[str],
    quantity_limits: dict[str, tuple[int, int]] | None = None,
) -> RequirementAnalysis:
    try:
        analysis = RequirementAnalysis.model_validate_json(raw_output)
    except ValidationError as exc:
        raise InvalidRequirementOutput(
            f"RequirementAnalysis validation failed with {len(exc.errors())} error(s)"
        ) from exc

    try:
        validate_requirement_analysis(
            analysis,
            valid_module_keys=valid_module_keys,
            quantity_limits=quantity_limits,
        )
    except SemanticContractViolation as exc:
        raise InvalidRequirementOutput(
            f"RequirementAnalysis semantic contract failed: {exc}"
        ) from exc
    return analysis


def complete_agent_run(
    run: AgentRun,
    raw_output: str,
    *,
    valid_module_keys: set[str],
    quantity_limits: dict[str, tuple[int, int]] | None = None,
) -> AgentRun:
    try:
        analysis = validate_requirement_output(
            raw_output,
            valid_module_keys=valid_module_keys,
            quantity_limits=quantity_limits,
        )
    except InvalidRequirementOutput as exc:
        return run.model_copy(
            update={
                "completed_at": utc_now(),
                "status": AgentRunStatus.NEEDS_REVIEW,
                "output": None,
                "error": AgentRunError(
                    category="INVALID_REQUIREMENT_OUTPUT",
                    message=str(exc),
                    retryable=False,
                ),
            }
        )

    return run.model_copy(
        update={
            "completed_at": utc_now(),
            "status": AgentRunStatus.COMPLETED,
            "output": analysis,
            "error": None,
        }
    )


def fail_agent_run(run: AgentRun, exc: Exception) -> AgentRun:
    return run.model_copy(
        update={
            "completed_at": utc_now(),
            "status": AgentRunStatus.FAILED,
            "output": None,
            "error": AgentRunError(
                category=type(exc).__name__,
                message=str(exc),
                retryable=False,
            ),
        }
    )


def extract_tool_actions(
    event: Event,
    *,
    agent_run_id: str,
    starting_sequence: int,
) -> list[ToolAction]:
    actions = extract_redacted_tool_actions([event], agent_run_id=agent_run_id)
    return [
        action.model_copy(update={"sequence": starting_sequence + index})
        for index, action in enumerate(actions)
    ]


def final_text_from_events(events: Iterable[Event]) -> str | None:
    return _final_text_from_events(events)


def configured_sop_path() -> Path:
    from os import getenv

    configured = getenv("SCOPELOCK_SOP_PATH")
    path = Path(configured) if configured else PROJECT_ROOT / "config" / "jvl_sop.example.yaml"
    return path if path.is_absolute() else PROJECT_ROOT / path


async def run_requirement_analysis(
    email_text: str,
    *,
    repository: JsonAgentRunRepository | None = None,
    user_id: str = "phase-zero",
) -> AgentRun:
    repository = repository or JsonAgentRunRepository()
    run = create_agent_run(email_text)
    events: list[Event] = []

    try:
        project_id()
        catalog = load_sop(configured_sop_path())
        session_service = InMemorySessionService()
        session = await session_service.create_session(
            app_name=app.name,
            user_id=user_id,
            session_id=run.correlation_id,
            state={"semantic_sop": catalog.semantic_view()},
        )
        runner = Runner(app=app, session_service=session_service)
        new_message = types.Content(
            role="user",
            parts=[types.Part(text=email_text)],
        )

        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=new_message,
        ):
            events.append(event)

        run.tool_trajectory = extract_redacted_tool_actions(
            events,
            agent_run_id=run.id,
        )

        raw_output = final_text_from_events(events)
        if raw_output is None:
            raise InvalidRequirementOutput(
                "ADK completed without a final RequirementAnalysis response"
            )
        run = complete_agent_run(
            run,
            raw_output,
            valid_module_keys={module.key for module in catalog.modules},
            quantity_limits={
                module.key: (module.quantity.minimum, module.quantity.maximum)
                for module in catalog.modules
            },
        )
    except InvalidRequirementOutput as exc:
        run = run.model_copy(
            update={
                "completed_at": utc_now(),
                "status": AgentRunStatus.NEEDS_REVIEW,
                "output": None,
                "error": AgentRunError(
                    category="INVALID_REQUIREMENT_OUTPUT",
                    message=str(exc),
                    retryable=False,
                ),
            }
        )
    except Exception as exc:
        run = fail_agent_run(run, exc)

    repository.save(run)
    return run


def main() -> None:
    configure_utf8_stdout()
    parser = argparse.ArgumentParser(
        description="Run ScopeLock Requirement Analyzer with application-owned audit records."
    )
    parser.add_argument("query", nargs="?")
    parser.add_argument("--email-file", type=Path)
    parser.add_argument("--record-dir", type=Path)
    args = parser.parse_args()

    if args.email_file is not None and args.query is not None:
        parser.error("Use either query or --email-file, not both")
    if args.email_file is not None:
        email_text = args.email_file.read_text(encoding="utf-8")
    elif args.query is not None:
        email_text = args.query
    else:
        parser.error("Provide an email query or --email-file")

    repository = JsonAgentRunRepository(args.record_dir)
    run = asyncio.run(
        run_requirement_analysis(
            email_text,
            repository=repository,
        )
    )
    print(run.model_dump_json(indent=2))
    if run.status == AgentRunStatus.NEEDS_REVIEW:
        raise SystemExit(2)
    if run.status != AgentRunStatus.COMPLETED:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

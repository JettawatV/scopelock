"""Run the Requirement Analyzer through Google ADK and validate its contract."""

import argparse
import asyncio
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from backend.app.agents.adk_tools import (
    get_current_scope,
    get_recent_thread_context,
    get_sop_catalog,
)
from backend.app.domain.models import RequirementAnalysis
from backend.app.services.sop_service import load_sop


def _json_default(value: Any) -> str:
    return repr(value)


def build_agent(model: str) -> Agent:
    return Agent(
        name="requirement_analyzer",
        model=model,
        output_schema=RequirementAnalysis,
        instruction=(
            "You are ScopeLock's Requirement Analyzer. Extract project requirements "
            "from the client email and map them only to valid SOP module keys. "
            "Never invent prices or calculate totals. Every requirement and module "
            "selection must include concise evidence. If critical information is "
            "missing, list it and set proposal_ready false. Return only the required "
            "structured output. Retrieve the catalog with get_sop_catalog; do not "
            "calculate or invent price."
        ),
        tools=[get_sop_catalog, get_current_scope, get_recent_thread_context],
    )


async def run_requirement_analysis(email_text: str, sop_path: str, model: str) -> dict[str, Any]:
    catalog = load_sop(sop_path)
    correlation_id = str(uuid4())
    input_hash = hashlib.sha256(email_text.encode("utf-8")).hexdigest()
    prompt_version = os.getenv("SCOPELOCK_PROMPT_VERSION", "requirement_analyzer_v1")
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="scopelock", user_id="phase-zero", session_id=correlation_id
    )
    runner = Runner(
        app_name="scopelock",
        agent=build_agent(model),
        session_service=session_service,
    )
    content = types.Content(role="user", parts=[types.Part(text=email_text)])
    events: list[dict[str, Any]] = []
    final_output: RequirementAnalysis | None = None
    started_at = datetime.now(timezone.utc).isoformat()
    try:
        async for event in runner.run_async(
            user_id="phase-zero", session_id=session.id, new_message=content
        ):
            event_record = {
                "author": getattr(event, "author", None),
                "is_final_response": bool(event.is_final_response()) if hasattr(event, "is_final_response") else False,
                "content": event.content.model_dump(mode="json") if getattr(event, "content", None) else None,
            }
            events.append(event_record)
            if event_record["is_final_response"] and event.content:
                text_parts = [part.text for part in (event.content.parts or []) if getattr(part, "text", None)]
                if text_parts:
                    final_output = RequirementAnalysis.model_validate_json("".join(text_parts))
        if final_output is None:
            raise RuntimeError("ADK completed without a final RequirementAnalysis response")
        valid_keys = {module.key for module in catalog.modules}
        invalid_keys = [item.module_key for item in final_output.selected_sop_modules if item.module_key not in valid_keys]
        if invalid_keys:
            raise ValueError(f"Agent selected unknown SOP modules: {invalid_keys}")
        status = "completed"
        error = None
        output = final_output.model_dump(mode="json")
    except Exception as exc:
        status = "failed"
        error = f"{type(exc).__name__}: {exc}"
        output = None
    return {
        "agent_name": "requirement_analyzer",
        "model": model,
        "prompt_version": prompt_version,
        "correlation_id": correlation_id,
        "trigger_type": "phase_zero_cli",
        "input_hash": input_hash,
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "output": output,
        "tool_trajectory": events,
        "error": error,
    }


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--email-file", type=Path)
    parser.add_argument("--sop", default=os.getenv("SCOPELOCK_SOP_PATH", "config/jvl_sop.example.yaml"))
    parser.add_argument("--model", default=os.getenv("SCOPELOCK_MODEL", "gemini-3.5-flash"))
    args = parser.parse_args()
    email = args.email_file.read_text(encoding="utf-8") if args.email_file else (
        "We want to automate incoming customer requests, store structured data, "
        "show an operations dashboard, and send email notifications for manual review."
    )
    result = asyncio.run(run_requirement_analysis(email, args.sop, args.model))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

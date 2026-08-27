import asyncio
import hashlib
import json

from google.adk.events import Event
from google.genai import types

from app.sub_agents.requirement_analyzer import PROMPT_VERSION
from scopelock.adk_runner import (
    complete_agent_run,
    create_agent_run,
    extract_tool_actions,
    run_requirement_analysis,
)
from scopelock.domain.models import (
    AgentRunStatus,
    ToolActionPhase,
    ToolActionStatus,
)
from scopelock.services.agent_run_repository import JsonAgentRunRepository


def valid_output(module_key: str = "email_intake") -> str:
    return json.dumps(
        {
            "is_project_request": True,
            "project_title": "Shared inbox automation",
            "objective": "Automate inbound Gmail requests.",
            "requirements": [
                {
                    "requirement_id": "REQ-01",
                    "category": "Intake",
                    "description": "Read inbound Gmail messages.",
                    "normalized_key": "gmail_intake",
                    "source_quote": "Automate our shared Gmail inbox.",
                }
            ],
            "selected_sop_modules": [
                {
                    "module_key": module_key,
                    "quantity": 1,
                    "mapped_requirement": "REQ-01: Read inbound Gmail messages.",
                    "confidence": 0.95,
                    "evidence": [
                        {
                            "source_type": "gmail",
                            "source_id": "current_email",
                            "quote_or_rule": "Automate our shared Gmail inbox.",
                        },
                        {
                            "source_type": "sop",
                            "source_id": module_key,
                            "quote_or_rule": "Read and process inbound Gmail messages.",
                        },
                    ],
                }
            ],
            "assumptions": [],
            "exclusions_to_surface": [],
            "missing_critical_information": [],
            "proposal_ready": True,
            "confidence": 0.95,
            "evidence": [
                {
                    "source_type": "gmail",
                    "source_id": "current_email",
                    "quote_or_rule": "Automate our shared Gmail inbox.",
                }
            ],
        }
    )


def test_completed_agent_run_records_required_metadata():
    email = "Automate our shared Gmail inbox."
    run = create_agent_run(email)
    completed = complete_agent_run(
        run,
        valid_output(),
        valid_module_keys={"email_intake"},
    )

    assert completed.status == AgentRunStatus.COMPLETED
    assert completed.correlation_id
    assert completed.agent_name == "requirement_analyzer"
    assert completed.model
    assert completed.prompt_version == PROMPT_VERSION
    assert completed.input_hash == hashlib.sha256(email.encode("utf-8")).hexdigest()
    assert completed.output is not None
    assert completed.error is None
    assert completed.started_at is not None
    assert completed.completed_at is not None


def test_invalid_output_becomes_needs_review():
    run = create_agent_run("This model output will be malformed.")
    completed = complete_agent_run(
        run,
        '{"project_title": 42}',
        valid_module_keys={"email_intake"},
    )

    assert completed.status == AgentRunStatus.NEEDS_REVIEW
    assert completed.output is None
    assert completed.error is not None
    assert completed.error.category == "INVALID_REQUIREMENT_OUTPUT"
    assert "validation failed" in completed.error.message


def test_unknown_sop_module_becomes_needs_review():
    run = create_agent_run("Please add teleportation.")
    completed = complete_agent_run(
        run,
        valid_output("teleportation"),
        valid_module_keys={"email_intake"},
    )

    assert completed.status == AgentRunStatus.NEEDS_REVIEW
    assert completed.error is not None
    assert "unknown SOP module" in completed.error.message


def test_unexpected_commercial_field_becomes_needs_review():
    raw_output = json.loads(valid_output())
    raw_output["price_usd"] = 500
    run = create_agent_run("Please price this project.")
    completed = complete_agent_run(
        run,
        json.dumps(raw_output),
        valid_module_keys={"email_intake"},
    )

    assert completed.status == AgentRunStatus.NEEDS_REVIEW
    assert completed.output is None
    assert completed.error is not None
    assert completed.error.category == "INVALID_REQUIREMENT_OUTPUT"


def test_tool_actions_and_run_bundle_are_application_owned(tmp_path):
    run = create_agent_run("Automate our shared Gmail inbox.")
    call = Event(
        id="event-call",
        author="requirement_analyzer",
        content=types.Content(
            role="model",
            parts=[
                types.Part(
                    function_call=types.FunctionCall(
                        id="call-1",
                        name="get_sop_catalog",
                        args={},
                    )
                )
            ],
        ),
    )
    result = Event(
        id="event-result",
        author="requirement_analyzer",
        content=types.Content(
            role="user",
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        id="call-1",
                        name="get_sop_catalog",
                        response={"modules": [{"key": "email_intake"}]},
                    )
                )
            ],
        ),
    )

    actions = extract_tool_actions(
        call,
        agent_run_id=run.id,
        starting_sequence=1,
    )
    actions.extend(
        extract_tool_actions(
            result,
            agent_run_id=run.id,
            starting_sequence=2,
        )
    )
    run = run.model_copy(update={"tool_trajectory": actions})
    run = complete_agent_run(
        run,
        valid_output(),
        valid_module_keys={"email_intake"},
    )

    record_path = JsonAgentRunRepository(tmp_path).save(run)
    actions_path = record_path.parent / "tool_actions.jsonl"
    persisted = json.loads(record_path.read_text(encoding="utf-8"))
    action_lines = actions_path.read_text(encoding="utf-8").splitlines()

    assert persisted["id"] == run.id
    assert len(action_lines) == 2
    assert actions[0].phase == ToolActionPhase.CALL
    assert actions[0].status == ToolActionStatus.REQUESTED
    assert actions[1].phase == ToolActionPhase.RESULT
    assert actions[1].status == ToolActionStatus.COMPLETED
    assert actions[0].call_id == actions[1].call_id == "call-1"


def test_missing_configuration_records_failed_run_without_tools(tmp_path, monkeypatch):
    def missing_project():
        raise RuntimeError("GOOGLE_CLOUD_PROJECT is missing from test configuration")

    monkeypatch.setattr("scopelock.adk_runner.project_id", missing_project)
    repository = JsonAgentRunRepository(tmp_path)
    run = asyncio.run(
        run_requirement_analysis(
            "Automate our shared Gmail inbox.",
            repository=repository,
        )
    )

    assert run.status == AgentRunStatus.FAILED
    assert run.output is None
    assert run.tool_trajectory == []
    assert run.error is not None
    assert run.error.category == "RuntimeError"
    assert "GOOGLE_CLOUD_PROJECT is missing" in run.error.message
    assert (tmp_path / run.id / "agent_run.json").exists()

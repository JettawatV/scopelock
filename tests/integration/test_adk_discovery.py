import subprocess
import sys
import inspect
from pathlib import Path

import app as app_package
from app.agent import app, build_direct_app, root_agent
from app.sub_agents.requirement_analyzer import PROMPT_VERSION, requirement_analyzer
from app.sub_agents.scope_analyzer import (
    PROMPT_VERSION as SCOPE_PROMPT_VERSION,
    scope_analyzer,
)
from scopelock.domain.enums import AgentRoute
from scopelock.services.adk_agent_gateway import AdkAgentGateway


def test_app_package_exposes_agent_module_for_adk_eval():
    assert app_package.agent.root_agent is root_agent
    assert app_package.agent.app is app
    assert app_package.agent.app.name == "app"


def test_adk_eval_loader_discovers_root_agent_once():
    script = (
        "import asyncio\n"
        "from pathlib import Path\n"
        "from google.adk.cli.cli_eval import get_app_or_root_agent\n"
        "loaded_app, loaded_agent = asyncio.run("
        "get_app_or_root_agent(str(Path('app').resolve())))\n"
        "assert loaded_app is not None\n"
        "assert loaded_app.name == 'app'\n"
        "assert loaded_agent.name == 'scopelock'\n"
        "print('ok')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_root_agent_exposes_scope_lock_hierarchy():
    assert app.name == "app"
    assert root_agent.name == "scopelock"
    assert [agent.name for agent in root_agent.sub_agents] == [
        "requirement_analyzer",
        "scope_analyzer",
    ]
    requirement_tool_names = {
        tool.__name__ for tool in requirement_analyzer.tools
    }
    scope_tool_names = {tool.__name__ for tool in scope_analyzer.tools}
    assert requirement_tool_names == {"get_sop_catalog"}
    assert scope_tool_names == {
        "get_current_scope",
        "get_recent_thread_context",
        "get_sop_catalog",
    }
    assert all(
        "send" not in tool_name
        for tool_name in requirement_tool_names | scope_tool_names
    )


def test_production_gateway_uses_direct_deterministic_sub_agent_routes():
    assert build_direct_app(AgentRoute.REQUIREMENT_ANALYSIS).root_agent.name == (
        "requirement_analyzer"
    )
    assert build_direct_app(AgentRoute.SCOPE_ANALYSIS).root_agent.name == "scope_analyzer"
    assert "EXISTING_PROJECT" not in inspect.getsource(AdkAgentGateway._input_text)


def test_requirement_analyzer_contains_golden_readiness_policy():
    assert PROMPT_VERSION == "requirement_analyzer_v5"
    assert "supported mappings" in requirement_analyzer.instruction
    assert "proposal_ready is true only" in requirement_analyzer.instruction
    assert "source language" in requirement_analyzer.instruction
    assert "Never calculate or promise a project total" in requirement_analyzer.instruction
    assert "Ordinary coordination, automated mail, social mail" in requirement_analyzer.instruction


def test_scope_analyzer_has_typed_read_only_scope_policy():
    assert SCOPE_PROMPT_VERSION == "scope_analyzer_v3"
    assert scope_analyzer.output_schema.__name__ == "ScopeAnalysis"
    assert "get_current_scope(project_id)" in scope_analyzer.instruction
    assert "get_recent_thread_context(project_id)" in scope_analyzer.instruction
    assert "get_sop_catalog()" in scope_analyzer.instruction
    assert "CLOSURE" in scope_analyzer.instruction
    assert "up to ten events" in scope_analyzer.instruction
    assert "Never calculate, estimate, or promise commerce" in scope_analyzer.instruction
    assert "Never mutate state" in scope_analyzer.instruction

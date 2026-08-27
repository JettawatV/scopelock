import subprocess
import sys
from pathlib import Path

import app as app_package
from app.agent import app, root_agent
from app.sub_agents.requirement_analyzer import PROMPT_VERSION, requirement_analyzer


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
    assert [agent.name for agent in root_agent.sub_agents] == ["requirement_analyzer"]
    assert len(root_agent.sub_agents[0].tools) == 3
    tool_names = {tool.__name__ for tool in root_agent.sub_agents[0].tools}
    assert tool_names == {
        "get_current_scope",
        "get_recent_thread_context",
        "get_sop_catalog",
    }
    assert all("send" not in tool_name for tool_name in tool_names)


def test_requirement_analyzer_contains_golden_readiness_policy():
    assert PROMPT_VERSION == "requirement_analyzer_v2"
    assert "standard golden-path request" in requirement_analyzer.instruction
    assert "Set proposal_ready to true" in requirement_analyzer.instruction
    assert "mapped_requirement must contain both" in requirement_analyzer.instruction
    assert "Never calculate, mention, estimate, or invent price" in requirement_analyzer.instruction
    assert "Ordinary coordination, lunch, social, or other non-project mail" in requirement_analyzer.instruction

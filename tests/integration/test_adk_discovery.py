from app.agent import app, root_agent
from app.sub_agents.requirement_analyzer import PROMPT_VERSION, requirement_analyzer


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

from app.agent import root_agent


def test_root_agent_exposes_scope_lock_hierarchy():
    assert root_agent.name == "scopelock"
    assert [agent.name for agent in root_agent.sub_agents] == ["requirement_analyzer"]
    assert len(root_agent.sub_agents[0].tools) == 3


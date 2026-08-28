"""Mirror the production gateway's direct Scope Analyzer selection."""

from app.sub_agents.scope_analyzer import build_scope_analyzer


root_agent = build_scope_analyzer()

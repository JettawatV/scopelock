"""Mirror the production gateway's direct Requirement Analyzer selection."""

from app.sub_agents.requirement_analyzer import build_requirement_analyzer


root_agent = build_requirement_analyzer()

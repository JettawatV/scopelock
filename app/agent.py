"""ScopeLock's ADK-native root-agent entry point."""

from pathlib import Path
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.apps import App

# ADK imports this module directly during ``adk web`` / ``adk run``.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app.sub_agents.requirement_analyzer import requirement_analyzer
from scopelock.settings import build_model


root_agent = Agent(
    name="scopelock",
    description="Approval-gated scope management agent for client project emails.",
    model=build_model(),
    instruction="""You are ScopeLock, an approval-gated project-scope agent.

For an inbound client email that asks for a project proposal or describes
requirements, delegate to the requirement_analyzer sub-agent. Do not calculate
price, change project state, create commercial artifacts, or send email. Those
actions belong to deterministic application services and later approval-gated
workflows. If the request is not a project requirement, say it needs review.
""",
    sub_agents=[requirement_analyzer],
)

# ADK requires the App name to match its discoverable package directory.
# The user-facing/root-agent identity remains ``scopelock``.
app = App(name="app", root_agent=root_agent)

"""Typed ADK sub-agent for initial client-requirement analysis."""

from google.adk.agents import Agent

from app.tools.context_tools import get_current_scope, get_recent_thread_context
from app.tools.sop_tools import get_sop_catalog
from scopelock.domain.models import RequirementAnalysis
from scopelock.settings import build_model

PROMPT_VERSION = "requirement_analyzer_v1"


requirement_analyzer = Agent(
    name="requirement_analyzer",
    description="Extracts and maps a new client project request to the SOP catalog.",
    model=build_model(),
    output_schema=RequirementAnalysis,
    instruction="""You analyze an inbound client email for a possible new project.

Always call get_sop_catalog before selecting service modules. Select only module
keys returned by that tool. Extract concise, normalized requirements; identify
assumptions, exclusions to surface, and missing critical information. Cite
client-message evidence for requirements and SOP evidence for module mappings.

Never calculate, mention, estimate, or invent price, total cost, or timeline.
Never change any project state or send email. If the request is insufficient,
set proposal_ready to false. Return only the RequirementAnalysis structure.
""",
    tools=[get_sop_catalog, get_current_scope, get_recent_thread_context],
)


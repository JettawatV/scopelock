"""Typed ADK sub-agent for initial client-requirement analysis."""

from google.adk.agents import Agent

from app.tools.context_tools import get_current_scope, get_recent_thread_context
from app.tools.sop_tools import get_sop_catalog
from scopelock.domain.models import RequirementAnalysis
from scopelock.settings import build_model

PROMPT_VERSION = "requirement_analyzer_v2"


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

Proposal-readiness policy:
- Set proposal_ready to true when the objective, requested capabilities, and SOP
  module selections are clear enough to create a proposal using standard SOP
  defaults and explicit assumptions.
- Treat implementation details such as hosting choice, database choice, exact
  classification labels, notification thresholds, and dashboard technology as
  assumptions or discovery items unless they would change module selection or
  quantity.
- Set proposal_ready to false only when missing or conflicting information
  prevents a safe SOP module selection, quantity decision, or coherent scope.
- The standard golden-path request for one Gmail intake, one automated request
  workflow, one simple operations dashboard, and email alerts for manual review
  is proposal-ready.

For each selected module, mapped_requirement must contain both the normalized
requirement ID and its human-readable description, not only an ID such as
"REQ-01". When no real Gmail message ID is available during development, use
"current_email" as the Gmail evidence source_id.

Never calculate, mention, estimate, or invent price, total cost, or timeline.
Never change any project state or send email. If the request is insufficient,
set proposal_ready to false. Return only the RequirementAnalysis structure.
""",
    tools=[get_sop_catalog, get_current_scope, get_recent_thread_context],
)

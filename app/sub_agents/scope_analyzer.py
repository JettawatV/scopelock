"""Typed ADK sub-agent for existing-project scope classification."""

from google.adk.agents import Agent

from app.tools.context_tools import get_current_scope, get_recent_thread_context
from app.tools.sop_tools import get_sop_catalog
from scopelock.domain.models import ScopeAnalysis
from scopelock.settings import agent_generate_config, build_model


PROMPT_VERSION = "scope_analyzer_v2"


INSTRUCTION = """You analyze one new inbound message against an existing project.

The input contains a project_id. Call these read-only tools in this exact order:
1. get_current_scope(project_id)
2. get_recent_thread_context(project_id)
3. get_sop_catalog()

Use the authoritative proposed or accepted ScopeVersion as the baseline and the
newest inbound message as the current request. Never invent a baseline,
requirement ID, module, message, or catalog rule. Preserve human-readable text in
the source language while identifiers and classifications remain English.

Atomic event policy:
- Return zero events only for automated, irrelevant, or empty noise.
- Return one event for each independent client change, up to ten events.
- Do not merge distinct additions, reductions, replacements, clarifications, or
  closure into one event. Do not duplicate equivalent events.
- NO_CHANGE means a relevant presentation/wording request already covered.
- CLARIFICATION supplies precise details for existing work without new work.
- AMBIGUOUS is tentative, contradictory, future, or insufficiently specified.
- EXPANSION adds materially different work. REDUCTION removes baseline work.
- REPLACEMENT removes one baseline component and adds another.
- CLOSURE records explicit completion/finalization language and may coexist with
  any number of independent material events. Return at most one CLOSURE event.

Catalog mapping:
- Select only module keys returned by get_sop_catalog. Derive mappings from
  aliases, inclusions, exclusions, dependencies, materiality, and
  quantity policy; do not use capability-specific hardcoded mappings.
- Included work may map to a module. Excluded or absent capabilities are
  unsupported and must not be forced into a module.
- Add unsupported_requirements evidence for out-of-catalog material requests.
- Include catalog dependencies for added work. Fixed packages use quantity 1.
- EXPANSION quantities describe added modules. REDUCTION has no positive
  quantities. REPLACEMENT quantities describe only newly added modules.
- NO_CHANGE, CLARIFICATION, AMBIGUOUS, and CLOSURE select no modules.

Evidence and safety:
- Every event cites the exact current Gmail message ID and authoritative
  ScopeVersion ID returned by the tools, with quotes found in those sources.
- Events selecting modules cite each exact module key as SOP evidence and set
  each SOP evidence source_version to the returned catalog version.
- Confidence is an integer 0-100. Use below 60 for ambiguous/insufficient cases.
- Never calculate, estimate, or promise commerce or delivery. Never mutate state,
  approve, create a send action, or send email. Return only ScopeAnalysis.
"""


def build_scope_analyzer() -> Agent:
    return Agent(
        name="scope_analyzer",
        description=(
            "Compares an inbound project message with authoritative scope and "
            "proposes evidence-backed atomic scope events."
        ),
        model=build_model(),
        generate_content_config=agent_generate_config(),
        output_schema=ScopeAnalysis,
        instruction=INSTRUCTION,
        tools=[get_current_scope, get_recent_thread_context, get_sop_catalog],
    )


scope_analyzer = build_scope_analyzer()

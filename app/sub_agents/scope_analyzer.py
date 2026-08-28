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
  closure into one event. Treat separately stated clauses, including clauses
  separated by punctuation or conjunctions, as independent when each changes a
  different requirement detail, even when several events have the same
  classification. Do not summarize a list of independently editable fields or
  actions into one event. Do not duplicate equivalent events.
- Before responding, count the independent imperative clauses in the newest
  message and verify that each appears in exactly one event. For example,
  "set A; rename B; filter by C; and color D" requires four events, not one
  summary event. A message with ten independent clauses requires ten events.
- NO_CHANGE means a relevant presentation, branding, label, title, color, or
  wording request already covered by the baseline package.
- CLARIFICATION supplies precise details for existing work without new work.
- AMBIGUOUS is tentative, contradictory, future, or insufficiently specified.
- A grammatically complete capability request is not AMBIGUOUS merely because
  it is phrased as a question. Explicit future language, deferral, or a request
  not to include/quote the work yet is AMBIGUOUS.
- EXPANSION adds materially different work. REDUCTION removes baseline work.
- REPLACEMENT removes one baseline component and adds another.
- Use REPLACEMENT only for one explicitly substitutive change such as "replace"
  or "instead of". When the client separately says to remove one item and add
  another, return independent REDUCTION and EXPANSION events.
- A separately stated recipient, schedule, category, filter, label, or other
  operational value is its own CLARIFICATION event, including when it follows a
  material event and describes the newly requested work.
- CLOSURE records explicit completion/finalization language and may coexist with
  any number of independent material events. Return at most one CLOSURE event.

Catalog mapping:
- Select only module keys returned by get_sop_catalog. Derive mappings from
  aliases, inclusions, exclusions, dependencies, materiality, and
  quantity policy; do not use capability-specific hardcoded mappings.
- Included work may map to a module. Excluded or absent capabilities are
  unsupported and must not be forced into a module.
- Add unsupported_requirements evidence for out-of-catalog material requests.
- A concrete material request remains EXPANSION even when it has no matching
  module; leave module keys empty and record it under unsupported_requirements.
- Include catalog dependencies for added work. Fixed packages use quantity 1.
- EXPANSION module keys and quantities describe added modules. REDUCTION module
  keys identify removed modules but quantities stay empty. REPLACEMENT module
  keys identify both removed and added modules while quantities describe only
  newly added modules.
- NO_CHANGE, CLARIFICATION, AMBIGUOUS, and CLOSURE select no modules.

Evidence and safety:
- Every event cites the exact current Gmail message ID and authoritative
  ScopeVersion ID directly in that event's evidence list, with quotes found in
  those sources. This also applies to CLOSURE and unsupported events; evidence
  nested under unsupported_requirements does not replace event evidence.
- Populate those Gmail and ScopeVersion references separately on every event;
  never omit them because another event from the same message already cites the
  sources.
- Populate affected_requirement_ids whenever the clause modifies, extends,
  removes, replaces, clarifies, or tentatively refers to a baseline requirement.
- In every event selecting modules, cite every exact module key selected by that
  event as SOP evidence, including dependencies, and set each SOP evidence
  source_version to the returned catalog version.
- Confidence is an integer 0-100. Use below 60 for ambiguous/insufficient cases.
- Final output check: inspect every event separately. Its evidence list must have
  a current-message Gmail reference and an authoritative ScopeVersion reference;
  every module key in that same event must also have matching versioned SOP
  evidence. Do not return until all event evidence lists satisfy this check.
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

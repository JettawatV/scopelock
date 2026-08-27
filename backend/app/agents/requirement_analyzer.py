from pathlib import Path

from backend.app.domain.models import EvidenceRef, NormalizedRequirement, RequirementAnalysis, SOPModuleSelection
from backend.app.services.sop_service import SOPCatalog, load_sop
from backend.app.agents.adk_tools import get_current_scope, get_recent_thread_context, get_sop_catalog

PROMPT_VERSION = "requirement_analyzer_v1"


def build_adk_agent():
    """Build the real ADK agent when the optional ADK dependency is installed.

    The application will later invoke this through an adapter. Keeping creation
    isolated prevents ADK imports from contaminating deterministic services/tests.
    """
    try:
        from google.adk.agents import Agent
    except ImportError as exc:
        raise RuntimeError("Install the 'adk' extra to run the Vertex/ADK agent") from exc
    return Agent(
        name="requirement_analyzer",
        model="gemini-3.5-flash",
        output_schema=RequirementAnalysis,
        instruction=(
            "Extract typed project requirements and map only to module keys returned by "
            "get_sop_catalog. Cite the client email and SOP evidence. Never calculate "
            "or invent price. Use get_current_scope and get_recent_thread_context only "
            "when a project ID is supplied."
        ),
        tools=[get_sop_catalog, get_current_scope, get_recent_thread_context],
    )


def offline_requirement_analysis(email_text: str, catalog: SOPCatalog) -> RequirementAnalysis:
    """Credential-free contract smoke test used before external integration.

    This is intentionally a fixture-oriented adapter, not the production semantic
    classifier. It proves the typed boundary and deterministic SOP validation.
    """
    quote = email_text.strip()
    selected = []
    for module in catalog.modules:
        terms = [module.name, module.key, *module.aliases]
        if any(term.lower() in quote.lower() for term in terms):
            selected.append(SOPModuleSelection(
                module_key=module.key,
                mapped_requirement=module.description,
                confidence=0.70,
                evidence=[EvidenceRef(source_type="gmail", source_id="offline-fixture", quote_or_rule=quote[:500])],
            ))
    requirement = NormalizedRequirement(
        requirement_id="req-001",
        category="client_request",
        description=quote[:500],
        normalized_key="client_project_request",
        source_quote=quote[:500],
    )
    return RequirementAnalysis(
        is_project_request=True,
        project_title="Offline requirement analysis",
        objective=quote[:500],
        requirements=[requirement],
        selected_sop_modules=selected,
        proposal_ready=bool(quote),
        confidence=0.70,
        evidence=[EvidenceRef(source_type="gmail", source_id="offline-fixture", quote_or_rule=quote[:500])],
    )


def analyze_fixture(email_text: str, sop_path: str | Path = "config/jvl_sop.example.yaml") -> RequirementAnalysis:
    return offline_requirement_analysis(email_text, load_sop(sop_path))

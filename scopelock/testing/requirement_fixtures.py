from pathlib import Path

from scopelock.domain.models import EvidenceRef, NormalizedRequirement, RequirementAnalysis, SOPModuleSelection
from scopelock.services.sop_service import SOPCatalog, load_sop


def offline_requirement_analysis(email_text: str, catalog: SOPCatalog) -> RequirementAnalysis:
    """Fixture-only contract smoke test; this is not production semantic analysis."""
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
    return RequirementAnalysis(
        is_project_request=True,
        project_title="Offline requirement analysis",
        objective=quote[:500],
        requirements=[NormalizedRequirement(
            requirement_id="req-001",
            category="client_request",
            description=quote[:500],
            normalized_key="client_project_request",
            source_quote=quote[:500],
        )],
        selected_sop_modules=selected,
        proposal_ready=bool(quote),
        confidence=0.70,
        evidence=[EvidenceRef(source_type="gmail", source_id="offline-fixture", quote_or_rule=quote[:500])],
    )


def analyze_fixture(email_text: str, sop_path: str | Path = "config/jvl_sop.example.yaml") -> RequirementAnalysis:
    return offline_requirement_analysis(email_text, load_sop(sop_path))


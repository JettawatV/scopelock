from backend.app.agents.requirement_analyzer import analyze_fixture
from backend.app.services.sop_service import load_sop


def test_sop_loads_and_has_unique_keys():
    catalog = load_sop("config/jvl_sop.example.yaml")
    assert len(catalog.modules) >= 5
    assert len({module.key for module in catalog.modules}) == len(catalog.modules)


def test_offline_requirement_analysis_returns_typed_output():
    result = analyze_fixture(
        "Please automate our shared inbox and show an operations dashboard."
    )
    assert result.is_project_request is True
    assert result.proposal_ready is True
    assert result.requirements[0].source_quote.startswith("Please automate")
    assert {item.module_key for item in result.selected_sop_modules} == {
        "email_intake",
        "operations_dashboard",
    }


def test_analysis_cannot_select_unknown_sop_module():
    result = analyze_fixture("Please add a teleportation module.")
    catalog = load_sop("config/jvl_sop.example.yaml")
    assert all(item.module_key in {module.key for module in catalog.modules} for item in result.selected_sop_modules)


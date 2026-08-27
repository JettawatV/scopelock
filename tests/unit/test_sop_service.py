from scopelock.services.sop_service import load_sop


def test_sop_loads_and_has_unique_keys():
    catalog = load_sop("config/jvl_sop.example.yaml")
    assert len(catalog.modules) >= 5
    assert len({module.key for module in catalog.modules}) == len(catalog.modules)


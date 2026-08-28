from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from scopelock.services.sop_service import SOPCatalog, load_sop


SOP_PATH = Path("config/jvl_sop.example.yaml")


def valid_catalog_data() -> dict:
    return yaml.safe_load(SOP_PATH.read_text(encoding="utf-8"))


def test_sop_loads_with_explicit_version_and_usd_currency():
    catalog = load_sop(SOP_PATH)

    assert catalog.version == "jvl-demo-v1"
    assert catalog.business.currency == "USD"
    assert len(catalog.modules) >= 5
    assert len({module.key for module in catalog.modules}) == len(catalog.modules)
    assert all(module.scope_rules.material_if_added for module in catalog.modules)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda data: data["modules"][1].update(
            key=data["modules"][0]["key"]
        ),
        lambda data: data["modules"][1]["aliases"].append(
            data["modules"][0]["aliases"][0].upper()
        ),
        lambda data: data["modules"][0]["included"].append(
            data["modules"][0]["included"][0].upper()
        ),
        lambda data: data["modules"][0]["excluded"].append(
            data["modules"][0]["included"][0]
        ),
        lambda data: data["modules"][0].setdefault("dependencies", []).append(
            "unknown_module"
        ),
        lambda data: data["modules"][0].setdefault("dependencies", []).append(
            data["modules"][0]["key"]
        ),
    ],
    ids=[
        "duplicate-module-key",
        "ambiguous-global-alias",
        "duplicate-inclusion",
        "included-excluded-overlap",
        "unknown-dependency",
        "self-dependency",
    ],
)
def test_sop_rejects_invalid_module_metadata(mutate):
    data = valid_catalog_data()
    mutate(data)

    with pytest.raises(ValidationError):
        SOPCatalog.model_validate(data)


def test_sop_rejects_dependency_cycles():
    data = valid_catalog_data()
    data["modules"][0]["dependencies"] = ["email_intake"]
    data["modules"][1]["dependencies"] = ["core_workflow_automation"]

    with pytest.raises(ValidationError, match="acyclic"):
        SOPCatalog.model_validate(data)


def test_sop_requires_explicit_boolean_materiality_settings():
    data = valid_catalog_data()
    del data["modules"][0]["scope_rules"]["material_if_added"]

    with pytest.raises(ValidationError):
        SOPCatalog.model_validate(data)

    data = valid_catalog_data()
    data["modules"][0]["scope_rules"]["material_if_added"] = "yes"

    with pytest.raises(ValidationError):
        SOPCatalog.model_validate(data)


@pytest.mark.parametrize(
    "pricing",
    [
        {"type": "percentage", "amount_usd": 100},
        {"type": "fixed", "amount_usd": 100, "unit": "integration"},
        {"type": "fixed", "amount_usd": 100, "minimum_units": 1},
        {"type": "per_unit", "amount_usd": 100},
        {
            "type": "per_unit",
            "amount_usd": 100,
            "unit": " ",
            "minimum_units": 1,
        },
        {
            "type": "per_unit",
            "amount_usd": 100,
            "unit": "integration",
            "minimum_units": 0,
        },
    ],
    ids=[
        "unsupported-type",
        "fixed-with-unit",
        "fixed-with-minimum",
        "per-unit-without-unit",
        "per-unit-empty-unit",
        "per-unit-invalid-minimum",
    ],
)
def test_sop_rejects_malformed_pricing_rules(pricing):
    data = valid_catalog_data()
    data["modules"][0]["pricing"] = pricing

    with pytest.raises(ValidationError):
        SOPCatalog.model_validate(data)


def test_sop_rejects_currency_mismatch():
    data = valid_catalog_data()
    data["business"]["currency"] = "EUR"

    with pytest.raises(ValidationError):
        SOPCatalog.model_validate(data)


def test_sop_rejects_empty_inclusion_and_exclusion_text():
    for field_name in ("included", "excluded", "aliases"):
        data = deepcopy(valid_catalog_data())
        data["modules"][0][field_name].append(" ")

        with pytest.raises(ValidationError):
            SOPCatalog.model_validate(data)

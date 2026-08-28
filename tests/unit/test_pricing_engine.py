import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from scopelock.domain.models import ModuleQuantity
from scopelock.services.pricing_engine import (
    CurrencyMismatchError,
    InvalidQuantityError,
    MissingDependencyError,
    PricingEngine,
    PricingInputError,
    UnknownModuleError,
)
from scopelock.services.sop_service import SOPCatalog, load_sop


SOP_PATH = Path("config/jvl_sop.example.yaml")
GOLDEN_PATH = Path("tests/fixtures/pricing_golden_path.json")


def catalog_with_per_unit_module() -> SOPCatalog:
    data = yaml.safe_load(SOP_PATH.read_text(encoding="utf-8"))
    data["modules"].append(
        {
            "key": "additional_mailbox",
            "name": "Additional Gmail Mailbox",
            "description": "Add another mailbox to an existing intake flow.",
            "aliases": ["extra mailbox"],
            "pricing": {
                "type": "per_unit",
                "amount_usd": 250,
                "unit": "mailbox",
                "minimum_units": 2,
            },
            "timeline": {"base_days": 1, "parallelizable": True},
            "included": ["one additional mailbox per unit"],
            "excluded": ["mailbox migration"],
            "dependencies": ["email_intake"],
            "scope_rules": {"material_if_added": True},
        }
    )
    return SOPCatalog.model_validate(data)


def test_fixed_price_module_produces_traceable_immutable_usd_line_item():
    engine = PricingEngine(load_sop(SOP_PATH))

    result = engine.calculate(
        [ModuleQuantity(module_key="core_workflow_automation", quantity=1)]
    )

    assert result.currency == "USD"
    assert result.sop_version == "jvl-demo-v1"
    assert result.total_usd == 4000
    assert result.line_items[0].model_dump() == {
        "module_key": "core_workflow_automation",
        "quantity": 1,
        "unit_rule": "fixed",
        "unit": None,
        "unit_amount_usd": 4000,
        "subtotal_usd": 4000,
        "currency": "USD",
        "sop_version": "jvl-demo-v1",
    }

    with pytest.raises(ValidationError):
        result.total_usd = 0
    with pytest.raises(ValidationError):
        result.line_items[0].subtotal_usd = 0


def test_per_unit_module_multiplies_valid_quantity():
    engine = PricingEngine(catalog_with_per_unit_module())

    result = engine.calculate(
        [
            ModuleQuantity(module_key="email_intake", quantity=1),
            ModuleQuantity(module_key="additional_mailbox", quantity=3),
        ]
    )

    item = result.line_items[1]
    assert item.unit_rule == "per_unit"
    assert item.unit == "mailbox"
    assert item.unit_amount_usd == 250
    assert item.quantity == 3
    assert item.subtotal_usd == 750
    assert result.total_usd == 1250


def test_per_unit_module_rejects_quantity_below_minimum():
    engine = PricingEngine(catalog_with_per_unit_module())

    with pytest.raises(InvalidQuantityError, match="requires at least 2"):
        engine.calculate(
            [
                ModuleQuantity(module_key="email_intake", quantity=1),
                ModuleQuantity(module_key="additional_mailbox", quantity=1),
            ]
        )


def test_duplicate_policy_collapses_fixed_and_sums_per_unit_selections():
    engine = PricingEngine(catalog_with_per_unit_module())

    result = engine.calculate(
        [
            ModuleQuantity(module_key="email_intake", quantity=1),
            ModuleQuantity(module_key="email_intake", quantity=1),
            ModuleQuantity(module_key="additional_mailbox", quantity=1),
            ModuleQuantity(module_key="additional_mailbox", quantity=2),
        ]
    )

    assert [item.module_key for item in result.line_items] == [
        "email_intake",
        "additional_mailbox",
    ]
    assert [item.quantity for item in result.line_items] == [1, 3]
    assert result.total_usd == 1250


def test_unknown_module_and_fixed_quantity_fail_safely():
    engine = PricingEngine(load_sop(SOP_PATH))

    with pytest.raises(UnknownModuleError):
        engine.calculate(
            [ModuleQuantity(module_key="not_in_catalog", quantity=1)]
        )
    with pytest.raises(InvalidQuantityError, match="requires quantity 1"):
        engine.calculate(
            [ModuleQuantity(module_key="email_intake", quantity=2)]
        )


@pytest.mark.parametrize("quantity", [0, -1, 1.5, "1", True])
def test_quantity_contract_rejects_non_positive_or_non_integer_values(quantity):
    with pytest.raises(ValidationError):
        ModuleQuantity(module_key="email_intake", quantity=quantity)


def test_model_amount_fields_cannot_enter_pricing_input():
    with pytest.raises(ValidationError):
        ModuleQuantity(
            module_key="email_intake",
            quantity=1,
            total_usd=1,
        )

    engine = PricingEngine(load_sop(SOP_PATH))
    with pytest.raises(PricingInputError):
        engine.calculate(
            [{"module_key": "email_intake", "quantity": 1, "total_usd": 1}]
        )


def test_required_dependencies_must_be_selected():
    engine = PricingEngine(load_sop(SOP_PATH))

    with pytest.raises(MissingDependencyError, match="line_notifications"):
        engine.calculate(
            [ModuleQuantity(module_key="line_approval", quantity=1)]
        )

    result = engine.calculate(
        [
            ModuleQuantity(module_key="line_notifications", quantity=1),
            ModuleQuantity(module_key="line_approval", quantity=1),
        ]
    )
    assert result.total_usd == 1500


def test_engine_defensively_rejects_non_usd_constructed_catalog():
    catalog = load_sop(SOP_PATH)
    invalid_business = catalog.business.model_copy(update={"currency": "EUR"})
    invalid_catalog = catalog.model_copy(update={"business": invalid_business})

    with pytest.raises(CurrencyMismatchError):
        PricingEngine(invalid_catalog)


def test_same_version_and_selections_always_produce_same_result():
    engine = PricingEngine(load_sop(SOP_PATH))
    selections = (
        ModuleQuantity(module_key="core_workflow_automation", quantity=1),
        ModuleQuantity(module_key="email_intake", quantity=1),
    )

    assert engine.calculate(selections) == engine.calculate(selections)


def test_golden_path_pricing_fixture_matches_catalog_rules():
    fixture = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    engine = PricingEngine(load_sop(SOP_PATH))
    selections = tuple(
        ModuleQuantity.model_validate(selection)
        for selection in fixture["selections"]
    )

    result = engine.calculate(selections)

    assert result.model_dump(mode="json") == fixture["expected_result"]

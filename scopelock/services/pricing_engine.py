"""Deterministic SOP pricing with no agent or model dependency."""

from collections.abc import Sequence

from scopelock.domain.models import ModuleQuantity, PriceLineItem, PricingResult
from scopelock.services.sop_service import (
    FixedPricingRule,
    PerUnitPricingRule,
    SOPCatalog,
)


class PricingError(ValueError):
    """Base class for safe, reviewable pricing failures."""


class PricingInputError(PricingError):
    pass


class UnknownModuleError(PricingError):
    pass


class InvalidQuantityError(PricingError):
    pass


class MissingDependencyError(PricingError):
    pass


class CurrencyMismatchError(PricingError):
    pass


class PricingEngine:
    """Calculate immutable USD line items from module keys and quantities.

    Duplicate policy:
    - fixed-price module duplicates collapse to one module instance; every
      incoming fixed-price selection must have quantity 1;
    - per-unit module duplicates are merged by summing their quantities;
    - output order follows the first appearance of each module key.

    This policy prevents a repeated semantic mapping from charging the same
    fixed package twice while preserving additive per-unit intent.
    """

    CURRENCY = "USD"

    def __init__(self, catalog: SOPCatalog):
        if catalog.business.currency != self.CURRENCY:
            raise CurrencyMismatchError(
                "PricingEngine supports only USD SOP catalogs; "
                f"received {catalog.business.currency!r}"
            )
        self._catalog = catalog

    def calculate(self, selections: Sequence[ModuleQuantity]) -> PricingResult:
        normalized = self._normalize(selections)
        selected_keys = {selection.module_key for selection in normalized}
        line_items: list[PriceLineItem] = []

        for selection in normalized:
            try:
                module = self._catalog.module(selection.module_key)
            except KeyError as error:
                raise UnknownModuleError(str(error)) from error

            missing_dependencies = set(module.dependencies) - selected_keys
            if missing_dependencies:
                raise MissingDependencyError(
                    f"Module {module.key!r} requires selected dependencies: "
                    f"{sorted(missing_dependencies)}"
                )

            rule = module.pricing
            if isinstance(rule, FixedPricingRule):
                subtotal = rule.amount_usd
                unit = None
            elif isinstance(rule, PerUnitPricingRule):
                if selection.quantity < rule.minimum_units:
                    raise InvalidQuantityError(
                        f"Module {module.key!r} requires at least "
                        f"{rule.minimum_units} {rule.unit}; received "
                        f"{selection.quantity}"
                    )
                subtotal = rule.amount_usd * selection.quantity
                unit = rule.unit
            else:  # pragma: no cover - guarded by the SOP discriminated union
                raise PricingError(
                    f"Module {module.key!r} has an unsupported pricing rule"
                )

            line_items.append(
                PriceLineItem(
                    module_key=module.key,
                    quantity=selection.quantity,
                    unit_rule=rule.type,
                    unit=unit,
                    unit_amount_usd=rule.amount_usd,
                    subtotal_usd=subtotal,
                    currency=self.CURRENCY,
                    sop_version=self._catalog.version,
                )
            )

        return PricingResult(
            currency=self.CURRENCY,
            sop_version=self._catalog.version,
            line_items=tuple(line_items),
            total_usd=sum(item.subtotal_usd for item in line_items),
        )

    def _normalize(
        self, selections: Sequence[ModuleQuantity]
    ) -> tuple[ModuleQuantity, ...]:
        normalized_quantities: dict[str, int] = {}

        for selection in selections:
            if not isinstance(selection, ModuleQuantity):
                raise PricingInputError(
                    "PricingEngine accepts only ModuleQuantity inputs containing "
                    "module_key and quantity"
                )
            try:
                module = self._catalog.module(selection.module_key)
            except KeyError as error:
                raise UnknownModuleError(str(error)) from error

            if isinstance(module.pricing, FixedPricingRule):
                if selection.quantity != 1:
                    raise InvalidQuantityError(
                        f"Fixed-price module {module.key!r} requires quantity 1; "
                        f"received {selection.quantity}"
                    )
                normalized_quantities.setdefault(module.key, 1)
            else:
                normalized_quantities[module.key] = (
                    normalized_quantities.get(module.key, 0) + selection.quantity
                )

        return tuple(
            ModuleQuantity(module_key=module_key, quantity=quantity)
            for module_key, quantity in normalized_quantities.items()
        )

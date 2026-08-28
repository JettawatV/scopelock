"""Deterministic timeline calculation from validated SOP module rules."""

from collections.abc import Sequence

from scopelock.domain.models import (
    ModuleQuantity,
    TimelineLineItem,
    TimelineResult,
)
from scopelock.services.sop_service import (
    FixedPricingRule,
    SOPCatalog,
    SOPModule,
)


class TimelineError(ValueError):
    """Base class for safe deterministic timeline failures."""


class TimelineInputError(TimelineError):
    pass


class UnknownTimelineModuleError(TimelineError):
    pass


class InvalidTimelineQuantityError(TimelineError):
    pass


class MissingTimelineDependencyError(TimelineError):
    pass


class TimelineEngine:
    """Apply the documented P0 base-plus-non-parallel algorithm.

    The selected module with the greatest ``base_days`` is the base module
    (module key breaks ties). Its days establish the base duration. Every other
    non-parallel module adds its full ``base_days``; parallel modules add zero.
    Dependencies are required explicitly and line items are emitted in a
    deterministic topological order.

    P0 timeline rules are module-based, so quantity is recorded for provenance
    but does not scale days. Quantity-sensitive duration requires a future SOP
    timeline rule and must not be inferred from pricing.
    """

    def __init__(self, catalog: SOPCatalog):
        self._catalog = catalog

    def calculate(self, selections: Sequence[ModuleQuantity]) -> TimelineResult:
        normalized = self._normalize(selections)
        if not normalized:
            return TimelineResult(
                sop_version=self._catalog.version,
                calculation_inputs=(),
                line_items=(),
                base_module_key=None,
                total_days=0,
            )

        selected_keys = {selection.module_key for selection in normalized}
        modules = {
            selection.module_key: self._catalog.module(selection.module_key)
            for selection in normalized
        }
        for module in modules.values():
            missing = set(module.dependencies) - selected_keys
            if missing:
                raise MissingTimelineDependencyError(
                    f"Module {module.key!r} requires selected dependencies: "
                    f"{sorted(missing)}"
                )

        ordered_keys = self._topological_order(modules)
        base_module = sorted(
            modules.values(),
            key=lambda module: (-module.timeline.base_days, module.key),
        )[0]
        quantities = {
            selection.module_key: selection.quantity for selection in normalized
        }
        line_items: list[TimelineLineItem] = []

        for module_key in ordered_keys:
            module = modules[module_key]
            is_base = module.key == base_module.key
            incremental_days = (
                module.timeline.base_days
                if is_base or not module.timeline.parallelizable
                else 0
            )
            line_items.append(
                TimelineLineItem(
                    module_key=module.key,
                    quantity=quantities[module.key],
                    base_days=module.timeline.base_days,
                    parallelizable=module.timeline.parallelizable,
                    dependency_keys=module.dependencies,
                    is_base_module=is_base,
                    incremental_days=incremental_days,
                    sop_version=self._catalog.version,
                )
            )

        return TimelineResult(
            sop_version=self._catalog.version,
            calculation_inputs=normalized,
            line_items=tuple(line_items),
            base_module_key=base_module.key,
            total_days=sum(item.incremental_days for item in line_items),
        )

    def _normalize(
        self, selections: Sequence[ModuleQuantity]
    ) -> tuple[ModuleQuantity, ...]:
        quantities: dict[str, int] = {}
        for selection in selections:
            if not isinstance(selection, ModuleQuantity):
                raise TimelineInputError(
                    "TimelineEngine accepts only ModuleQuantity inputs"
                )
            try:
                module = self._catalog.module(selection.module_key)
            except KeyError as error:
                raise UnknownTimelineModuleError(str(error)) from error

            if isinstance(module.pricing, FixedPricingRule):
                if selection.quantity != 1:
                    raise InvalidTimelineQuantityError(
                        f"Fixed module {module.key!r} requires quantity 1; "
                        f"received {selection.quantity}"
                    )
                quantities.setdefault(module.key, 1)
            else:
                quantities[module.key] = (
                    quantities.get(module.key, 0) + selection.quantity
                )

        return tuple(
            ModuleQuantity(module_key=key, quantity=quantities[key])
            for key in sorted(quantities)
        )

    @staticmethod
    def _topological_order(modules: dict[str, SOPModule]) -> tuple[str, ...]:
        remaining_dependencies = {
            key: set(module.dependencies) for key, module in modules.items()
        }
        ordered: list[str] = []
        while remaining_dependencies:
            ready = sorted(
                key
                for key, dependencies in remaining_dependencies.items()
                if not dependencies
            )
            if not ready:  # pragma: no cover - catalog validation prevents cycles
                raise TimelineError("Selected module dependencies contain a cycle")
            for key in ready:
                ordered.append(key)
                del remaining_dependencies[key]
            for dependencies in remaining_dependencies.values():
                dependencies.difference_update(ready)
        return tuple(ordered)

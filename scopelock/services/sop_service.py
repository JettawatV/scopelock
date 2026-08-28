"""Validated, immutable access to the ScopeLock business SOP catalog."""

from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
    model_validator,
)


NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
ModuleKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^[a-z][a-z0-9_]*$"),
]
UsdAmount = Annotated[int, Field(ge=0, strict=True)]
PositiveQuantity = Annotated[int, Field(ge=1, strict=True)]


class FrozenSOPModel(BaseModel):
    """Base model for loaded SOP data, which must not mutate during a run."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class FixedPricingRule(FrozenSOPModel):
    type: Literal["fixed"]
    amount_usd: UsdAmount


class PerUnitPricingRule(FrozenSOPModel):
    type: Literal["per_unit"]
    amount_usd: UsdAmount
    unit: NonEmptyText
    minimum_units: PositiveQuantity = 1


PricingRule = Annotated[
    FixedPricingRule | PerUnitPricingRule,
    Field(discriminator="type"),
]


class TimelineRule(FrozenSOPModel):
    base_days: Annotated[int, Field(ge=0, strict=True)]
    parallelizable: StrictBool = False


class MaterialitySettings(FrozenSOPModel):
    """P0 materiality rule documented by the SOP specification."""

    material_if_added: StrictBool


class BusinessSettings(FrozenSOPModel):
    name: NonEmptyText
    currency: Literal["USD"]
    proposal_valid_days: PositiveQuantity
    default_quiet_window_minutes: PositiveQuantity


class SOPPolicies(FrozenSOPModel):
    human_approval_required_for_send: StrictBool
    accepted_scope_is_immutable: StrictBool
    ambiguous_commercial_change_requires_review: StrictBool


def _normalized_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _duplicates(values: tuple[str, ...]) -> set[str]:
    normalized = [_normalized_text(value) for value in values]
    return {value for value in normalized if normalized.count(value) > 1}


class SOPModule(FrozenSOPModel):
    key: ModuleKey
    name: NonEmptyText
    description: NonEmptyText
    aliases: tuple[NonEmptyText, ...] = ()
    pricing: PricingRule
    timeline: TimelineRule
    included: tuple[NonEmptyText, ...] = ()
    excluded: tuple[NonEmptyText, ...] = ()
    dependencies: tuple[ModuleKey, ...] = ()
    scope_rules: MaterialitySettings

    @model_validator(mode="after")
    def validate_module_metadata(self) -> "SOPModule":
        for field_name, values in (
            ("aliases", self.aliases),
            ("included", self.included),
            ("excluded", self.excluded),
            ("dependencies", self.dependencies),
        ):
            duplicates = _duplicates(values)
            if duplicates:
                raise ValueError(
                    f"SOP module {self.key!r} has duplicate {field_name}: "
                    f"{sorted(duplicates)}"
                )

        included = {_normalized_text(value) for value in self.included}
        excluded = {_normalized_text(value) for value in self.excluded}
        overlap = included & excluded
        if overlap:
            raise ValueError(
                f"SOP module {self.key!r} cannot both include and exclude: "
                f"{sorted(overlap)}"
            )
        if self.key in self.dependencies:
            raise ValueError(f"SOP module {self.key!r} cannot depend on itself")
        return self


class SOPCatalog(FrozenSOPModel):
    version: NonEmptyText
    business: BusinessSettings
    policies: SOPPolicies
    modules: tuple[SOPModule, ...]

    @model_validator(mode="after")
    def validate_catalog(self) -> "SOPCatalog":
        keys = [module.key for module in self.modules]
        if len(keys) != len(set(keys)):
            raise ValueError("SOP module keys must be unique")

        alias_owners: dict[str, str] = {}
        for module in self.modules:
            for alias in module.aliases:
                normalized = _normalized_text(alias)
                owner = alias_owners.get(normalized)
                if owner is not None and owner != module.key:
                    raise ValueError(
                        f"SOP alias {alias!r} is ambiguous between {owner!r} "
                        f"and {module.key!r}"
                    )
                alias_owners[normalized] = module.key

        known_keys = set(keys)
        for module in self.modules:
            unknown = set(module.dependencies) - known_keys
            if unknown:
                raise ValueError(
                    f"SOP module {module.key!r} has unknown dependencies: "
                    f"{sorted(unknown)}"
                )

        self._validate_acyclic_dependencies()
        return self

    def _validate_acyclic_dependencies(self) -> None:
        dependencies = {
            module.key: module.dependencies for module in self.modules
        }
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(key: str, path: tuple[str, ...]) -> None:
            if key in visiting:
                cycle_start = path.index(key)
                cycle = (*path[cycle_start:], key)
                raise ValueError(
                    "SOP dependencies must be acyclic: " + " -> ".join(cycle)
                )
            if key in visited:
                return
            visiting.add(key)
            for dependency in dependencies[key]:
                visit(dependency, (*path, key))
            visiting.remove(key)
            visited.add(key)

        for module_key in dependencies:
            visit(module_key, ())

    def module(self, key: str) -> SOPModule:
        for module in self.modules:
            if module.key == key:
                return module
        raise KeyError(f"Unknown SOP module: {key}")


def load_sop(path: str | Path) -> SOPCatalog:
    with Path(path).open("r", encoding="utf-8") as handle:
        raw_catalog = yaml.safe_load(handle)
    if not isinstance(raw_catalog, dict):
        raise ValueError("SOP document must contain a mapping at its root")
    return SOPCatalog.model_validate(raw_catalog)

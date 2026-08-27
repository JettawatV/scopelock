from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator


class PricingRule(BaseModel):
    type: str
    amount_usd: int = Field(ge=0)
    unit: str | None = None
    minimum_units: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_type(self):
        if self.type not in {"fixed", "per_unit"}:
            raise ValueError("P0 supports only fixed and per_unit pricing")
        if self.type == "per_unit" and not self.unit:
            raise ValueError("per_unit pricing requires unit")
        return self


class TimelineRule(BaseModel):
    base_days: int = Field(ge=0)
    parallelizable: bool = False


class SOPModule(BaseModel):
    key: str
    name: str
    description: str
    aliases: list[str] = Field(default_factory=list)
    pricing: PricingRule
    timeline: TimelineRule
    included: list[str] = Field(default_factory=list)
    excluded: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)


class SOPCatalog(BaseModel):
    business: dict[str, Any]
    policies: dict[str, bool]
    modules: list[SOPModule]

    @model_validator(mode="after")
    def unique_module_keys(self):
        keys = [module.key for module in self.modules]
        if len(keys) != len(set(keys)):
            raise ValueError("SOP module keys must be unique")
        return self

    def module(self, key: str) -> SOPModule:
        for module in self.modules:
            if module.key == key:
                return module
        raise KeyError(f"Unknown SOP module: {key}")


def load_sop(path: str | Path) -> SOPCatalog:
    with Path(path).open("r", encoding="utf-8") as handle:
        return SOPCatalog.model_validate(yaml.safe_load(handle))


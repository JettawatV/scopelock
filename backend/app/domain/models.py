from typing import Literal

from pydantic import BaseModel, Field


class EvidenceRef(BaseModel):
    source_type: Literal["gmail", "scope_version", "sop"]
    source_id: str
    quote_or_rule: str


class NormalizedRequirement(BaseModel):
    requirement_id: str
    category: str
    description: str
    normalized_key: str
    source_quote: str


class SOPModuleSelection(BaseModel):
    module_key: str
    quantity: int = Field(default=1, ge=1)
    mapped_requirement: str
    confidence: float = Field(ge=0, le=1)
    evidence: list[EvidenceRef] = Field(default_factory=list)


class RequirementAnalysis(BaseModel):
    is_project_request: bool
    project_title: str
    objective: str
    requirements: list[NormalizedRequirement]
    selected_sop_modules: list[SOPModuleSelection]
    assumptions: list[str] = Field(default_factory=list)
    exclusions_to_surface: list[str] = Field(default_factory=list)
    missing_critical_information: list[str] = Field(default_factory=list)
    proposal_ready: bool
    confidence: float = Field(ge=0, le=1)
    evidence: list[EvidenceRef] = Field(default_factory=list)


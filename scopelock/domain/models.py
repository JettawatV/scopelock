from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceRef(StrictContractModel):
    source_type: Literal["gmail", "scope_version", "sop"]
    source_id: str
    quote_or_rule: str


class NormalizedRequirement(StrictContractModel):
    requirement_id: str
    category: str
    description: str
    normalized_key: str
    source_quote: str


class SOPModuleSelection(StrictContractModel):
    module_key: str
    quantity: int = Field(default=1, ge=1)
    mapped_requirement: str
    confidence: float = Field(ge=0, le=1)
    evidence: list[EvidenceRef] = Field(default_factory=list)


class RequirementAnalysis(StrictContractModel):
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


class AgentRunStatus(StrEnum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    FAILED = "FAILED"


class ToolActionPhase(StrEnum):
    CALL = "CALL"
    RESULT = "RESULT"


class ToolActionStatus(StrEnum):
    REQUESTED = "REQUESTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AgentRunError(StrictContractModel):
    category: str
    message: str
    retryable: bool = False


class ToolAction(StrictContractModel):
    id: str
    agent_run_id: str
    sequence: int = Field(ge=1)
    call_id: str
    tool_name: str
    phase: ToolActionPhase
    status: ToolActionStatus
    payload: Any = None
    event_id: str | None = None
    author: str | None = None
    recorded_at: datetime
    error: str | None = None


class AgentRun(StrictContractModel):
    id: str
    correlation_id: str
    project_id: str | None = None
    trigger_type: str
    trigger_ref: str | None = None
    agent_name: str
    model: str
    prompt_version: str
    started_at: datetime
    completed_at: datetime | None = None
    status: AgentRunStatus
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    output: RequirementAnalysis | None = None
    tool_trajectory: list[ToolAction] = Field(default_factory=list)
    error: AgentRunError | None = None

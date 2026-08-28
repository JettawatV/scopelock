from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from scopelock.domain.enums import (
    ApprovalStatus,
    ArtifactStatus,
    ArtifactType,
    ConfidenceBand,
    ProjectLifecycleStatus,
    ScopeAnalysisStatus,
    ScopeEventClassification,
    ScopeEventStatus,
    ScopeVersionStatus,
    SendIntentStatus,
)


class StrictContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StrictFrozenContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


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


class ModuleQuantity(StrictFrozenContractModel):
    """The complete input contract accepted by deterministic pricing."""

    module_key: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    quantity: int = Field(ge=1, strict=True)


class PriceLineItem(StrictFrozenContractModel):
    module_key: str
    quantity: int = Field(ge=1, strict=True)
    unit_rule: Literal["fixed", "per_unit"]
    unit: str | None = None
    unit_amount_usd: int = Field(ge=0, strict=True)
    subtotal_usd: int = Field(ge=0, strict=True)
    currency: Literal["USD"]
    sop_version: str


class PricingResult(StrictFrozenContractModel):
    currency: Literal["USD"]
    sop_version: str
    line_items: tuple[PriceLineItem, ...]
    total_usd: int = Field(ge=0, strict=True)


class TimelineLineItem(StrictFrozenContractModel):
    module_key: str
    quantity: int = Field(ge=1, strict=True)
    base_days: int = Field(ge=0, strict=True)
    parallelizable: bool
    dependency_keys: tuple[str, ...] = ()
    is_base_module: bool
    incremental_days: int = Field(ge=0, strict=True)
    sop_version: str


class TimelineResult(StrictFrozenContractModel):
    sop_version: str
    calculation_inputs: tuple[ModuleQuantity, ...]
    line_items: tuple[TimelineLineItem, ...]
    base_module_key: str | None
    total_days: int = Field(ge=0, strict=True)


class ScopeRequirementSnapshot(StrictFrozenContractModel):
    requirement_id: str
    category: str
    description: str
    normalized_key: str
    source_message_id: str
    source_quote: str


class ScopeVersion(StrictFrozenContractModel):
    id: str
    project_id: str
    version_number: int = Field(ge=1, strict=True)
    status: ScopeVersionStatus
    requirements: tuple[ScopeRequirementSnapshot, ...]
    module_selections: tuple[ModuleQuantity, ...]
    assumptions: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()
    pricing_result: PricingResult
    timeline_result: TimelineResult
    total_price_usd: int = Field(ge=0, strict=True)
    timeline_days: int = Field(ge=0, strict=True)
    currency: Literal["USD"]
    sop_version: str
    source_artifact_id: str | None = None
    created_at: datetime

    @model_validator(mode="after")
    def validate_calculation_provenance(self) -> "ScopeVersion":
        if self.total_price_usd != self.pricing_result.total_usd:
            raise ValueError("ScopeVersion total must match PricingResult")
        if self.timeline_days != self.timeline_result.total_days:
            raise ValueError("ScopeVersion timeline must match TimelineResult")
        if self.currency != self.pricing_result.currency:
            raise ValueError("ScopeVersion currency must match PricingResult")
        if {
            self.sop_version,
            self.pricing_result.sop_version,
            self.timeline_result.sop_version,
        } != {self.sop_version}:
            raise ValueError("ScopeVersion calculation records must use one SOP version")
        if self.module_selections != self.timeline_result.calculation_inputs:
            raise ValueError("ScopeVersion inputs must match TimelineResult inputs")
        return self


class CommercialArtifact(StrictFrozenContractModel):
    id: str
    project_id: str
    artifact_type: ArtifactType
    version_number: int = Field(ge=1, strict=True)
    change_order_number: int | None = Field(default=None, ge=1, strict=True)
    baseline_scope_version_id: str | None = None
    proposed_scope_version_id: str
    status: ArtifactStatus
    sop_version: str
    calculation_inputs: tuple[ModuleQuantity, ...]
    pricing_result: PricingResult
    timeline_result: TimelineResult
    checksum: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    created_at: datetime

    @model_validator(mode="after")
    def validate_artifact_type_and_provenance(self) -> "CommercialArtifact":
        if self.artifact_type == ArtifactType.CHANGE_ORDER:
            if self.change_order_number is None:
                raise ValueError("Change orders require change_order_number")
            if self.baseline_scope_version_id is None:
                raise ValueError("Change orders require an accepted baseline")
        elif self.change_order_number is not None:
            raise ValueError("Proposal artifacts cannot have change_order_number")

        if {
            self.sop_version,
            self.pricing_result.sop_version,
            self.timeline_result.sop_version,
        } != {self.sop_version}:
            raise ValueError("Commercial artifact calculations must use one SOP version")
        if self.calculation_inputs != self.timeline_result.calculation_inputs:
            raise ValueError("Artifact inputs must match TimelineResult inputs")
        return self


class ApprovalRecord(StrictFrozenContractModel):
    id: str
    artifact_id: str
    artifact_version: int = Field(ge=1, strict=True)
    artifact_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: ApprovalStatus
    approver_id: str
    correlation_id: str
    decided_at: datetime


class SendIntent(StrictFrozenContractModel):
    id: str
    artifact_id: str
    artifact_version: int = Field(ge=1, strict=True)
    artifact_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    approval_id: str
    gmail_thread_id: str
    correlation_id: str
    idempotency_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: SendIntentStatus
    created_at: datetime


class WorkflowStep(StrictFrozenContractModel):
    sequence: int = Field(ge=1, strict=True)
    actor: Literal["event_adapter", "adk_agent", "application", "human", "external"]
    action: str
    read_only: bool


class WorkflowTrajectory(StrictFrozenContractModel):
    name: Literal["initial_proposal", "scope_expansion"]
    correlation_id: str
    steps: tuple[WorkflowStep, ...]
    terminal_project_status: ProjectLifecycleStatus
    terminal_scope_event_status: ScopeEventStatus | None = None


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


class ScopeEventProposal(StrictContractModel):
    classification: ScopeEventClassification
    description: str
    affected_requirement_ids: list[str] = Field(default_factory=list)
    proposed_requirements: list[NormalizedRequirement] = Field(default_factory=list)
    sop_module_keys: list[str] = Field(default_factory=list)
    quantities: list[ModuleQuantity] = Field(default_factory=list)
    rationale: str
    evidence: list[EvidenceRef] = Field(default_factory=list)
    confidence: int = Field(ge=0, le=100, strict=True)

    @model_validator(mode="after")
    def validate_semantic_event_shape(self) -> "ScopeEventProposal":
        if len(self.sop_module_keys) != len(set(self.sop_module_keys)):
            raise ValueError("Scope event SOP module keys must be unique")
        quantity_keys = [quantity.module_key for quantity in self.quantities]
        if len(quantity_keys) != len(set(quantity_keys)):
            raise ValueError("Scope event quantity module keys must be unique")
        unknown_quantity_keys = set(quantity_keys) - set(self.sop_module_keys)
        if unknown_quantity_keys:
            raise ValueError(
                "Scope event quantities must reference selected SOP modules: "
                f"{sorted(unknown_quantity_keys)}"
            )
        if self.classification in {
            ScopeEventClassification.NO_CHANGE,
            ScopeEventClassification.CLARIFICATION,
            ScopeEventClassification.AMBIGUOUS,
            ScopeEventClassification.CLOSURE,
        } and (self.sop_module_keys or self.quantities):
            raise ValueError(
                f"{self.classification.value} cannot propose commercial modules"
            )
        return self


class ScopeAnalysis(StrictContractModel):
    events: list[ScopeEventProposal] = Field(min_length=1)
    conversation_closure: bool
    overall_confidence: int = Field(ge=0, le=100, strict=True)

    @model_validator(mode="after")
    def validate_closure_event(self) -> "ScopeAnalysis":
        has_closure_event = any(
            event.classification == ScopeEventClassification.CLOSURE
            for event in self.events
        )
        if has_closure_event != self.conversation_closure:
            raise ValueError(
                "conversation_closure must exactly match presence of a CLOSURE event"
            )
        return self


class ConfidenceThresholds(StrictFrozenContractModel):
    high: int = Field(default=85, gt=0, le=100, strict=True)
    medium: int = Field(default=60, ge=0, lt=100, strict=True)
    low: int = Field(default=0, ge=0, lt=100, strict=True)

    @model_validator(mode="after")
    def validate_order(self) -> "ConfidenceThresholds":
        if not self.low < self.medium < self.high:
            raise ValueError("confidence thresholds must satisfy low < medium < high")
        return self


class ScopeAnalysisDecision(StrictFrozenContractModel):
    analysis: ScopeAnalysis
    status: ScopeAnalysisStatus
    confidence_band: ConfidenceBand
    review_required: bool
    reasons: tuple[str, ...] = ()


class ScopeRunOutcome(StrictFrozenContractModel):
    correlation_id: str
    status: ScopeAnalysisStatus
    analysis: ScopeAnalysis | None = None
    review_required: bool
    reasons: tuple[str, ...] = ()
    error: str | None = None

    @model_validator(mode="after")
    def validate_failure_boundary(self) -> "ScopeRunOutcome":
        if self.analysis is None:
            if self.status != ScopeAnalysisStatus.NEEDS_REVIEW:
                raise ValueError("Missing analysis must route to NEEDS_REVIEW")
            if not self.review_required or not self.error:
                raise ValueError("Missing analysis requires a reviewable error")
        return self


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
    output: RequirementAnalysis | ScopeAnalysis | None = None
    tool_trajectory: list[ToolAction] = Field(default_factory=list)
    error: AgentRunError | None = None

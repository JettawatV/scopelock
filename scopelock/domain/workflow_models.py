"""Application-owned records for local workflows and persistent audit state."""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from scopelock.domain.enums import (
    ArtifactStatus,
    BufferFinalizationReason,
    ProjectLifecycleStatus,
    ScopeBufferStatus,
    ScopeEventClassification,
    ScopeEventStatus,
)
from scopelock.domain.models import (
    ApprovalRecord,
    CommercialArtifact,
    EvidenceRef,
    ModuleQuantity,
    PriceLineItem,
    ScopeRequirementSnapshot,
    ScopeVersion,
    SendIntent,
    StrictFrozenContractModel,
    TimelineResult,
)


class InboundEmail(StrictFrozenContractModel):
    message_id: str
    thread_id: str
    sender_name: str
    sender_email: str
    subject: str
    body: str
    received_at: datetime


class ProjectRecord(StrictFrozenContractModel):
    id: str
    client_name: str
    client_email: str
    gmail_thread_id: str
    title: str
    lifecycle_status: ProjectLifecycleStatus
    baseline_scope_version_id: str | None = None
    active_scope_version_id: str | None = None
    active_proposal_id: str | None = None
    scope_buffer_id: str | None = None
    current_price_usd: int = Field(default=0, ge=0, strict=True)
    current_timeline_days: int = Field(default=0, ge=0, strict=True)
    correlation_id: str
    created_at: datetime
    updated_at: datetime


class ProposalData(StrictFrozenContractModel):
    """Deterministic proposal payload rendered independently of the model."""

    project_id: str
    project_title: str
    client_name: str
    client_email: str
    objective: str
    requirements: tuple[ScopeRequirementSnapshot, ...]
    selected_modules: tuple[ModuleQuantity, ...]
    line_items: tuple[PriceLineItem, ...]
    total_usd: int = Field(ge=0, strict=True)
    currency: Literal["USD"]
    timeline: TimelineResult
    assumptions: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()
    evidence: tuple[EvidenceRef, ...] = ()
    validity_days: int = Field(ge=1, strict=True)
    source_message_id: str
    source_scope_version_id: str
    source_scope_version_number: int = Field(ge=1, strict=True)
    sop_version: str
    generated_at: datetime

    @model_validator(mode="after")
    def validate_commercial_provenance(self) -> "ProposalData":
        if self.total_usd != sum(item.subtotal_usd for item in self.line_items):
            raise ValueError("Proposal total must equal deterministic line subtotals")
        if any(item.currency != self.currency for item in self.line_items):
            raise ValueError("Proposal line-item currency must match proposal currency")
        if any(item.sop_version != self.sop_version for item in self.line_items):
            raise ValueError("Proposal line items must use the proposal SOP version")
        if self.timeline.sop_version != self.sop_version:
            raise ValueError("Proposal timeline must use the proposal SOP version")
        if self.selected_modules != self.timeline.calculation_inputs:
            raise ValueError("Proposal modules must match deterministic timeline inputs")
        return self


class RenderedProposal(StrictFrozenContractModel):
    commercial_artifact_id: str
    proposal_data_path: str
    proposal_markdown_path: str
    content_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_scope_version_id: str
    source_scope_version_number: int = Field(ge=1, strict=True)
    sop_version: str


class ScopeDecisionRecord(StrictFrozenContractModel):
    id: str
    project_id: str
    gmail_message_id: str
    decision_type: str
    selected_module_keys: tuple[str, ...] = ()
    rationale: str
    evidence: tuple[EvidenceRef, ...] = ()
    correlation_id: str
    created_at: datetime


class StateTransitionRecord(StrictFrozenContractModel):
    id: str
    entity_type: Literal["project", "artifact", "scope_event", "scope_buffer"]
    entity_id: str
    from_status: str
    to_status: str
    reason: str
    correlation_id: str
    created_at: datetime


class ArtifactEventRecord(StrictFrozenContractModel):
    id: str
    artifact_id: str
    artifact_version: int = Field(ge=1, strict=True)
    status: ArtifactStatus
    action: str
    checksum: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    correlation_id: str
    created_at: datetime


class AuditRecord(StrictFrozenContractModel):
    id: str
    record_type: str
    entity_id: str
    action: str
    actor: Literal["event_adapter", "adk_agent", "application", "human", "external"]
    correlation_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ModuleReplacement(StrictFrozenContractModel):
    remove: ModuleQuantity
    add: ModuleQuantity


class ScopeEventRecord(StrictFrozenContractModel):
    id: str
    project_id: str
    gmail_message_id: str
    baseline_scope_version_id: str
    classification: ScopeEventClassification
    status: ScopeEventStatus
    description: str
    additions: tuple[ModuleQuantity, ...] = ()
    reductions: tuple[ModuleQuantity, ...] = ()
    replacements: tuple[ModuleReplacement, ...] = ()
    evidence: tuple[EvidenceRef, ...] = ()
    price_delta_usd: int = 0
    timeline_delta_days: int = 0
    review_required: bool = False
    correlation_id: str
    created_at: datetime

    @property
    def is_material(self) -> bool:
        return self.classification in {
            ScopeEventClassification.EXPANSION,
            ScopeEventClassification.REDUCTION,
            ScopeEventClassification.REPLACEMENT,
        }

    @model_validator(mode="after")
    def validate_operations(self) -> "ScopeEventRecord":
        if not self.is_material and (
            self.additions or self.reductions or self.replacements
        ):
            raise ValueError("Non-material scope events cannot change modules")
        if self.classification == ScopeEventClassification.EXPANSION and not self.additions:
            raise ValueError("Expansion requires at least one module addition")
        if self.classification == ScopeEventClassification.REDUCTION and not self.reductions:
            raise ValueError("Reduction requires at least one module reduction")
        if self.classification == ScopeEventClassification.REPLACEMENT and not self.replacements:
            raise ValueError("Replacement requires at least one replacement")
        return self


class ScopeBufferRecord(StrictFrozenContractModel):
    id: str
    project_id: str
    baseline_scope_version_id: str
    event_ids: tuple[str, ...]
    additions: tuple[ModuleQuantity, ...] = ()
    reductions: tuple[ModuleQuantity, ...] = ()
    replacements: tuple[ModuleReplacement, ...] = ()
    proposed_module_selections: tuple[ModuleQuantity, ...]
    net_price_delta_usd: int
    net_timeline_delta_days: int
    status: ScopeBufferStatus
    last_client_message_at: datetime
    quiet_window_minutes: int = Field(ge=1, strict=True)
    quiet_window_expires_at: datetime
    finalized_at: datetime | None = None
    finalization_reason: BufferFinalizationReason | None = None
    correlation_id: str
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_finalization(self) -> "ScopeBufferRecord":
        finalized = self.status == ScopeBufferStatus.FINALIZED
        if finalized != (self.finalized_at is not None):
            raise ValueError("Finalized buffers require finalized_at")
        if finalized != (self.finalization_reason is not None):
            raise ValueError("Finalized buffers require a finalization reason")
        return self


class LocalInitialProposalResult(StrictFrozenContractModel):
    idempotency_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    correlation_id: str
    project: ProjectRecord
    scope_version_id: str
    artifact: CommercialArtifact
    proposal: ProposalData
    rendered_proposal: RenderedProposal
    agent_run_id: str
    scope_decision_id: str
    audit_record_ids: tuple[str, ...]
    replayed: bool = False


class LocalGoldenPathResult(StrictFrozenContractModel):
    demo_mode: Literal["post_acceptance_change_order"]
    initial: LocalInitialProposalResult
    final_project: ProjectRecord
    accepted_baseline: ScopeVersion
    scope_events: tuple[ScopeEventRecord, ...]
    finalized_buffer: ScopeBufferRecord
    proposed_change_scope: ScopeVersion
    artifacts: tuple[CommercialArtifact, ...]
    approvals: tuple[ApprovalRecord, ...]
    send_intents: tuple[SendIntent, ...]
    elapsed_seconds: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_demo_story(self) -> "LocalGoldenPathResult":
        if len(self.approvals) != 2 or len(self.send_intents) != 2:
            raise ValueError("Golden path requires exactly two approvals and send intents")
        if any(
            intent.approval_id not in {approval.id for approval in self.approvals}
            for intent in self.send_intents
        ):
            raise ValueError("Every send intent must reference an explicit approval")
        return self

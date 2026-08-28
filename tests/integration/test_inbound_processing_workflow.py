import asyncio
import hashlib
from datetime import timedelta
from pathlib import Path

from scopelock.domain.enums import (
    InboundProcessingStatus,
    ProjectLifecycleStatus,
    ScopeBufferStatus,
    ScopeEventClassification,
)
from scopelock.domain.models import (
    AgentRun,
    AgentRunStatus,
    ClientConstraint,
    EvidenceRef,
    RequirementAnalysis,
    ScopeAnalysis,
    ScopeEventProposal,
    UnsupportedRequirement,
)
from scopelock.domain.workflow_models import (
    AnalysisContext,
    InboundEmail,
    ProjectRecord,
    ScopeBufferRecord,
)
from scopelock.repositories.in_memory import InMemoryApplicationRepository
from scopelock.services.inbound_processing_workflow import InboundProcessingWorkflow
from scopelock.services.sop_service import load_sop
from scopelock.testing.local_golden_path import load_local_golden_fixture


class FakeGateway:
    def __init__(self, requirement_analysis, scope_factory=None):
        self.requirement_analysis = requirement_analysis
        self.scope_factory = scope_factory
        self.requirement_calls = 0
        self.scope_calls = 0

    @staticmethod
    def _run(context, output, *, correlation_id, agent_name, prompt_version):
        return AgentRun(
            id=f"run-{context.current_email.message_id}",
            correlation_id=correlation_id,
            project_id=context.current_scope.project_id if context.current_scope else None,
            trigger_type="gmail_message",
            trigger_ref=context.current_email.message_id,
            agent_name=agent_name,
            model="fake-model",
            prompt_version=prompt_version,
            started_at=context.current_email.received_at,
            completed_at=context.current_email.received_at,
            status=AgentRunStatus.COMPLETED,
            input_hash=hashlib.sha256(context.current_email.body.encode()).hexdigest(),
            output=output,
        )

    async def analyze_requirements(self, context, *, correlation_id=None, **_):
        self.requirement_calls += 1
        return self._run(
            context,
            self.requirement_analysis,
            correlation_id=correlation_id,
            agent_name="requirement_analyzer",
            prompt_version="requirement_analyzer_v5",
        )

    async def analyze_scope(self, context, *, correlation_id=None, **_):
        self.scope_calls += 1
        output = self.scope_factory(context)
        return self._run(
            context,
            output,
            correlation_id=correlation_id,
            agent_name="scope_analyzer",
            prompt_version="scope_analyzer_v3",
        )


def _workflow(tmp_path: Path, analysis, *, scope_factory=None):
    email, _, _ = load_local_golden_fixture()
    repository = InMemoryApplicationRepository(clock=lambda: email.received_at)
    gateway = FakeGateway(analysis, scope_factory)
    workflow = InboundProcessingWorkflow(
        catalog=load_sop("config/jvl_sop.example.yaml"),
        repository=repository,
        artifact_root=tmp_path,
        gateway=gateway,
    )
    return email, repository, gateway, workflow


def test_irrelevant_email_records_run_without_creating_project(tmp_path):
    analysis = RequirementAnalysis(
        is_project_request=False,
        project_title="",
        objective="",
        requirements=[],
        selected_sop_modules=[],
        proposal_ready=False,
        confidence=1,
        source_language="en",
    )
    email, repository, _, workflow = _workflow(tmp_path, analysis)

    result = asyncio.run(workflow.process(email))

    assert result.status == InboundProcessingStatus.IGNORED
    assert repository.list(collection="projects") == ()
    assert len(repository.list(collection="inbound_messages")) == 1
    assert len(repository.list(collection="agent_runs")) == 1
    assert repository.list(collection="artifacts") == ()


def test_mixed_scope_keeps_supported_mapping_but_creates_no_artifact(tmp_path):
    email, analysis, _ = load_local_golden_fixture()
    mixed = analysis.model_copy(
        update={
            "selected_sop_modules": analysis.selected_sop_modules[:2],
            "unsupported_requirements": [
                UnsupportedRequirement(
                    requirement_id="REQ-99",
                    description="Synchronize Salesforce records.",
                    reason="No matching semantic SOP module.",
                    evidence=[
                        EvidenceRef(
                            source_type="gmail",
                            source_id=email.message_id,
                            quote_or_rule="shared Gmail inbox",
                        )
                    ],
                )
            ],
            "proposal_ready": False,
            "source_language": "en",
        }
    )
    _, repository, _, workflow = _workflow(tmp_path, mixed)

    result = asyncio.run(workflow.process(email))

    assert result.status == InboundProcessingStatus.NEEDS_REVIEW
    project = ProjectRecord.model_validate(repository.list(collection="projects")[0].payload)
    assert project.lifecycle_status == ProjectLifecycleStatus.NEEDS_CLARIFICATION
    assert repository.list(collection="artifacts") == ()
    assert repository.list(collection="scope_versions") == ()
    run = AgentRun.model_validate(repository.list(collection="agent_runs")[0].payload)
    assert [item.module_key for item in run.output.selected_sop_modules] == [
        "core_workflow_automation",
        "email_intake",
    ]


def test_proposal_ready_message_uses_one_agent_run_and_replays_before_model(tmp_path):
    email, analysis, _ = load_local_golden_fixture()
    _, repository, gateway, workflow = _workflow(tmp_path, analysis)

    first = asyncio.run(workflow.process(email))
    replay = asyncio.run(workflow.process(email))

    assert first.status == InboundProcessingStatus.PROPOSAL_CREATED
    assert replay.replayed is True
    assert replay.artifact_id == first.artifact_id
    assert gateway.requirement_calls == 1
    assert len(repository.list(collection="agent_runs")) == 1
    assert len(repository.list(collection="artifacts")) == 1


def test_known_scope_records_multiple_atomic_events_and_buffer(tmp_path):
    email, analysis, _ = load_local_golden_fixture()

    def scope_factory(context: AnalysisContext) -> ScopeAnalysis:
        assert context.current_scope is not None
        body = context.current_email.body
        baseline_quote = context.current_scope.requirements[0].description
        common = [
            EvidenceRef(
                source_type="gmail",
                source_id=context.current_email.message_id,
                quote_or_rule=body,
            ),
            EvidenceRef(
                source_type="scope_version",
                source_id=context.current_scope.id,
                quote_or_rule=baseline_quote,
            ),
        ]
        return ScopeAnalysis(
            events=[
                ScopeEventProposal(
                    classification=ScopeEventClassification.EXPANSION,
                    description="Add LINE notifications.",
                    sop_module_keys=["line_notifications"],
                    quantities=[{"module_key": "line_notifications", "quantity": 1}],
                    rationale="New supported notification channel.",
                    evidence=[
                        *common,
                        EvidenceRef(
                            source_type="sop",
                            source_id="line_notifications",
                            source_version="jvl-demo-v1",
                            quote_or_rule="Send workflow notifications through LINE.",
                        ),
                    ],
                    confidence=95,
                ),
                ScopeEventProposal(
                    classification=ScopeEventClassification.REDUCTION,
                    description="Remove email notifications.",
                    affected_requirement_ids=["REQ-04"],
                    sop_module_keys=["email_notifications"],
                    rationale="Client replaced the prior channel requirement.",
                    evidence=[
                        *common,
                        EvidenceRef(
                            source_type="sop",
                            source_id="email_notifications",
                            source_version="jvl-demo-v1",
                            quote_or_rule="Email alerts for predefined workflow events.",
                        ),
                    ],
                    confidence=95,
                ),
            ],
            conversation_closure=False,
            overall_confidence=95,
            source_language="en",
        )

    _, repository, gateway, workflow = _workflow(
        tmp_path,
        analysis,
        scope_factory=scope_factory,
    )
    initial = asyncio.run(workflow.process(email))
    followup = InboundEmail(
        message_id="gmail-golden-scope-1",
        thread_id=email.thread_id,
        sender_name=email.sender_name,
        sender_email=email.sender_email,
        subject="Change notification channels",
        body="Please add LINE notifications and remove email notifications.",
        received_at=email.received_at + timedelta(minutes=5),
    )

    result = asyncio.run(workflow.process(followup))

    assert initial.status == InboundProcessingStatus.PROPOSAL_CREATED
    assert result.status == InboundProcessingStatus.SCOPE_EVENTS_RECORDED
    assert len(result.scope_event_ids) == 2
    assert gateway.scope_calls == 1
    assert len(repository.list(collection="scope_events")) == 2
    assert len(repository.list(collection="buffers")) == 1


def _rebind_requirement_analysis(analysis, *, message_id):
    selections = []
    for selection in analysis.selected_sop_modules:
        selections.append(
            selection.model_copy(
                update={
                    "evidence": [
                        item.model_copy(update={"source_id": message_id})
                        if item.source_type == "gmail"
                        else item
                        for item in selection.evidence
                    ]
                }
            )
        )
    return analysis.model_copy(
        update={
            "selected_sop_modules": selections,
            "evidence": [
                item.model_copy(update={"source_id": message_id})
                if item.source_type == "gmail"
                else item
                for item in analysis.evidence
            ],
        }
    )


def test_clarification_followup_reuses_project_and_reruns_requirement_agent(tmp_path):
    email, analysis, _ = load_local_golden_fixture()
    incomplete = analysis.model_copy(
        update={
            "proposal_ready": False,
            "missing_critical_information": ["Confirm the workflow output."],
        }
    )
    _, repository, gateway, workflow = _workflow(tmp_path, incomplete)
    first = asyncio.run(workflow.process(email))
    followup = email.model_copy(
        update={
            "message_id": "gmail-golden-clarification",
            "received_at": email.received_at + timedelta(minutes=1),
        }
    )
    gateway.requirement_analysis = _rebind_requirement_analysis(
        analysis,
        message_id=followup.message_id,
    )

    second = asyncio.run(workflow.process(followup))

    assert first.status == InboundProcessingStatus.NEEDS_REVIEW
    assert second.status == InboundProcessingStatus.PROPOSAL_CREATED
    assert first.project_id == second.project_id
    assert gateway.requirement_calls == 2
    assert len(repository.list(collection="projects")) == 1
    assert len(repository.list(collection="scope_versions")) == 1


def test_deadline_and_budget_constraints_do_not_change_deterministic_commerce(tmp_path):
    email, analysis, _ = load_local_golden_fixture()
    constrained_email = email.model_copy(
        update={
            "body": (
                email.body
                + "\nOur budget limit is USD 1.00 and requested deadline is 2026-10-01."
            )
        }
    )
    constrained = analysis.model_copy(
        update={
            "client_constraints": [
                ClientConstraint(
                    kind="REQUESTED_DEADLINE",
                    value_text="2026-10-01",
                    normalized_date="2026-10-01",
                    evidence=[
                        EvidenceRef(
                            source_type="gmail",
                            source_id=email.message_id,
                            quote_or_rule="requested deadline is 2026-10-01",
                        )
                    ],
                ),
                ClientConstraint(
                    kind="BUDGET_LIMIT",
                    value_text="USD 1.00",
                    amount="1.00",
                    currency="USD",
                    evidence=[
                        EvidenceRef(
                            source_type="gmail",
                            source_id=email.message_id,
                            quote_or_rule="budget limit is USD 1.00",
                        )
                    ],
                ),
            ]
        }
    )
    _, repository, _, workflow = _workflow(tmp_path, constrained)

    result = asyncio.run(workflow.process(constrained_email))
    project = ProjectRecord.model_validate(repository.list(collection="projects")[0].payload)

    assert result.status == InboundProcessingStatus.PROPOSAL_CREATED
    assert project.current_price_usd == 5_650
    assert project.current_timeline_days == 5


def test_closure_before_multiple_changes_still_finalizes_the_buffer(tmp_path):
    email, analysis, _ = load_local_golden_fixture()

    def scope_factory(context: AnalysisContext) -> ScopeAnalysis:
        assert context.current_scope is not None
        common = [
            EvidenceRef(
                source_type="gmail",
                source_id=context.current_email.message_id,
                quote_or_rule=context.current_email.body,
            ),
            EvidenceRef(
                source_type="scope_version",
                source_id=context.current_scope.id,
                quote_or_rule=context.current_scope.requirements[0].description,
            ),
        ]
        events = [
            ScopeEventProposal(
                classification=ScopeEventClassification.CLOSURE,
                description="The client says this is everything.",
                rationale="Explicit closure.",
                evidence=common,
                confidence=95,
            )
        ]
        for key in ("line_notifications", "line_approval"):
            events.append(
                ScopeEventProposal(
                    classification=ScopeEventClassification.EXPANSION,
                    description=f"Add {key}.",
                    sop_module_keys=[key],
                    quantities=[{"module_key": key, "quantity": 1}],
                    rationale="Independent supported expansion.",
                    evidence=[
                        *common,
                        EvidenceRef(
                            source_type="sop",
                            source_id=key,
                            source_version="jvl-demo-v1",
                            quote_or_rule=key,
                        ),
                    ],
                    confidence=95,
                )
            )
        return ScopeAnalysis(
            events=events,
            conversation_closure=True,
            overall_confidence=95,
            source_language="en",
        )

    _, repository, _, workflow = _workflow(
        tmp_path,
        analysis,
        scope_factory=scope_factory,
    )
    asyncio.run(workflow.process(email))
    followup = email.model_copy(
        update={
            "message_id": "gmail-golden-close-and-change",
            "body": "Add LINE notifications and LINE approval. That's everything.",
            "received_at": email.received_at + timedelta(minutes=5),
        }
    )

    result = asyncio.run(workflow.process(followup))
    buffer = ScopeBufferRecord.model_validate(
        repository.list(collection="buffers")[0].payload
    )

    assert result.status == InboundProcessingStatus.SCOPE_EVENTS_RECORDED
    assert len(result.scope_event_ids) == 3
    assert buffer.status == ScopeBufferStatus.READY_TO_FINALIZE

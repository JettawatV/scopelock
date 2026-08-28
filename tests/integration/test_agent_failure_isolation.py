"""Unsafe semantic output must stop before any commercial side effect."""

from __future__ import annotations

from pathlib import Path

import pytest

from scopelock.repositories.in_memory import InMemoryApplicationRepository
from scopelock.domain.models import AgentRun, AgentRunStatus
from scopelock.services.initial_proposal_workflow import InitialProposalWorkflow
from scopelock.services.semantic_contracts import SemanticContractViolation
from scopelock.services.sop_service import load_sop
from scopelock.testing.local_golden_path import load_local_golden_fixture


COMMERCIAL_COLLECTIONS = (
    "scope_versions",
    "artifacts",
    "artifact_events",
    "approvals",
    "sends",
    "audit_records",
    "workflow_results",
)


def _run_with_analysis(tmp_path: Path, analysis):
    email, _, _ = load_local_golden_fixture()
    repository = InMemoryApplicationRepository(clock=lambda: email.received_at)
    workflow = InitialProposalWorkflow(
        catalog=load_sop("config/jvl_sop.example.yaml"),
        repository=repository,
        analyzer=lambda _: analysis,
        artifact_root=tmp_path,
    )
    return email, repository, workflow


@pytest.mark.parametrize("unsafe_kind", ["missing_evidence", "unknown_module", "commerce_text"])
def test_unsafe_requirement_output_creates_zero_commercial_records(
    tmp_path,
    unsafe_kind,
):
    _, analysis, _ = load_local_golden_fixture()
    first = analysis.selected_sop_modules[0]
    if unsafe_kind == "missing_evidence":
        unsafe = analysis.model_copy(
            update={
                "selected_sop_modules": [
                    first.model_copy(update={"evidence": []}),
                    *analysis.selected_sop_modules[1:],
                ]
            }
        )
    elif unsafe_kind == "unknown_module":
        unsafe = analysis.model_copy(
            update={
                "selected_sop_modules": [
                    first.model_copy(update={"module_key": "invented_module"}),
                    *analysis.selected_sop_modules[1:],
                ]
            }
        )
    else:
        unsafe = analysis.model_copy(
            update={"objective": "Set the price and send immediately."}
        )

    _, repository, workflow = _run_with_analysis(tmp_path, unsafe)

    with pytest.raises(SemanticContractViolation):
        workflow.run(load_local_golden_fixture()[0])

    assert len(repository.list(collection="projects")) == 1
    run = AgentRun.model_validate(repository.list(collection="agent_runs")[0].payload)
    assert run.status == AgentRunStatus.NEEDS_REVIEW
    assert run.output is None
    assert run.error is not None
    assert len(repository.list(collection="scope_decisions")) == 0
    for collection in COMMERCIAL_COLLECTIONS:
        assert len(repository.list(collection=collection)) == 0
    assert list(tmp_path.rglob("*")) == []


def test_model_exception_is_recorded_and_cannot_reach_commerce(tmp_path):
    email, _, _ = load_local_golden_fixture()
    repository = InMemoryApplicationRepository(clock=lambda: email.received_at)

    def timed_out(_):
        raise TimeoutError("Vertex model request timed out")

    workflow = InitialProposalWorkflow(
        catalog=load_sop("config/jvl_sop.example.yaml"),
        repository=repository,
        analyzer=timed_out,
        artifact_root=tmp_path,
    )

    with pytest.raises(TimeoutError):
        workflow.run(email)

    run = AgentRun.model_validate(repository.list(collection="agent_runs")[0].payload)
    assert run.status == AgentRunStatus.FAILED
    assert run.output is None
    assert run.error is not None
    assert run.error.category == "TimeoutError"
    for collection in COMMERCIAL_COLLECTIONS:
        assert len(repository.list(collection=collection)) == 0
    assert list(tmp_path.rglob("*")) == []

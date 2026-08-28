import json
import subprocess
import sys
from pathlib import Path

from scopelock.domain.enums import ArtifactStatus, ProjectLifecycleStatus
from scopelock.domain.models import AgentRun
from scopelock.repositories.in_memory import InMemoryApplicationRepository
from scopelock.services.initial_proposal_workflow import InitialProposalWorkflow
from scopelock.services.proposal_service import verify_rendered_proposal
from scopelock.services.sop_service import load_sop
from scopelock.testing.local_golden_path import load_local_golden_fixture


def build_workflow(tmp_path: Path):
    email, analysis, _ = load_local_golden_fixture()
    repository = InMemoryApplicationRepository(clock=lambda: email.received_at)
    workflow = InitialProposalWorkflow(
        catalog=load_sop("config/jvl_sop.example.yaml"),
        repository=repository,
        analyzer=lambda _: analysis,
        artifact_root=tmp_path,
    )
    return email, repository, workflow


def test_initial_vertical_path_produces_complete_reviewable_proposal(tmp_path):
    email, repository, workflow = build_workflow(tmp_path)
    result = workflow.run(email)

    assert result.project.lifecycle_status == ProjectLifecycleStatus.AWAITING_USER_REVIEW
    assert result.artifact.status == ArtifactStatus.AWAITING_USER_REVIEW
    assert result.proposal.currency == "USD"
    assert result.proposal.total_usd == 5650
    assert result.proposal.timeline.total_days == 5
    assert len(result.proposal.requirements) == 4
    assert {item.module_key for item in result.proposal.selected_modules} == {
        "core_workflow_automation",
        "email_intake",
        "operations_dashboard",
        "email_notifications",
    }
    assert result.proposal.assumptions
    assert result.proposal.exclusions
    assert result.proposal.evidence
    assert verify_rendered_proposal(result.rendered_proposal)
    assert result.rendered_proposal.source_scope_version_id == result.scope_version_id
    assert result.rendered_proposal.sop_version == "jvl-demo-v1"

    assert len(repository.list(collection="agent_runs")) == 1
    assert len(repository.list(collection="scope_decisions")) == 1
    assert len(repository.list(collection="tool_actions")) == 2
    assert len(repository.list(collection="state_transitions")) == 2
    assert len(repository.list(collection="artifact_events")) == 1
    audit_actions = {
        item.payload["action"] for item in repository.list(collection="audit_records")
    }
    assert audit_actions == {
        "calculate_price",
        "calculate_timeline",
        "render_fixed_template",
    }

    run_document = repository.list(collection="agent_runs")[0]
    run = AgentRun.model_validate(run_document.payload)
    semantic_payload = run.output.model_dump()
    assert "total_usd" not in semantic_payload
    assert "timeline_days" not in semantic_payload


def test_initial_vertical_path_replay_is_idempotent(tmp_path):
    email, repository, workflow = build_workflow(tmp_path)
    first = workflow.run(email)
    replay = workflow.run(email)

    assert replay.replayed is True
    assert replay.artifact.id == first.artifact.id
    assert replay.scope_version_id == first.scope_version_id
    assert replay.rendered_proposal.content_checksum == first.rendered_proposal.content_checksum
    assert len(repository.list(collection="projects")) == 1
    assert len(repository.list(collection="scope_versions")) == 1
    assert len(repository.list(collection="artifacts")) == 1
    assert len(repository.list(collection="workflow_results")) == 1


def test_documented_initial_proposal_command_runs_from_repository_root(tmp_path):
    command = [
        sys.executable,
        "-m",
        "scopelock.cli",
        "initial-proposal",
        "--output",
        str(tmp_path),
        "--repeat",
        "2",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=True)
    output = json.loads(completed.stdout)

    assert output["project_status"] == "AWAITING_USER_REVIEW"
    assert output["artifact_status"] == "AWAITING_USER_REVIEW"
    assert output["currency"] == "USD"
    assert output["total_usd"] == 5650
    assert output["timeline_days"] == 5
    assert output["replayed"] is True
    assert output["artifacts"] == 1

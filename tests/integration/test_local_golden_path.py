import json
import subprocess
import sys
from pathlib import Path

from scopelock.domain.enums import (
    ArtifactType,
    ProjectLifecycleStatus,
    ScopeEventClassification,
    ScopeVersionStatus,
)
from scopelock.repositories.in_memory import InMemoryApplicationRepository
from scopelock.services.golden_path_rehearsal import GoldenPathRehearsal
from scopelock.services.sop_service import load_sop
from scopelock.testing.local_golden_path import load_local_golden_fixture


def run_rehearsal(tmp_path: Path):
    email, analysis, followups = load_local_golden_fixture()
    repository = InMemoryApplicationRepository(clock=lambda: email.received_at)
    result = GoldenPathRehearsal(
        catalog=load_sop("config/jvl_sop.example.yaml"),
        repository=repository,
        artifact_root=tmp_path,
    ).run(email=email, analysis=analysis, followups=followups)
    return repository, result


def test_complete_local_golden_path_is_approval_gated_and_evidence_backed(tmp_path):
    repository, result = run_rehearsal(tmp_path)

    assert result.demo_mode == "post_acceptance_change_order"
    assert result.final_project.lifecycle_status == ProjectLifecycleStatus.ACTIVE_PROJECT
    assert result.accepted_baseline.status == ScopeVersionStatus.ACCEPTED
    assert result.accepted_baseline.total_price_usd == 5650
    assert result.accepted_baseline.timeline_days == 5
    assert result.finalized_buffer.net_price_delta_usd == 1500
    assert result.finalized_buffer.net_timeline_delta_days == 5
    assert result.proposed_change_scope.total_price_usd == 7150
    assert result.proposed_change_scope.timeline_days == 10
    assert [event.classification for event in result.scope_events] == [
        ScopeEventClassification.NO_CHANGE,
        ScopeEventClassification.EXPANSION,
        ScopeEventClassification.CLOSURE,
    ]
    assert result.scope_events[0].evidence
    assert result.scope_events[1].evidence
    assert [artifact.artifact_type for artifact in result.artifacts] == [
        ArtifactType.PROPOSAL,
        ArtifactType.CHANGE_ORDER,
    ]
    assert len(result.approvals) == len(result.send_intents) == 2
    assert {
        intent.approval_id for intent in result.send_intents
    } == {approval.id for approval in result.approvals}
    assert {intent.gmail_thread_id for intent in result.send_intents} == {
        "gmail-thread-golden-001"
    }
    assert len(repository.list(collection="sends")) == 2
    assert result.elapsed_seconds < 240


def test_golden_path_repeats_from_clean_state_with_same_commerce(tmp_path):
    first_repo, first = run_rehearsal(tmp_path / "first")
    second_repo, second = run_rehearsal(tmp_path / "second")

    assert first.accepted_baseline.pricing_result == second.accepted_baseline.pricing_result
    assert first.proposed_change_scope.pricing_result == second.proposed_change_scope.pricing_result
    assert first.finalized_buffer.net_price_delta_usd == second.finalized_buffer.net_price_delta_usd
    assert first.finalized_buffer.net_timeline_delta_days == second.finalized_buffer.net_timeline_delta_days
    assert len(first_repo.list(collection="projects")) == 1
    assert len(second_repo.list(collection="projects")) == 1


def test_documented_golden_path_command_runs_under_four_minutes(tmp_path):
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scopelock.cli",
            "golden-path",
            "--output",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=240,
    )
    output = json.loads(completed.stdout)

    assert output["demo_mode"] == "post_acceptance_change_order"
    assert output["final_project_status"] == "ACTIVE_PROJECT"
    assert output["price_delta_usd"] == 1500
    assert output["timeline_delta_days"] == 5
    assert output["approvals"] == output["send_intents"] == 2
    assert output["elapsed_seconds"] < 240

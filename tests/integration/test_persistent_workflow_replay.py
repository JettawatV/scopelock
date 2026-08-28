from datetime import datetime, timezone

import pytest

from scopelock.domain.enums import ArtifactStatus, ProjectLifecycleStatus, ScopeEventStatus
from scopelock.repositories.contracts import ImmutableDocumentError
from scopelock.repositories.in_memory import InMemoryApplicationRepository
from scopelock.services.golden_path_rehearsal import GoldenPathRehearsal
from scopelock.services.sop_service import load_sop
from scopelock.testing.local_golden_path import load_local_golden_fixture
from scopelock.domain.state_machines import transition_project


class FailOnceRepository:
    def __init__(self, wrapped, collection):
        self.wrapped = wrapped
        self.collection = collection
        self.failed = False

    def create_or_get(self, **kwargs):
        if kwargs["collection"] == self.collection and not self.failed:
            self.failed = True
            raise ConnectionError(f"injected {self.collection} write failure")
        return self.wrapped.create_or_get(**kwargs)

    def get(self, **kwargs):
        return self.wrapped.get(**kwargs)

    def list(self, **kwargs):
        return self.wrapped.list(**kwargs)

    def compare_and_set(self, **kwargs):
        return self.wrapped.compare_and_set(**kwargs)


def rehearsal(repository, tmp_path):
    email, analysis, followups = load_local_golden_fixture()
    service = GoldenPathRehearsal(
        catalog=load_sop("config/jvl_sop.example.yaml"),
        repository=repository,
        artifact_root=tmp_path,
    )
    return service, email, analysis, followups


def test_replaying_complete_fixture_creates_no_duplicate_business_records(tmp_path):
    email, _, _ = load_local_golden_fixture()
    repository = InMemoryApplicationRepository(clock=lambda: email.received_at)
    service, email, analysis, followups = rehearsal(repository, tmp_path)
    first = service.run(email=email, analysis=analysis, followups=followups)
    counts = {
        collection: len(repository.list(collection=collection))
        for collection in (
            "projects",
            "scope_versions",
            "scope_events",
            "buffers",
            "artifacts",
            "approvals",
            "sends",
        )
    }
    second_service, _, _, _ = rehearsal(repository, tmp_path)
    replay = second_service.run(email=email, analysis=analysis, followups=followups)

    assert replay == first
    assert counts == {
        collection: len(repository.list(collection=collection))
        for collection in counts
    }
    assert counts == {
        "projects": 1,
        "scope_versions": 2,
        "scope_events": 3,
        "buffers": 1,
        "artifacts": 2,
        "approvals": 2,
        "sends": 2,
    }


def test_stored_final_state_and_transition_history_match_explicit_machines(tmp_path):
    email, _, _ = load_local_golden_fixture()
    repository = InMemoryApplicationRepository(clock=lambda: email.received_at)
    service, email, analysis, followups = rehearsal(repository, tmp_path)
    service.run(email=email, analysis=analysis, followups=followups)

    project = repository.list(collection="projects")[0].payload
    artifacts = [item.payload for item in repository.list(collection="artifacts")]
    events = [item.payload for item in repository.list(collection="scope_events")]
    buffer = repository.list(collection="buffers")[0].payload

    assert project["lifecycle_status"] == ProjectLifecycleStatus.ACTIVE_PROJECT.value
    assert {item["status"] for item in artifacts} == {
        ArtifactStatus.ACCEPTED.value,
        ArtifactStatus.SENT.value,
    }
    assert {item["status"] for item in events} == {
        ScopeEventStatus.RECORDED.value,
        ScopeEventStatus.SENT.value,
    }
    assert buffer["status"] == "FINALIZED"
    for item in repository.list(collection="state_transitions"):
        transition = item.payload
        if transition["entity_type"] == "project":
            assert transition_project(
                ProjectLifecycleStatus(transition["from_status"]),
                ProjectLifecycleStatus(transition["to_status"]),
            ) == ProjectLifecycleStatus(transition["to_status"])


def test_failed_approval_write_creates_no_send_and_is_recoverable(tmp_path):
    email, _, _ = load_local_golden_fixture()
    base_repository = InMemoryApplicationRepository(clock=lambda: email.received_at)
    failing = FailOnceRepository(base_repository, "approvals")
    service, email, analysis, followups = rehearsal(failing, tmp_path)

    with pytest.raises(ConnectionError, match="injected approvals"):
        service.run(email=email, analysis=analysis, followups=followups)
    assert base_repository.list(collection="sends") == ()
    assert base_repository.list(collection="golden_path_results") == ()

    recovered_service, _, _, _ = rehearsal(failing, tmp_path)
    recovered = recovered_service.run(
        email=email, analysis=analysis, followups=followups
    )
    assert len(recovered.send_intents) == 2
    assert len(base_repository.list(collection="sends")) == 2


def test_accepted_scope_document_is_immutable_in_storage(tmp_path):
    email, _, _ = load_local_golden_fixture()
    repository = InMemoryApplicationRepository(clock=lambda: email.received_at)
    service, email, analysis, followups = rehearsal(repository, tmp_path)
    result = service.run(email=email, analysis=analysis, followups=followups)
    stored = repository.get(
        collection="scope_versions", document_id=result.accepted_baseline.id
    )
    assert stored is not None and stored.immutable
    changed = dict(stored.payload)
    changed["total_price_usd"] = 1

    with pytest.raises(ImmutableDocumentError):
        repository.compare_and_set(
            collection="scope_versions",
            document_id=stored.document_id,
            expected_revision=stored.revision,
            payload=changed,
        )

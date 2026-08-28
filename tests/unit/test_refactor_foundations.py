from datetime import datetime, timezone

import pytest
from pydantic import BaseModel, ConfigDict

from scopelock.domain.enums import ProjectLifecycleStatus, ScopeEventClassification
from scopelock.domain.models import ModuleQuantity, ScopeRequirementSnapshot
from scopelock.domain.workflow_models import ProjectRecord
from scopelock.repositories.contracts import DocumentNotFoundError
from scopelock.repositories.in_memory import InMemoryApplicationRepository
from scopelock.repositories.model_store import CollectionName, ModelStore
from scopelock.services.golden_path_scenario import GoldenPathScenarioBuilder
from scopelock.services.identity import stable_hash, stable_id
from scopelock.services.commercial_artifact_service import (
    accept_scope_version,
    create_scope_version,
)
from scopelock.services.pricing_engine import PricingEngine
from scopelock.services.sop_service import load_sop
from scopelock.services.timeline_engine import TimelineEngine
from scopelock.services.workflow_state import advance_project
from scopelock.testing.local_golden_path import load_local_golden_fixture


NOW = datetime(2026, 8, 28, tzinfo=timezone.utc)


class DemoRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    value: int


def accepted_baseline():
    catalog = load_sop("config/jvl_sop.example.yaml")
    selections = tuple(
        ModuleQuantity(module_key=key, quantity=1)
        for key in (
            "core_workflow_automation",
            "email_intake",
            "operations_dashboard",
            "email_notifications",
        )
    )
    pricing = PricingEngine(catalog).calculate(selections)
    timeline = TimelineEngine(catalog).calculate(selections)
    proposed = create_scope_version(
        project_id="project-refactor",
        existing=(),
        requirements=(
            ScopeRequirementSnapshot(
                requirement_id="REQ-01",
                category="Workflow",
                description="Golden baseline",
                normalized_key="golden_baseline",
                source_message_id="message-1",
                source_quote="golden baseline",
            ),
        ),
        module_selections=timeline.calculation_inputs,
        pricing_result=pricing,
        timeline_result=timeline,
        scope_version_id="scope-refactor",
        created_at=NOW,
    )
    return accept_scope_version(proposed)


def test_model_store_centralizes_typed_create_get_and_cas_replace():
    repository = InMemoryApplicationRepository(clock=lambda: NOW)
    store = ModelStore(repository)
    original = DemoRecord(id="record-1", value=1)

    store.create(CollectionName.EVAL_RESULTS, original)
    assert store.get(CollectionName.EVAL_RESULTS, original.id, DemoRecord) == original

    updated = original.model_copy(update={"value": 2})
    stored = store.replace(CollectionName.EVAL_RESULTS, updated)
    assert stored.revision == 2
    assert store.get(CollectionName.EVAL_RESULTS, original.id, DemoRecord) == updated


def test_model_store_raises_explicitly_for_missing_cas_target():
    store = ModelStore(InMemoryApplicationRepository(clock=lambda: NOW))
    with pytest.raises(DocumentNotFoundError):
        store.replace(
            CollectionName.EVAL_RESULTS,
            DemoRecord(id="missing", value=1),
        )


def test_shared_identity_and_project_transition_helpers_are_deterministic():
    project = ProjectRecord(
        id="project-1",
        client_name="Client",
        client_email="client@example.com",
        gmail_thread_id="thread-1",
        title="Project",
        lifecycle_status=ProjectLifecycleStatus.NEW,
        correlation_id="corr-1",
        created_at=NOW,
        updated_at=NOW,
    )

    updated, transition = advance_project(
        project,
        ProjectLifecycleStatus.ANALYZING_REQUIREMENTS,
        reason="test",
        at=NOW,
    )

    assert project.lifecycle_status == ProjectLifecycleStatus.NEW
    assert updated.lifecycle_status == ProjectLifecycleStatus.ANALYZING_REQUIREMENTS
    assert transition.from_status == "NEW"
    assert transition.to_status == "ANALYZING_REQUIREMENTS"
    assert stable_hash("a", "b") == stable_hash("a", "b")
    assert stable_id("event", "message-1").startswith("event-")


def test_golden_scenario_builder_is_pure_and_returns_typed_followups():
    email, _, followups = load_local_golden_fixture()
    baseline = accepted_baseline()
    project = ProjectRecord(
        id=baseline.project_id,
        client_name="Client",
        client_email="client@example.com",
        gmail_thread_id=email.thread_id,
        title=email.subject,
        lifecycle_status=ProjectLifecycleStatus.ACTIVE_PROJECT,
        baseline_scope_version_id=baseline.id,
        active_scope_version_id=baseline.id,
        current_price_usd=baseline.total_price_usd,
        current_timeline_days=baseline.timeline_days,
        correlation_id="corr-scenario",
        created_at=email.received_at,
        updated_at=email.received_at,
    )

    events = GoldenPathScenarioBuilder.build(
        project=project,
        baseline=baseline,
        followups=followups,
        started_at=email.received_at,
    )

    assert events.clarification.classification == ScopeEventClassification.NO_CHANGE
    assert events.expansion.classification == ScopeEventClassification.EXPANSION
    assert events.closure.classification == ScopeEventClassification.CLOSURE
    assert {item.module_key for item in events.expansion.additions} == {
        "line_notifications",
        "line_approval",
    }

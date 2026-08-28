import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest

from scopelock.repositories.in_memory import InMemoryApplicationRepository
from scopelock.services.execution_boundaries import (
    BoundaryPolicy,
    BoundaryTimeoutError,
    WorkflowExecutionBoundaries,
    run_with_boundary,
)
from scopelock.services.idempotency_service import IdempotencyKeys


NOW = datetime(2026, 8, 28, tzinfo=timezone.utc)


def test_all_external_and_commercial_idempotency_keys_are_stable_and_namespaced():
    values = {
        IdempotencyKeys.gmail_message("m1"),
        IdempotencyKeys.gmail_thread("t1"),
        IdempotencyKeys.gmail_history("demo@example.com", "h1"),
        IdempotencyKeys.pubsub_event("p1"),
        IdempotencyKeys.artifact_version("project-1", "proposal", 1),
        IdempotencyKeys.approval("artifact-1", 1, "a" * 64),
        IdempotencyKeys.send_action("artifact-1", 1, "a" * 64, "thread-1"),
    }
    assert len(values) == 7
    assert all(len(value) == 64 for value in values)
    assert IdempotencyKeys.gmail_message("m1") == IdempotencyKeys.gmail_message("m1")


def test_concurrent_duplicate_create_resolves_to_one_canonical_document():
    repository = InMemoryApplicationRepository(clock=lambda: NOW)

    def create(index):
        return repository.create_or_get(
            collection="scope_events",
            document_id=f"event-{index}",
            payload={"attempt": index},
            unique_keys={"gmail_message_id": "message-canonical"},
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = tuple(executor.map(create, range(32)))

    assert len({result.document_id for result in results}) == 1
    assert len(repository.list(collection="scope_events")) == 1


def test_transient_call_retries_within_boundary_and_send_policy_never_blindly_retries():
    attempts = 0

    def transient():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionError("temporary")
        return "ok"

    result = run_with_boundary(
        transient,
        policy=BoundaryPolicy("test", timeout_seconds=1, max_attempts=3),
        sleeper=lambda _: None,
    )

    assert result == "ok"
    assert attempts == 3
    assert WorkflowExecutionBoundaries.external_send_policy.max_attempts == 1


def test_timeout_is_explicit_and_reviewable():
    with pytest.raises(BoundaryTimeoutError):
        run_with_boundary(
            lambda: time.sleep(0.05),
            policy=BoundaryPolicy("slow", timeout_seconds=0.001, max_attempts=1),
            sleeper=lambda _: None,
        )

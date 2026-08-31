import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import scopelock.http_api as http_api
from scopelock.domain.enums import EmailDirection, ProjectLifecycleStatus
from scopelock.domain.models import (
    AgentRun,
    AgentRunStatus,
    ToolAction,
    ToolActionPhase,
    ToolActionStatus,
)
from scopelock.domain.workflow_models import (
    GmailWatchRecord,
    InboundEmail,
    InboundMessageRecord,
    ProjectRecord,
)
from scopelock.http_api import GmailApiRuntime, create_app
from scopelock.repositories.in_memory import InMemoryApplicationRepository
from scopelock.repositories.model_store import CollectionName, ModelStore
from scopelock.services.dashboard_query_service import DashboardQueryService


NOW = datetime(2026, 8, 30, 7, 17, 46, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[2]


class _ProposalPdfService:
    def proposal_pdf(self, artifact_id: str) -> bytes:
        if artifact_id != "artifact-1":
            raise KeyError(artifact_id)
        return b"%PDF-1.4\n% ScopeLock test proposal\n"


def _dashboard_service() -> DashboardQueryService:
    repository = InMemoryApplicationRepository(clock=lambda: NOW)
    store = ModelStore(repository)
    store.create(
        CollectionName.PROJECTS,
        ProjectRecord(
            id="project-1",
            client_name="Client",
            client_email="client@example.com",
            gmail_thread_id="thread-1",
            title="Intake automation",
            lifecycle_status=ProjectLifecycleStatus.AWAITING_USER_REVIEW,
            correlation_id="corr-project",
            created_at=NOW,
            updated_at=NOW,
        ),
    )
    action = ToolAction(
        id="tool-1",
        agent_run_id="run-1",
        sequence=1,
        call_id="call-1",
        tool_name="get_sop_catalog",
        phase=ToolActionPhase.RESULT,
        status=ToolActionStatus.COMPLETED,
        payload={"raw_email_body": "must-not-leak"},
        recorded_at=NOW,
    )
    store.create(
        CollectionName.AGENT_RUNS,
        AgentRun(
            id="run-1",
            correlation_id="corr-run",
            project_id="project-1",
            trigger_type="gmail",
            trigger_ref="sensitive-message-id",
            agent_name="requirement_analyzer",
            model="gemini-3.5-flash",
            prompt_version="requirement_analyzer_v5",
            started_at=NOW,
            completed_at=NOW,
            status=AgentRunStatus.COMPLETED,
            input_hash="a" * 64,
            tool_trajectory=[action],
        ),
    )
    store.create(
        CollectionName.INBOUND_MESSAGES,
        InboundMessageRecord(
            id="inbound-1",
            email=InboundEmail(
                message_id="gmail-message-id-must-not-leak",
                thread_id="thread-1",
                sender_name="Client",
                sender_email="client@example.com",
                subject="Project requirements",
                body="Sensitive request body must-not-leak",
                received_at=NOW,
                recipient_emails=("hidden-recipient@example.com",),
                direction=EmailDirection.INBOUND,
                raw_content_hash="b" * 64,
            ),
            correlation_id="corr-inbound",
            created_at=NOW,
        ),
    )
    store.create(
        CollectionName.GMAIL_WATCHES,
        GmailWatchRecord(
            id="watch-1",
            mailbox="operator@example.com",
            topic_name="projects/example/topics/gmail",
            history_id="12345",
            expiration=NOW,
            created_at=NOW,
        ),
    )
    return DashboardQueryService(
        repository,
        readiness_path=ROOT / "config" / "agent_readiness.json",
        clock=lambda: NOW,
    )


def _runtime(service: DashboardQueryService) -> GmailApiRuntime:
    return GmailApiRuntime(
        event_service=None,
        watch_service=None,
        commercial_service=_ProposalPdfService(),
        revision_workflow=None,
        mailbox="demo@example.com",
        topic_name="projects/example/topics/gmail",
        operator_api_key="operator-secret",
        pubsub_verifier=None,
        dashboard_service=service,
    )


def test_dashboard_projection_is_bounded_and_redacts_agent_payloads():
    snapshot = _dashboard_service().overview()
    serialized = json.dumps(snapshot.model_dump(mode="json"))

    assert snapshot.readiness.status == "PASS"
    assert snapshot.projects[0].id == "project-1"
    assert snapshot.agent_runs[0].tool_count == 1
    assert snapshot.inbox_messages[0].subject == "Project requirements"
    assert snapshot.inbox_messages[0].project_id == "project-1"
    assert snapshot.gmail_watch is not None
    assert snapshot.gmail_watch.mailbox == "operator@example.com"
    assert "must-not-leak" not in serialized
    assert "Sensitive request body" not in serialized
    assert "gmail-message-id-must-not-leak" not in serialized
    assert "hidden-recipient@example.com" not in serialized
    assert "raw_content_hash" not in serialized
    assert "recipient_emails" not in serialized
    assert "history_id" not in serialized
    assert "sensitive-message-id" not in serialized
    assert "input_hash" not in serialized
    assert "tool_trajectory" not in serialized
    assert "output" not in serialized


def test_dashboard_http_requires_operator_key_and_returns_project_detail():
    client = TestClient(create_app(lambda: _runtime(_dashboard_service())))

    assert client.get("/api/dashboard").status_code == 401
    dashboard = client.get(
        "/api/dashboard",
        headers={"X-ScopeLock-Operator-Key": "operator-secret"},
    )
    session = client.get(
        "/api/session",
        headers={"X-ScopeLock-Operator-Key": "operator-secret"},
    )
    detail = client.get(
        "/api/projects/project-1",
        headers={"X-ScopeLock-Operator-Key": "operator-secret"},
    )
    message = client.get(
        "/api/messages/inbound-1",
        headers={"X-ScopeLock-Operator-Key": "operator-secret"},
    )
    unauthenticated_message = client.get("/api/messages/inbound-1")
    proposal_pdf = client.get(
        "/api/artifacts/artifact-1/proposal.pdf",
        headers={"X-ScopeLock-Operator-Key": "operator-secret"},
    )
    unauthenticated_pdf = client.get("/api/artifacts/artifact-1/proposal.pdf")

    assert dashboard.status_code == 200
    assert dashboard.json()["projects"][0]["id"] == "project-1"
    assert session.status_code == 200
    assert session.json() == {"status": "accepted"}
    assert detail.status_code == 200
    assert detail.json()["project"]["id"] == "project-1"
    assert message.status_code == 200
    assert message.json()["body"] == "Sensitive request body must-not-leak"
    assert "raw_content_hash" not in message.json()
    assert "recipient_emails" not in message.json()
    assert unauthenticated_message.status_code == 401
    assert proposal_pdf.status_code == 200
    assert proposal_pdf.headers["content-type"] == "application/pdf"
    assert proposal_pdf.content.startswith(b"%PDF-1.4")
    assert unauthenticated_pdf.status_code == 401


def test_operator_session_accepts_the_environment_key_without_starting_runtime(
    monkeypatch,
):
    def runtime_must_not_start():
        raise AssertionError("The session check must not initialize cloud runtime")

    key = "local-operator-key-for-safe-session-check"
    monkeypatch.setenv("SCOPELOCK_OPERATOR_API_KEY", key)
    monkeypatch.setattr(http_api, "build_default_runtime", runtime_must_not_start)
    client = TestClient(http_api.create_app())

    accepted = client.get("/api/session", headers={"X-ScopeLock-Operator-Key": key})
    rejected = client.get("/api/session")

    assert accepted.status_code == 200
    assert accepted.json() == {"status": "accepted"}
    assert rejected.status_code == 401


def test_static_frontend_gets_ui_csp_while_api_keeps_strict_csp(
    tmp_path, monkeypatch
):
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text(
        "<!doctype html><title>ScopeLock</title>", encoding="utf-8"
    )
    assets = frontend / "assets"
    assets.mkdir()
    (assets / "index.js").write_text("console.log('ok')", encoding="utf-8")
    monkeypatch.setenv("SCOPELOCK_FRONTEND_ROOT", str(frontend))
    client = TestClient(create_app(lambda: _runtime(_dashboard_service())))

    home = client.get("/")
    settings = client.get("/settings")
    settings_slash = client.get("/settings/")
    asset = client.get("/assets/index.js")
    health = client.get("/health")

    assert home.status_code == 200
    assert settings.status_code == 200
    assert settings_slash.status_code == 200
    assert "script-src 'self' 'unsafe-inline'" in settings.headers[
        "content-security-policy"
    ]
    assert asset.status_code == 200
    assert "ScopeLock" in home.text
    assert "script-src 'self' 'unsafe-inline'" in home.headers[
        "content-security-policy"
    ]
    assert "script-src 'self' 'unsafe-inline'" in asset.headers[
        "content-security-policy"
    ]
    assert "frame-src 'self' blob:" in home.headers["content-security-policy"]
    assert asset.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert health.headers["content-security-policy"] == (
        "default-src 'none'; frame-ancestors 'none'"
    )


def test_static_frontend_rejects_websocket_connections_cleanly(
    tmp_path, monkeypatch
):
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text(
        "<!doctype html><title>ScopeLock</title>", encoding="utf-8"
    )
    monkeypatch.setenv("SCOPELOCK_FRONTEND_ROOT", str(frontend))
    client = TestClient(create_app(lambda: _runtime(_dashboard_service())))

    with pytest.raises(WebSocketDisconnect) as rejected:
        with client.websocket_connect("/live-reload"):
            pass

    assert rejected.value.code == 1000


def test_static_frontend_falls_back_to_spa_entrypoint_for_client_routes(
    tmp_path, monkeypatch
):
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text(
        "<!doctype html><title>ScopeLock</title>", encoding="utf-8"
    )
    monkeypatch.setenv("SCOPELOCK_FRONTEND_ROOT", str(frontend))
    client = TestClient(create_app(lambda: _runtime(_dashboard_service())))

    route = client.get("/projects/")

    assert route.status_code == 200
    assert "ScopeLock" in route.text


def test_frontend_uses_vite_static_spa_contract():
    package = json.loads((ROOT / "frontend" / "package.json").read_text())

    assert package["scripts"]["dev"].startswith("vite")
    assert package["scripts"]["build"] == "vite build"
    assert package["scripts"]["lint"] == "tsc --noEmit"
    assert package["devDependencies"]["vite"] == "7.3.6"
    assert (ROOT / "frontend" / "index.html").exists()
    assert (ROOT / "frontend" / "src" / "globals.css").exists()
    assert (ROOT / "frontend" / "src" / "components" / "operator-app.tsx").exists()
    assert (
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "commercial-artifact-review.tsx"
    ).exists()
    assert (
        ROOT / "frontend" / "src" / "components" / "dashboard-primitives.tsx"
    ).exists()
    assert (ROOT / "frontend" / "src" / "lib" / "browser-storage.ts").exists()
    assert (ROOT / "frontend" / "src" / "lib" / "types.ts").exists()
    assert (ROOT / "frontend" / "vite.config.ts").exists()
    assert not (ROOT / "frontend" / "app").exists()

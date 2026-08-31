import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import scopelock.http_api as http_api
import scopelock.reviewer_auth as reviewer_auth
from scopelock.reviewer_auth import ReviewerIdentity, verify_reviewer_token
from tests.unit.test_dashboard_frontend import _dashboard_service, _runtime


def test_reviewer_token_requires_verified_email(monkeypatch):
    monkeypatch.setenv("SCOPELOCK_FIREBASE_PROJECT_ID", "scopelock-test")

    identity = verify_reviewer_token(
        "Bearer firebase-token",
        verifier=lambda token, request, audience: {
            "sub": "uid-1",
            "email": "Client@Example.com",
            "email_verified": True,
        },
    )

    assert identity == ReviewerIdentity(uid="uid-1", email="client@example.com")

    with pytest.raises(HTTPException) as rejected:
        verify_reviewer_token(
            "Bearer firebase-token",
            verifier=lambda token, request, audience: {
                "sub": "uid-1",
                "email": "client@example.com",
                "email_verified": False,
            },
        )
    assert rejected.value.status_code == 403


def test_reviewer_identity_accepts_gateway_token_header(monkeypatch):
    expected = ReviewerIdentity(uid="uid-1", email="client@example.com")
    seen = []
    monkeypatch.setattr(
        reviewer_auth,
        "verify_reviewer_token",
        lambda value: (seen.append(value), expected)[1],
    )
    identity = reviewer_auth.reviewer_identity(
        authorization="Bearer cloud-run-iam-token",
        reviewer_token="Bearer firebase-token",
    )

    assert identity == expected
    assert seen == ["Bearer firebase-token"]


def test_reviewer_dashboard_is_scoped_and_hides_demo_mailbox(monkeypatch):
    app = http_api.create_app(lambda: _runtime(_dashboard_service()))
    app.dependency_overrides[http_api.reviewer_identity] = lambda: ReviewerIdentity(
        uid="uid-1", email="client@example.com"
    )
    client = TestClient(app)

    dashboard = client.get("/api/reviewer/dashboard")
    message = client.get("/api/reviewer/messages/inbound-1")

    assert dashboard.status_code == 200
    assert [project["id"] for project in dashboard.json()["projects"]] == ["project-1"]
    assert dashboard.json()["gmail_watch"]["mailbox"] == "ScopeLock demo inbox"
    assert message.status_code == 200
    assert message.json()["body"] == "Sensitive request body must-not-leak"
    assert "recipient_emails" not in message.json()

    app.dependency_overrides[http_api.reviewer_identity] = lambda: ReviewerIdentity(
        uid="uid-2", email="other@example.com"
    )
    isolated = client.get("/api/reviewer/dashboard")
    hidden_message = client.get("/api/reviewer/messages/inbound-1")
    assert isolated.status_code == 200
    assert isolated.json()["projects"] == []
    assert hidden_message.status_code == 404


def test_reviewer_config_returns_only_public_firebase_values(monkeypatch):
    monkeypatch.setenv("SCOPELOCK_FIREBASE_PROJECT_ID", "scopelock-test")
    monkeypatch.setenv("SCOPELOCK_FIREBASE_API_KEY", "public-web-key")
    monkeypatch.setenv("SCOPELOCK_FIREBASE_AUTH_DOMAIN", "scopelock-test.firebaseapp.com")
    client = TestClient(http_api.create_app(lambda: _runtime(_dashboard_service())))

    response = client.get("/api/reviewer/config")

    assert response.status_code == 200
    assert response.json() == {
        "apiKey": "public-web-key",
        "authDomain": "scopelock-test.firebaseapp.com",
        "projectId": "scopelock-test",
    }
    assert "operator" not in response.text.lower()

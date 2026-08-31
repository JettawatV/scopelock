from fastapi.testclient import TestClient

import scopelock.reviewer_gateway as gateway


def test_reviewer_gateway_exposes_only_review_surface(monkeypatch):
    monkeypatch.setenv("SCOPELOCK_PRIVATE_API_URL", "https://private.example.run.app")
    client = TestClient(gateway.app, follow_redirects=False)

    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/").status_code == 307
    assert client.get("/").headers["location"] == "/review/"
    assert client.get("/settings").status_code == 404
    assert client.get("/api/reviewer/../api/dashboard").status_code in {404, 405}


def test_reviewer_gateway_forwards_firebase_token_separately(monkeypatch):
    seen = {}

    def fake_forward(**kwargs):
        seen.update(kwargs)
        return 200, b'{"status":"accepted"}', "application/json"

    monkeypatch.setenv("SCOPELOCK_PRIVATE_API_URL", "https://private.example.run.app")
    monkeypatch.setattr(gateway, "_forward_sync", fake_forward)
    monkeypatch.setattr(gateway, "_service_identity_token", lambda audience: "iam-token")
    client = TestClient(gateway.app)

    response = client.get(
        "/api/reviewer/session",
        headers={"Authorization": "Bearer firebase-token"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}
    assert seen["target_url"] == "https://private.example.run.app/api/reviewer/session"
    assert seen["reviewer_authorization"] == "Bearer firebase-token"

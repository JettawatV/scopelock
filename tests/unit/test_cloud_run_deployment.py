from pathlib import Path

import pytest

from scopelock.cloud_run import load_cloud_run_settings, main


ROOT = Path(__file__).resolve().parents[2]


def _environment() -> dict[str, str]:
    return {
        "PORT": "8080",
        "GOOGLE_CLOUD_PROJECT": "scopelock-506806",
        "GOOGLE_CLOUD_LOCATION": "us-central1",
        "GOOGLE_GENAI_USE_VERTEXAI": "true",
        "SCOPELOCK_GMAIL_ACCOUNT": "scopelocktest1@gmail.com",
        "SCOPELOCK_GMAIL_PUBSUB_TOPIC": (
            "projects/scopelock-506806/topics/scopelock-gmail"
        ),
        "SCOPELOCK_PUBSUB_AUDIENCE": "https://scopelock-api.example.run.app",
        "SCOPELOCK_PUBSUB_PUSH_SERVICE_ACCOUNT": (
            "scopelock-pubsub-push@scopelock-506806.iam.gserviceaccount.com"
        ),
        "SCOPELOCK_OPERATOR_API_KEY": "o" * 64,
        "SCOPELOCK_GMAIL_TOKEN_JSON": '{"refresh_token":"redacted"}',
    }


def test_cloud_run_settings_validate_non_secret_runtime_contract():
    settings = load_cloud_run_settings(_environment())

    assert settings.port == 8080
    assert settings.project_id == "scopelock-506806"
    assert settings.topic_name.endswith("/topics/scopelock-gmail")
    assert not hasattr(settings, "operator_api_key")
    assert not hasattr(settings, "token_json")


def test_cloud_run_entrypoint_passes_validated_port_to_uvicorn(monkeypatch):
    for name, value in _environment().items():
        monkeypatch.setenv(name, value)
    observed = {}

    def fake_run(application, **options):
        observed.update({"application": application, **options})

    monkeypatch.setattr("scopelock.cloud_run.uvicorn.run", fake_run)

    main()

    assert observed == {
        "application": "scopelock.http_api:app",
        "host": "0.0.0.0",
        "port": 8080,
        "proxy_headers": True,
        "forwarded_allow_ips": "*",
        "access_log": True,
    }


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("PORT", "0", "PORT"),
        ("GOOGLE_GENAI_USE_VERTEXAI", "false", "must be true"),
        (
            "SCOPELOCK_GMAIL_PUBSUB_TOPIC",
            "projects/attacker/topics/scopelock-gmail",
            "valid topic",
        ),
        ("SCOPELOCK_PUBSUB_AUDIENCE", "http://example.test", "HTTPS"),
        (
            "SCOPELOCK_PUBSUB_PUSH_SERVICE_ACCOUNT",
            "person@example.com",
            "must belong",
        ),
        (
            "SCOPELOCK_PUBSUB_PUSH_SERVICE_ACCOUNT",
            "scopelock-push@attacker.iam.gserviceaccount.com",
            "must belong",
        ),
        ("SCOPELOCK_OPERATOR_API_KEY", "short", "at least"),
        ("SCOPELOCK_GMAIL_TOKEN_JSON", "", "required"),
    ],
)
def test_cloud_run_settings_fail_closed(name, value, message):
    environment = _environment()
    environment[name] = value

    with pytest.raises(RuntimeError, match=message):
        load_cloud_run_settings(environment)


def test_container_build_context_excludes_credentials_and_local_state():
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    gcloudignore = (ROOT / ".gcloudignore").read_text(encoding="utf-8")

    for ignored in (
        ".env",
        "secrets/",
        "client_secret*.json",
        "gmail_token*.json",
        "*service-account*.json",
        ".venv313/",
        "artifacts/",
        "**/.adk/**",
        "scopelock/testing/**",
    ):
        assert ignored in dockerignore
        assert ignored in gcloudignore

    assert dockerignore.startswith("**\n")
    assert gcloudignore.startswith("**\n")
    for included in (
        "!Dockerfile",
        "!pyproject.toml",
        "!uv.lock",
        "!app/**",
        "!config/**",
        "!scopelock/**",
    ):
        assert included in dockerignore
        assert included in gcloudignore


def test_dockerfile_is_locked_non_root_and_does_not_copy_the_repository_root():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "python:3.13.15-slim-bookworm" in dockerfile
    assert "ghcr.io/astral-sh/uv:0.11.28" in dockerfile
    assert "uv sync --locked --no-dev --no-install-project" in dockerfile
    assert "USER 10001:10001" in dockerfile
    assert 'CMD ["python", "-m", "scopelock.cloud_run"]' in dockerfile
    assert "COPY . " not in dockerfile

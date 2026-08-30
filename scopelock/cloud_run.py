"""Fail-closed Cloud Run process entry point for the ScopeLock API."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlparse

import uvicorn

from scopelock.observability import configure_structured_logging, emit_structured_event
from scopelock.security import MIN_OPERATOR_KEY_LENGTH, require_email_address


_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_TOPIC_ID = re.compile(r"^[A-Za-z][A-Za-z0-9._~+%-]{2,254}$")
_MAX_HOSTED_TOKEN_BYTES = 64 * 1024


@dataclass(frozen=True)
class CloudRunSettings:
    """Validated, non-secret process settings safe to retain in memory."""

    port: int
    project_id: str
    location: str
    mailbox: str
    topic_name: str
    audience: str
    push_service_account: str


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required for the Cloud Run runtime")
    return value


def _port(environment: Mapping[str, str]) -> int:
    raw = environment.get("PORT", "8080").strip()
    try:
        value = int(raw)
    except ValueError as error:
        raise RuntimeError("PORT must be an integer") from error
    if not 1 <= value <= 65_535:
        raise RuntimeError("PORT must be between 1 and 65535")
    return value


def _audience(environment: Mapping[str, str]) -> str:
    value = _required(environment, "SCOPELOCK_PUBSUB_AUDIENCE")
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise RuntimeError(
            "SCOPELOCK_PUBSUB_AUDIENCE must be one HTTPS service origin"
        )
    return value.rstrip("/")


def load_cloud_run_settings(
    environment: Mapping[str, str] | None = None,
) -> CloudRunSettings:
    """Validate hosted configuration without retaining or logging secret values."""

    env = environment if environment is not None else os.environ
    project_id = _required(env, "GOOGLE_CLOUD_PROJECT")
    if _PROJECT_ID.fullmatch(project_id) is None:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT is malformed")
    if env.get("GOOGLE_GENAI_USE_VERTEXAI", "").strip().casefold() != "true":
        raise RuntimeError("GOOGLE_GENAI_USE_VERTEXAI must be true in Cloud Run")

    mailbox = require_email_address(
        _required(env, "SCOPELOCK_GMAIL_ACCOUNT"), label="Gmail account"
    )
    topic_name = _required(env, "SCOPELOCK_GMAIL_PUBSUB_TOPIC")
    topic_prefix = f"projects/{project_id}/topics/"
    topic_id = topic_name.removeprefix(topic_prefix)
    if not topic_name.startswith(topic_prefix) or _TOPIC_ID.fullmatch(topic_id) is None:
        raise RuntimeError(
            "SCOPELOCK_GMAIL_PUBSUB_TOPIC must be a valid topic in "
            "GOOGLE_CLOUD_PROJECT"
        )

    push_service_account = require_email_address(
        _required(env, "SCOPELOCK_PUBSUB_PUSH_SERVICE_ACCOUNT"),
        label="Pub/Sub push service account",
    )
    if not push_service_account.endswith(
        f"@{project_id}.iam.gserviceaccount.com"
    ):
        raise RuntimeError(
            "SCOPELOCK_PUBSUB_PUSH_SERVICE_ACCOUNT must belong to "
            "GOOGLE_CLOUD_PROJECT"
        )

    operator_key = _required(env, "SCOPELOCK_OPERATOR_API_KEY")
    if len(operator_key) < MIN_OPERATOR_KEY_LENGTH:
        raise RuntimeError(
            f"SCOPELOCK_OPERATOR_API_KEY must be at least "
            f"{MIN_OPERATOR_KEY_LENGTH} characters"
        )
    hosted_token = _required(env, "SCOPELOCK_GMAIL_TOKEN_JSON")
    if len(hosted_token.encode("utf-8")) > _MAX_HOSTED_TOKEN_BYTES:
        raise RuntimeError("SCOPELOCK_GMAIL_TOKEN_JSON exceeds the safe size limit")

    return CloudRunSettings(
        port=_port(env),
        project_id=project_id,
        location=_required(env, "GOOGLE_CLOUD_LOCATION"),
        mailbox=mailbox,
        topic_name=topic_name,
        audience=_audience(env),
        push_service_account=push_service_account,
    )


def main() -> None:
    settings = load_cloud_run_settings()
    configure_structured_logging()
    emit_structured_event("cloud_run.starting", status="STARTING")
    # Cloud Run requires the ingress container to listen on every interface.
    uvicorn.run(
        "scopelock.http_api:app",
        host="0.0.0.0",  # nosec B104
        port=settings.port,
        proxy_headers=True,
        forwarded_allow_ips="*",
        access_log=True,
    )


if __name__ == "__main__":  # pragma: no cover - process entry point
    main()

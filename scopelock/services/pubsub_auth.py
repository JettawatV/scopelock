"""OIDC verification for authenticated Google Pub/Sub push requests."""

from __future__ import annotations

from typing import Any

from scopelock.security import MAX_BEARER_TOKEN_LENGTH, require_email_address
from scopelock.services.execution_boundaries import WorkflowExecutionBoundaries


class PubSubAuthenticationError(PermissionError):
    pass


class PubSubOidcVerifier:
    def __init__(self, *, audience: str, service_account_email: str) -> None:
        if (
            not audience
            or len(audience) > 2_048
            or "\r" in audience
            or "\n" in audience
        ):
            raise ValueError("Pub/Sub audience and push service account are required")
        self._audience = audience
        self._service_account_email = require_email_address(
            service_account_email, label="Pub/Sub push service account"
        )

    def verify(self, authorization: str | None) -> dict[str, Any]:
        if not authorization or not authorization.startswith("Bearer "):
            raise PubSubAuthenticationError("Missing Pub/Sub bearer token")
        token = authorization.removeprefix("Bearer ").strip()
        if (
            not token
            or len(token) > MAX_BEARER_TOKEN_LENGTH
            or any(character.isspace() for character in token)
        ):
            raise PubSubAuthenticationError("Malformed Pub/Sub bearer token")
        try:
            from google.auth.transport.requests import Request
            from google.oauth2 import id_token
        except ImportError as error:  # pragma: no cover - dependency guard
            raise RuntimeError("Install google-auth to verify Pub/Sub OIDC") from error
        claims = WorkflowExecutionBoundaries.external_read(
            lambda: id_token.verify_oauth2_token(
                token, Request(), audience=self._audience
            )
        )
        email = str(claims.get("email") or "").casefold()
        if email != self._service_account_email or claims.get("email_verified") is not True:
            raise PubSubAuthenticationError(
                "Pub/Sub token service account is not authorized"
            )
        return dict(claims)

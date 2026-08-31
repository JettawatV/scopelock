"""Firebase email-link authentication for the public judging surface.

The reviewer surface is intentionally separate from the operator API key. A
Firebase email-link sign-in gives a judge a short-lived ID token that is
verified on every request. The token identifies the judge's email so the
reviewer projection can be restricted to messages that they sent to the
dedicated demo mailbox.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from fastapi import Header, HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from scopelock.security import MAX_BEARER_TOKEN_LENGTH, require_email_address


@dataclass(frozen=True)
class ReviewerIdentity:
    """Verified Firebase identity used by reviewer-only endpoints."""

    uid: str
    email: str


def firebase_project_id() -> str:
    value = (
        os.getenv("SCOPELOCK_FIREBASE_PROJECT_ID", "").strip()
        or os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
    )
    if not value:
        raise RuntimeError("SCOPELOCK_FIREBASE_PROJECT_ID is required for reviewer access")
    return value


def firebase_web_config() -> dict[str, str]:
    """Return only public Firebase web configuration for the sign-in client."""

    project = firebase_project_id()
    api_key = os.getenv("SCOPELOCK_FIREBASE_API_KEY", "").strip()
    auth_domain = (
        os.getenv("SCOPELOCK_FIREBASE_AUTH_DOMAIN", "").strip()
        or f"{project}.firebaseapp.com"
    )
    if not api_key:
        raise RuntimeError("SCOPELOCK_FIREBASE_API_KEY is required for reviewer access")
    return {
        "apiKey": api_key,
        "authDomain": auth_domain,
        "projectId": project,
    }


def verify_reviewer_token(
    authorization: str | None,
    *,
    verifier: Any = id_token.verify_firebase_token,
) -> ReviewerIdentity:
    """Verify a Firebase ID token and return its verified email identity."""

    prefix = "Bearer "
    if not authorization or not authorization.startswith(prefix):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Reviewer sign-in required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization[len(prefix) :].strip()
    if (
        not token
        or len(token) > MAX_BEARER_TOKEN_LENGTH
        or any(char.isspace() for char in token)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid reviewer session",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = verifier(
            token,
            google_requests.Request(),
            audience=firebase_project_id(),
        )
    except Exception as error:  # Google auth errors intentionally stay redacted.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired reviewer session",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    uid = claims.get("sub")
    email = claims.get("email")
    if (
        not isinstance(uid, str)
        or not uid
        or not isinstance(email, str)
        or not claims.get("email_verified")
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A verified reviewer email is required",
        )
    try:
        normalized_email = require_email_address(email, label="reviewer email")
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A verified reviewer email is required",
        ) from error
    return ReviewerIdentity(uid=uid, email=normalized_email)


def reviewer_identity(
    authorization: str | None = Header(default=None),
    reviewer_token: str | None = Header(
        default=None, alias="X-ScopeLock-Reviewer-Token"
    ),
) -> ReviewerIdentity:
    # The public gateway must use the Cloud Run IAM Authorization header for
    # service-to-service invocation. It forwards the Firebase token separately
    # so the private API can verify the reviewer identity without confusing the
    # two authentication layers.
    return verify_reviewer_token(reviewer_token or authorization)

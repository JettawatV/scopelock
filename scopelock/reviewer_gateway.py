"""Public reviewer gateway for the private ScopeLock Cloud Run service.

The gateway is the only public Cloud Run service. It serves the reviewer SPA
and forwards only ``/api/reviewer/*`` to the private core service with a
Cloud Run identity token. The judge's Firebase ID token is carried in a
separate header so the private service can verify both IAM and reviewer
identity independently.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request as UrlRequest
from urllib.request import urlopen
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from scopelock.security import MAX_API_REQUEST_BYTES
from scopelock.settings import PROJECT_ROOT


def _frontend_root() -> Path:
    configured = os.getenv("SCOPELOCK_FRONTEND_ROOT", "").strip()
    if not configured:
        return PROJECT_ROOT / "frontend" / "dist"
    path = Path(configured)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _private_api_origin() -> str:
    value = os.getenv("SCOPELOCK_PRIVATE_API_URL", "").strip().rstrip("/")
    parsed = urlparse(value)
    if (
        parsed.scheme not in {"https", "http"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError("SCOPELOCK_PRIVATE_API_URL must be one service origin")
    return value


class ReviewerStaticFiles(StaticFiles):
    """Serve the reviewer SPA while keeping operator routes off the gateway."""

    async def get_response(self, path: str, scope: dict[str, Any]):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as error:
            if error.status_code == status.HTTP_404_NOT_FOUND and path.strip("/") in {
                "review",
                "review/",
            }:
                return await super().get_response("index.html", scope)
            raise


app = FastAPI(
    title="ScopeLock reviewer gateway",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


def _allowed_reviewer_path(path: str, method: str) -> bool:
    """Keep the public gateway's forwarding surface explicit and bounded."""

    if path in {"config", "session", "dashboard"}:
        return method == "GET"
    if path.startswith("messages/"):
        return method == "GET"
    if path.startswith("artifacts/"):
        parts = path.split("/")
        if len(parts) != 3 or not parts[1] or not parts[2]:
            return False
        return (method == "GET" and parts[2] == "proposal.pdf") or (
            method == "POST"
            and parts[2]
            in {"approve", "reject", "revise", "draft", "send", "accept"}
        )
    if path.startswith("buffers/"):
        parts = path.split("/")
        return (
            method == "POST"
            and len(parts) == 3
            and parts[2] == "finalize"
            and bool(parts[1])
        )
    return False


@app.middleware("http")
async def gateway_security(request: Request, call_next):
    request_id = uuid4().hex
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) < 0 or int(content_length) > MAX_API_REQUEST_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Request body exceeds the safe size limit"},
                )
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Malformed Content-Length"})
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; base-uri 'self'; connect-src 'self' "
        "https://identitytoolkit.googleapis.com https://securetoken.googleapis.com; "
        "font-src 'self'; frame-ancestors 'none'; frame-src 'self' blob:; "
        "img-src 'self' data:; object-src 'none'; script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'"
    )
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-ScopeLock-Request-ID"] = request_id
    return response


def _service_identity_token(audience: str) -> str:
    return id_token.fetch_id_token(google_requests.Request(), audience)


def _forward_sync(
    *,
    target_url: str,
    method: str,
    body: bytes,
    reviewer_authorization: str | None,
) -> tuple[int, bytes, str]:
    headers = {
        "Accept": "application/json, application/pdf",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {_service_identity_token(target_url.split('/api/', 1)[0])}",
    }
    if reviewer_authorization:
        headers["X-ScopeLock-Reviewer-Token"] = reviewer_authorization
    request = UrlRequest(target_url, data=body or None, headers=headers, method=method)
    try:
        with urlopen(  # nosec B310 - target is validated env
            request, timeout=35
        ) as response:
            return (
                response.status,
                response.read(MAX_API_REQUEST_BYTES + 1),
                response.headers.get_content_type(),
            )
    except HTTPError as error:
        return (
            error.code,
            error.read(MAX_API_REQUEST_BYTES + 1),
            error.headers.get_content_type(),
        )
    except URLError as error:
        raise RuntimeError("Private reviewer service is unavailable") from error


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse("/review/", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@app.api_route("/api/reviewer/{path:path}", methods=["GET", "POST"])
async def reviewer_proxy(path: str, request: Request) -> Response:
    if not _allowed_reviewer_path(path, request.method):
        return JSONResponse(status_code=404, content={"detail": "Reviewer route not found"})
    try:
        origin = _private_api_origin()
    except RuntimeError as error:
        return JSONResponse(status_code=503, content={"detail": str(error)})
    target_url = f"{origin}/api/reviewer/{path}"
    body = await request.body()
    if len(body) > MAX_API_REQUEST_BYTES:
        return JSONResponse(
            status_code=413,
            content={"detail": "Request body exceeds the safe size limit"},
        )
    try:
        status_code, response_body, content_type = await asyncio.to_thread(
            _forward_sync,
            target_url=target_url,
            method=request.method,
            body=body,
            reviewer_authorization=request.headers.get("authorization"),
        )
    except RuntimeError as error:
        return JSONResponse(status_code=503, content={"detail": str(error)})
    return Response(
        content=response_body,
        status_code=status_code,
        media_type=content_type,
    )


frontend_root = _frontend_root()
if frontend_root.is_dir():
    app.mount(
        "/",
        ReviewerStaticFiles(directory=frontend_root, html=True),
        name="reviewer-frontend",
    )

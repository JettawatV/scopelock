"""FastAPI command/event surface for Days 11-13."""

from __future__ import annotations

import hmac
import hashlib
import json
import os
from time import perf_counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from threading import Lock
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from scopelock.domain.enums import ApprovalStatus, BufferFinalizationReason
from scopelock.domain.models import CommercialArtifact
from scopelock.observability import emit_structured_event
from scopelock.repositories.firestore import FirestoreApplicationRepository
from scopelock.services.approval_policy import ApprovalPolicyViolation
from scopelock.services.gmail_commercial_service import GmailCommercialService
from scopelock.security import (
    MAX_API_REQUEST_BYTES,
    MIN_OPERATOR_KEY_LENGTH,
    redacted_error,
    require_email_address,
)
from scopelock.services.gmail_event_service import (
    GmailEventInProgress,
    GmailEventService,
    PubSubEnvelopeError,
)
from scopelock.services.gmail_gateway import GoogleGmailGateway
from scopelock.services.gmail_oauth import GmailCredentialProvider
from scopelock.services.gmail_watch_service import GmailWatchService
from scopelock.services.dashboard_query_service import DashboardQueryService
from scopelock.services.inbound_processing_workflow import InboundProcessingWorkflow
from scopelock.services.pubsub_auth import (
    PubSubAuthenticationError,
    PubSubOidcVerifier,
)
from scopelock.services.scope_revision_workflow import ScopeRevisionWorkflow
from scopelock.services.sop_service import load_sop
from scopelock.settings import PROJECT_ROOT, project_id


class HttpOnlyStaticFiles(StaticFiles):
    """Serve the SPA without turning the catch-all mount into a WS app."""

    _SPA_ROUTES = {"projects", "evals"}

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1000})
            return
        await super().__call__(scope, receive, send)

    async def get_response(self, path: str, scope: dict[str, Any]):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as error:
            if (
                error.status_code == status.HTTP_404_NOT_FOUND
                and path.strip("/") in self._SPA_ROUTES
            ):
                return await super().get_response("index.html", scope)
            raise


class CommandModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DecisionCommand(CommandModel):
    approver_id: str = Field(min_length=1, max_length=320)
    correlation_id: str = Field(min_length=1, max_length=128)


class RevisionCommand(CommandModel):
    operator_id: str = Field(min_length=1, max_length=320)
    correlation_id: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=1, max_length=2_000)


class ActionCommand(CommandModel):
    correlation_id: str = Field(min_length=1, max_length=128)


class AcceptanceCommand(CommandModel):
    source_inbound_message_id: str = Field(min_length=1, max_length=256)
    correlation_id: str = Field(min_length=1, max_length=128)


class FinalizeCommand(CommandModel):
    correlation_id: str = Field(min_length=1, max_length=128)


@dataclass(frozen=True)
class GmailApiRuntime:
    event_service: GmailEventService
    watch_service: GmailWatchService
    commercial_service: GmailCommercialService
    revision_workflow: ScopeRevisionWorkflow
    mailbox: str
    topic_name: str
    operator_api_key: str = field(repr=False)
    pubsub_verifier: PubSubOidcVerifier | None
    dashboard_service: DashboardQueryService | None = None


class RuntimeProvider:
    def __init__(self, factory: Callable[[], GmailApiRuntime]) -> None:
        self._factory = factory
        self._runtime: GmailApiRuntime | None = None
        self._lock = Lock()

    def __call__(self) -> GmailApiRuntime:
        if self._runtime is None:
            with self._lock:
                if self._runtime is None:
                    self._runtime = self._factory()
        return self._runtime


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required for the Gmail HTTP runtime")
    return value


def _operator_secret() -> str:
    value = _required_env("SCOPELOCK_OPERATOR_API_KEY")
    if len(value) < MIN_OPERATOR_KEY_LENGTH:
        raise RuntimeError(
            f"SCOPELOCK_OPERATOR_API_KEY must be at least {MIN_OPERATOR_KEY_LENGTH} characters"
        )
    return value


def _secret_matches(candidate: str, expected: str) -> bool:
    candidate_digest = hashlib.sha256(candidate.encode("utf-8")).digest()
    expected_digest = hashlib.sha256(expected.encode("utf-8")).digest()
    return hmac.compare_digest(candidate_digest, expected_digest)


def _pubsub_verifier() -> PubSubOidcVerifier:
    return PubSubOidcVerifier(
        audience=_required_env("SCOPELOCK_PUBSUB_AUDIENCE"),
        service_account_email=_required_env(
            "SCOPELOCK_PUBSUB_PUSH_SERVICE_ACCOUNT"
        ),
    )


def _artifact_root() -> Path:
    configured = os.getenv("SCOPELOCK_ARTIFACT_ROOT", "").strip()
    if not configured:
        return PROJECT_ROOT / "artifacts"
    path = Path(configured)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _frontend_root() -> Path:
    configured = os.getenv("SCOPELOCK_FRONTEND_ROOT", "").strip()
    if not configured:
        return PROJECT_ROOT / "frontend" / "dist"
    path = Path(configured)
    return path if path.is_absolute() else PROJECT_ROOT / path


def build_default_runtime() -> GmailApiRuntime:
    from google.cloud import firestore

    cloud_project = project_id()
    mailbox = require_email_address(
        _required_env("SCOPELOCK_GMAIL_ACCOUNT"), label="Gmail account"
    )
    topic_name = _required_env("SCOPELOCK_GMAIL_PUBSUB_TOPIC")
    firestore_database = (
        os.getenv("SCOPELOCK_FIRESTORE_DATABASE", "default").strip() or "default"
    )
    repository = FirestoreApplicationRepository(
        firestore.Client(project=cloud_project, database=firestore_database)
    )
    catalog_path = Path(
        os.getenv("SCOPELOCK_SOP_PATH", "config/jvl_sop.example.yaml")
    )
    if not catalog_path.is_absolute():
        catalog_path = PROJECT_ROOT / catalog_path
    catalog = load_sop(catalog_path)
    gateway = GoogleGmailGateway(GmailCredentialProvider().load())
    revisions = ScopeRevisionWorkflow(catalog=catalog, repository=repository)
    inbound = InboundProcessingWorkflow(
        catalog=catalog,
        repository=repository,
        artifact_root=_artifact_root(),
    )
    verifier = _pubsub_verifier()
    return GmailApiRuntime(
        event_service=GmailEventService(
            gateway=gateway,
            workflow=inbound,
            repository=repository,
            mailbox=mailbox,
            ready_buffer_finalizer=revisions,
        ),
        watch_service=GmailWatchService(
            gateway=gateway,
            repository=repository,
            google_cloud_project=cloud_project,
        ),
        commercial_service=GmailCommercialService(
            gateway=gateway, repository=repository, mailbox=mailbox
        ),
        revision_workflow=revisions,
        mailbox=mailbox,
        topic_name=topic_name,
        operator_api_key=_operator_secret(),
        pubsub_verifier=verifier,
        dashboard_service=DashboardQueryService(
            repository,
            readiness_path=PROJECT_ROOT / "config" / "agent_readiness.json",
        ),
    )


def create_app(
    runtime_provider: Callable[[], GmailApiRuntime] | None = None,
) -> FastAPI:
    provider = runtime_provider or RuntimeProvider(build_default_runtime)
    app = FastAPI(
        title="ScopeLock Gmail Runtime",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    def secure_response(response, *, request_id: str, request_path: str):
        is_ui = request_path == "/" or request_path.startswith(
            ("/projects", "/evals", "/assets/", "/icon.svg")
        )
        response.headers["Cache-Control"] = (
            "public, max-age=31536000, immutable"
            if request_path.startswith("/assets/")
            else "no-store"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; base-uri 'self'; connect-src 'self'; "
            "font-src 'self'; frame-ancestors 'none'; img-src 'self' data:; "
            "object-src 'none'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'"
            if is_ui
            else "default-src 'none'; frame-ancestors 'none'"
        )
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-ScopeLock-Request-ID"] = request_id
        return response

    @app.middleware("http")
    async def security_boundary(request: Request, call_next):
        request_id = uuid4().hex
        started_at = perf_counter()

        def complete(response):
            secured = secure_response(
                response, request_id=request_id, request_path=request.url.path
            )
            emit_structured_event(
                "http.request.completed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=secured.status_code,
                duration_ms=int((perf_counter() - started_at) * 1_000),
            )
            return secured

        content_length = request.headers.get("content-length")
        if content_length:
            try:
                declared_length = int(content_length)
            except ValueError:
                return complete(
                    JSONResponse(
                        status_code=400,
                        content={"detail": "Malformed Content-Length"},
                    )
                )
            if declared_length < 0 or declared_length > MAX_API_REQUEST_BYTES:
                return complete(
                    JSONResponse(
                        status_code=413,
                        content={
                            "detail": "Request body exceeds the safe size limit"
                        },
                    )
                )
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > MAX_API_REQUEST_BYTES:
                return complete(
                    JSONResponse(
                        status_code=413,
                        content={
                            "detail": "Request body exceeds the safe size limit"
                        },
                    )
                )
        request._body = bytes(body)
        response = await call_next(request)
        return complete(response)

    def runtime() -> GmailApiRuntime:
        try:
            return provider()
        except Exception as error:
            safe_error = redacted_error(error, operation="runtime initialization")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=safe_error,
            ) from error

    def require_operator_key(
        operator_key: str | None = Header(
            default=None, alias="X-ScopeLock-Operator-Key"
        ),
    ) -> None:
        """Verify the operator secret without initializing Gmail or Firestore.

        The small session endpoint below uses this dependency so an operator can
        distinguish an incorrect key from a separately unavailable runtime.
        """
        if runtime_provider is None:
            try:
                expected_key = _operator_secret()
            except Exception as error:
                safe_error = redacted_error(
                    error, operation="operator authentication configuration"
                )
                raise HTTPException(status_code=503, detail=safe_error) from error
            if (
                not operator_key
                or len(operator_key) > 512
                or not _secret_matches(operator_key, expected_key)
            ):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid operator API key",
                    headers={"WWW-Authenticate": "ScopeLockOperatorKey"},
                )
            return

        configured = runtime()
        if not operator_key or len(operator_key) > 512 or not _secret_matches(
            operator_key, configured.operator_api_key
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid operator API key",
                headers={"WWW-Authenticate": "ScopeLockOperatorKey"},
            )

    def operator_runtime(
        operator_key: str | None = Header(
            default=None, alias="X-ScopeLock-Operator-Key"
        ),
    ) -> GmailApiRuntime:
        require_operator_key(operator_key)
        configured = runtime()
        return configured

    # Cloud Run reserves some paths ending in "z", so keep this endpoint
    # intentionally named /health rather than the common /healthz.
    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/session")
    def operator_session(_: None = Depends(require_operator_key)) -> dict[str, str]:
        """Authenticate an operator key without opening cloud dependencies."""

        return {"status": "accepted"}

    @app.get("/api/dashboard")
    def dashboard(
        configured: GmailApiRuntime = Depends(operator_runtime),
    ) -> dict[str, Any]:
        if configured.dashboard_service is None:
            raise HTTPException(
                status_code=503, detail="Dashboard read service is unavailable"
            )
        return configured.dashboard_service.overview().model_dump(mode="json")

    @app.get("/api/projects/{project_id}")
    def project_detail(
        project_id: str,
        configured: GmailApiRuntime = Depends(operator_runtime),
    ) -> dict[str, Any]:
        if len(project_id) > 256:
            raise HTTPException(status_code=404, detail="Project not found")
        if configured.dashboard_service is None:
            raise HTTPException(
                status_code=503, detail="Dashboard read service is unavailable"
            )
        try:
            result = configured.dashboard_service.project_detail(project_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Project not found") from error
        return result.model_dump(mode="json")

    @app.post("/webhooks/gmail")
    async def gmail_webhook(
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        try:
            if runtime_provider is None:
                _pubsub_verifier().verify(authorization)
                configured = runtime()
            else:
                configured = runtime()
                if configured.pubsub_verifier is not None:
                    configured.pubsub_verifier.verify(authorization)
            raw_body = await request.body()
            try:
                envelope = json.loads(raw_body)
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise PubSubEnvelopeError(
                    "Webhook body is not a valid JSON object"
                ) from error
            if not isinstance(envelope, dict):
                raise PubSubEnvelopeError("Webhook body must be a JSON object")
            result = await configured.event_service.process_pubsub(envelope)
            if result.status == "FAILED":
                raise HTTPException(
                    status_code=503,
                    detail={"status": result.status, "event_id": result.id},
                )
            return result.model_dump(mode="json")
        except PubSubAuthenticationError as error:
            raise HTTPException(
                status_code=401,
                detail="Pub/Sub authentication failed",
            ) from error
        except PubSubEnvelopeError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except GmailEventInProgress as error:
            raise HTTPException(
                status_code=503,
                detail="Pub/Sub event is already processing",
            ) from error
        except HTTPException:
            raise
        except Exception as error:
            safe_error = redacted_error(error, operation="gmail webhook")
            raise HTTPException(status_code=503, detail=safe_error) from error

    @app.post("/gmail/watch")
    def register_watch(
        configured: GmailApiRuntime = Depends(operator_runtime),
    ) -> dict[str, Any]:
        record = configured.watch_service.register(
            mailbox=configured.mailbox,
            topic_name=configured.topic_name,
        )
        return record.model_dump(mode="json")

    @app.get("/artifacts/{artifact_id}")
    def get_artifact(
        artifact_id: str,
        configured: GmailApiRuntime = Depends(operator_runtime),
    ) -> dict[str, Any]:
        try:
            artifact = configured.commercial_service.get_artifact(artifact_id)
            return artifact.model_dump(mode="json")
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    def _decision(
        artifact_id: str,
        command: DecisionCommand,
        configured: GmailApiRuntime,
        decision: ApprovalStatus,
    ) -> dict[str, Any]:
        try:
            artifact, approval = configured.commercial_service.decide(
                artifact_id,
                decision=decision,
                approver_id=command.approver_id,
                correlation_id=command.correlation_id,
            )
            return {
                "artifact": artifact.model_dump(mode="json"),
                "approval": approval.model_dump(mode="json"),
            }
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ApprovalPolicyViolation as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/artifacts/{artifact_id}/approve")
    def approve_artifact(
        artifact_id: str,
        command: DecisionCommand,
        configured: GmailApiRuntime = Depends(operator_runtime),
    ) -> dict[str, Any]:
        return _decision(artifact_id, command, configured, ApprovalStatus.APPROVED)

    @app.post("/artifacts/{artifact_id}/reject")
    def reject_artifact(
        artifact_id: str,
        command: DecisionCommand,
        configured: GmailApiRuntime = Depends(operator_runtime),
    ) -> dict[str, Any]:
        return _decision(artifact_id, command, configured, ApprovalStatus.REJECTED)

    @app.post("/artifacts/{artifact_id}/revise")
    def revise_artifact(
        artifact_id: str,
        command: RevisionCommand,
        configured: GmailApiRuntime = Depends(operator_runtime),
    ) -> dict[str, Any]:
        try:
            artifact = configured.commercial_service.mark_for_revision(
                artifact_id,
                operator_id=command.operator_id,
                correlation_id=command.correlation_id,
                reason=command.reason,
            )
            return artifact.model_dump(mode="json")
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Artifact not found") from error
        except ApprovalPolicyViolation as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/artifacts/{artifact_id}/draft")
    def create_draft(
        artifact_id: str,
        command: ActionCommand,
        configured: GmailApiRuntime = Depends(operator_runtime),
    ) -> dict[str, Any]:
        try:
            draft = configured.commercial_service.create_draft(
                artifact_id, correlation_id=command.correlation_id
            )
            return draft.model_dump(mode="json")
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Artifact not found") from error
        except ApprovalPolicyViolation as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/artifacts/{artifact_id}/send")
    def send_artifact(
        artifact_id: str,
        command: ActionCommand,
        configured: GmailApiRuntime = Depends(operator_runtime),
    ) -> dict[str, Any]:
        try:
            result = configured.commercial_service.send(
                artifact_id, correlation_id=command.correlation_id
            )
            code = 200 if result.status == "SENT" else 503
            if code != 200:
                raise HTTPException(code, detail=result.model_dump(mode="json"))
            return result.model_dump(mode="json")
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Artifact not found") from error
        except ApprovalPolicyViolation as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/buffers/{buffer_id}/finalize")
    def finalize_buffer(
        buffer_id: str,
        command: FinalizeCommand,
        configured: GmailApiRuntime = Depends(operator_runtime),
    ) -> dict[str, Any]:
        try:
            result = configured.revision_workflow.finalize_buffer(
                buffer_id,
                reason=BufferFinalizationReason.MANUAL,
                finalized_at=datetime.now(timezone.utc),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Scope buffer not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "buffer": result.buffer.model_dump(mode="json"),
            "scope": result.proposed_scope.model_dump(mode="json"),
            "artifact": result.artifact.model_dump(mode="json"),
            "correlation_id": command.correlation_id,
        }

    @app.post("/buffers/finalize-due")
    def finalize_due(
        command: FinalizeCommand,
        configured: GmailApiRuntime = Depends(operator_runtime),
    ) -> dict[str, Any]:
        results = configured.revision_workflow.finalize_due(
            now=datetime.now(timezone.utc)
        )
        return {
            "artifact_ids": [item.artifact.id for item in results],
            "correlation_id": command.correlation_id,
        }

    @app.post("/artifacts/{artifact_id}/accept")
    def accept_artifact(
        artifact_id: str,
        command: AcceptanceCommand,
        configured: GmailApiRuntime = Depends(operator_runtime),
    ) -> dict[str, Any]:
        try:
            artifact, scope, project = (
                configured.revision_workflow.accept_sent_artifact_from_record(
                    artifact_id,
                    inbound_message_record_id=command.source_inbound_message_id,
                    correlation_id=command.correlation_id,
                )
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Artifact not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "artifact": artifact.model_dump(mode="json"),
            "scope": scope.model_dump(mode="json"),
            "project": project.model_dump(mode="json"),
        }

    frontend_root = _frontend_root()
    if frontend_root.is_dir():
        app.mount(
            "/",
            HttpOnlyStaticFiles(directory=frontend_root, html=True),
            name="frontend",
        )

    return app


app = create_app()

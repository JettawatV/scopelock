"""Redacted, read-only projections for the operator dashboard."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import Field

from scopelock.domain.models import (
    AgentRun,
    CommercialArtifact,
    ScopeVersion,
    StrictFrozenContractModel,
)
from scopelock.domain.workflow_models import (
    GmailWatchRecord,
    InboundMessageRecord,
    ProjectRecord,
    ScopeBufferRecord,
    ScopeEventRecord,
)
from scopelock.repositories.contracts import ApplicationRepository
from scopelock.repositories.model_store import CollectionName


MAX_DASHBOARD_RECORDS = 50
MAX_READINESS_FILE_BYTES = 32 * 1024


class ReadinessCheck(StrictFrozenContractModel):
    key: str
    label: str
    passed: int = Field(ge=0, strict=True)
    expected: int = Field(ge=0, strict=True)


class AgentReadinessSnapshot(StrictFrozenContractModel):
    status: str
    verified_at: datetime | None = None
    model: str | None = None
    prompt_versions: tuple[str, ...] = ()
    checks: tuple[ReadinessCheck, ...] = ()
    note: str


class DashboardAgentRun(StrictFrozenContractModel):
    id: str
    correlation_id: str
    project_id: str | None = None
    agent_name: str
    model: str
    prompt_version: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    tool_count: int = Field(ge=0, strict=True)
    error_category: str | None = None
    retryable: bool = False


class DashboardInboxMessage(StrictFrozenContractModel):
    """Safe metadata for a message that belongs to an existing project.

    The dashboard must never be a second mailbox client.  In particular, this
    projection intentionally excludes the message body, recipients, Gmail
    history ID, raw-content hash, and attachment identifiers.
    """

    id: str
    project_id: str
    sender_name: str
    sender_email: str
    subject: str
    received_at: datetime
    direction: str
    attachment_count: int = Field(ge=0, strict=True)


class DashboardMessageAttachment(StrictFrozenContractModel):
    """Safe attachment metadata without Gmail attachment identifiers."""

    filename: str
    mime_type: str
    size: int = Field(ge=0, strict=True)


class DashboardMessageDetail(DashboardInboxMessage):
    """One explicitly selected, project-linked message for operator review.

    Message bodies stay out of the overview projection and are returned only
    through the authenticated single-message endpoint. Raw hashes, recipients,
    history IDs, and attachment IDs remain excluded.
    """

    body: str
    body_format: str
    attachments: tuple[DashboardMessageAttachment, ...] = ()


class GmailWatchSnapshot(StrictFrozenContractModel):
    """Safe watch status for the operator; topic and history stay private."""

    mailbox: str
    expiration: datetime
    created_at: datetime


class DashboardSnapshot(StrictFrozenContractModel):
    generated_at: datetime
    projects: tuple[ProjectRecord, ...]
    artifacts: tuple[CommercialArtifact, ...]
    scope_events: tuple[ScopeEventRecord, ...]
    scope_buffers: tuple[ScopeBufferRecord, ...]
    agent_runs: tuple[DashboardAgentRun, ...]
    readiness: AgentReadinessSnapshot
    inbox_messages: tuple[DashboardInboxMessage, ...] = ()
    gmail_watch: GmailWatchSnapshot | None = None
    warnings: tuple[str, ...] = ()


class ProjectDetailSnapshot(StrictFrozenContractModel):
    generated_at: datetime
    project: ProjectRecord
    scope_versions: tuple[ScopeVersion, ...]
    artifacts: tuple[CommercialArtifact, ...]
    scope_events: tuple[ScopeEventRecord, ...]
    scope_buffers: tuple[ScopeBufferRecord, ...]
    agent_runs: tuple[DashboardAgentRun, ...]
    warnings: tuple[str, ...] = ()


class DashboardQueryService:
    """Build bounded projections without exposing raw email or agent payloads."""

    def __init__(
        self,
        repository: ApplicationRepository,
        *,
        readiness_path: Path | None = None,
        clock=lambda: datetime.now(timezone.utc),
    ) -> None:
        self._repository = repository
        self._readiness_path = readiness_path
        self._clock = clock

    def overview(self) -> DashboardSnapshot:
        warnings: list[str] = []
        projects = self._load(CollectionName.PROJECTS, ProjectRecord, warnings)
        artifacts = self._load(CollectionName.ARTIFACTS, CommercialArtifact, warnings)
        events = self._load(CollectionName.SCOPE_EVENTS, ScopeEventRecord, warnings)
        buffers = self._load(CollectionName.BUFFERS, ScopeBufferRecord, warnings)
        agent_runs = self._agent_runs(warnings)
        inbox_messages = self._inbox_messages(projects, warnings)
        gmail_watch = self._gmail_watch(warnings)
        return DashboardSnapshot(
            generated_at=self._clock(),
            projects=self._recent(projects, "updated_at"),
            artifacts=self._recent(artifacts, "created_at"),
            scope_events=self._recent(events, "created_at"),
            scope_buffers=self._recent(buffers, "updated_at"),
            agent_runs=self._recent(agent_runs, "started_at"),
            readiness=self._readiness(),
            inbox_messages=self._recent(inbox_messages, "received_at"),
            gmail_watch=gmail_watch,
            warnings=tuple(warnings),
        )

    def project_detail(self, project_id: str) -> ProjectDetailSnapshot:
        warnings: list[str] = []
        project = next(
            (
                item
                for item in self._load(
                    CollectionName.PROJECTS, ProjectRecord, warnings
                )
                if item.id == project_id
            ),
            None,
        )
        if project is None:
            raise KeyError(project_id)

        scopes = self._for_project(
            self._load(CollectionName.SCOPE_VERSIONS, ScopeVersion, warnings),
            project_id,
        )
        artifacts = self._for_project(
            self._load(CollectionName.ARTIFACTS, CommercialArtifact, warnings),
            project_id,
        )
        events = self._for_project(
            self._load(CollectionName.SCOPE_EVENTS, ScopeEventRecord, warnings),
            project_id,
        )
        buffers = self._for_project(
            self._load(CollectionName.BUFFERS, ScopeBufferRecord, warnings),
            project_id,
        )
        agent_runs = tuple(
            run for run in self._agent_runs(warnings) if run.project_id == project_id
        )
        return ProjectDetailSnapshot(
            generated_at=self._clock(),
            project=project,
            scope_versions=tuple(
                sorted(scopes, key=lambda item: item.version_number, reverse=True)
            )[:MAX_DASHBOARD_RECORDS],
            artifacts=self._recent(artifacts, "created_at"),
            scope_events=self._recent(events, "created_at"),
            scope_buffers=self._recent(buffers, "updated_at"),
            agent_runs=self._recent(agent_runs, "started_at"),
            warnings=tuple(warnings),
        )

    def message_detail(self, message_id: str) -> DashboardMessageDetail:
        """Return one bounded message only when it belongs to a known project."""

        warnings: list[str] = []
        projects = self._load(CollectionName.PROJECTS, ProjectRecord, warnings)
        record = next(
            (
                item
                for item in self._load(
                    CollectionName.INBOUND_MESSAGES,
                    InboundMessageRecord,
                    warnings,
                )
                if item.id == message_id
            ),
            None,
        )
        if record is None:
            raise KeyError(message_id)
        project = next(
            (
                item
                for item in projects
                if item.gmail_thread_id == record.email.thread_id
            ),
            None,
        )
        if project is None:
            raise KeyError(message_id)
        return DashboardMessageDetail(
            id=record.id,
            project_id=project.id,
            sender_name=record.email.sender_name,
            sender_email=record.email.sender_email,
            subject=record.email.subject,
            received_at=record.email.received_at,
            direction=record.email.direction.value,
            attachment_count=len(record.email.attachments),
            body=record.email.body,
            body_format=record.email.body_format.value,
            attachments=tuple(
                DashboardMessageAttachment(
                    filename=item.filename,
                    mime_type=item.mime_type,
                    size=item.size,
                )
                for item in record.email.attachments
            ),
        )

    def _agent_runs(self, warnings: list[str]) -> tuple[DashboardAgentRun, ...]:
        records = self._load(CollectionName.AGENT_RUNS, AgentRun, warnings)
        return tuple(
            DashboardAgentRun(
                id=record.id,
                correlation_id=record.correlation_id,
                project_id=record.project_id,
                agent_name=record.agent_name,
                model=record.model,
                prompt_version=record.prompt_version,
                status=record.status.value,
                started_at=record.started_at,
                completed_at=record.completed_at,
                tool_count=len(record.tool_trajectory),
                error_category=record.error.category if record.error else None,
                retryable=record.error.retryable if record.error else False,
            )
            for record in records
        )

    def _inbox_messages(
        self,
        projects: tuple[ProjectRecord, ...],
        warnings: list[str],
    ) -> tuple[DashboardInboxMessage, ...]:
        """Return only safe metadata for messages tied to known project threads."""

        project_ids_by_thread = {
            project.gmail_thread_id: project.id
            for project in projects
            if project.gmail_thread_id
        }
        records = self._load(
            CollectionName.INBOUND_MESSAGES,
            InboundMessageRecord,
            warnings,
        )
        messages: list[DashboardInboxMessage] = []
        for record in records:
            project_id = project_ids_by_thread.get(record.email.thread_id)
            if project_id is None:
                continue
            messages.append(
                DashboardInboxMessage(
                    id=record.id,
                    project_id=project_id,
                    sender_name=record.email.sender_name,
                    sender_email=record.email.sender_email,
                    subject=record.email.subject,
                    received_at=record.email.received_at,
                    direction=record.email.direction.value,
                    attachment_count=len(record.email.attachments),
                )
            )
        return tuple(messages)

    def _gmail_watch(self, warnings: list[str]) -> GmailWatchSnapshot | None:
        records = self._load(
            CollectionName.GMAIL_WATCHES,
            GmailWatchRecord,
            warnings,
        )
        if not records:
            return None
        latest = max(records, key=lambda record: (record.expiration, record.created_at))
        return GmailWatchSnapshot(
            mailbox=latest.mailbox,
            expiration=latest.expiration,
            created_at=latest.created_at,
        )

    def _readiness(self) -> AgentReadinessSnapshot:
        path = self._readiness_path
        if path is None or not path.is_file():
            return AgentReadinessSnapshot(
                status="NOT_RECORDED",
                note="No packaged agent-readiness record is available.",
            )
        if path.stat().st_size > MAX_READINESS_FILE_BYTES:
            return AgentReadinessSnapshot(
                status="INVALID",
                note="The packaged readiness record exceeds the safe size limit.",
            )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return AgentReadinessSnapshot.model_validate(payload)
        except (OSError, ValueError, TypeError):
            return AgentReadinessSnapshot(
                status="INVALID",
                note="The packaged readiness record could not be validated.",
            )

    def _load(self, collection, model_type, warnings: list[str]):
        valid = []
        for document in self._repository.list(collection=collection.value):
            try:
                valid.append(model_type.model_validate(document.payload))
            except ValueError:
                warnings.append(
                    f"Ignored one invalid {collection.value} record "
                    f"({document.document_id})."
                )
        return tuple(valid)

    @staticmethod
    def _for_project(records, project_id: str):
        return tuple(
            record for record in records if getattr(record, "project_id", None) == project_id
        )

    @staticmethod
    def _recent(records, field_name: str):
        return tuple(
            sorted(
                records,
                key=lambda item: getattr(item, field_name),
                reverse=True,
            )[:MAX_DASHBOARD_RECORDS]
        )

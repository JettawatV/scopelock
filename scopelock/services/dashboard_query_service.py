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


class DashboardSnapshot(StrictFrozenContractModel):
    generated_at: datetime
    projects: tuple[ProjectRecord, ...]
    artifacts: tuple[CommercialArtifact, ...]
    scope_events: tuple[ScopeEventRecord, ...]
    scope_buffers: tuple[ScopeBufferRecord, ...]
    agent_runs: tuple[DashboardAgentRun, ...]
    readiness: AgentReadinessSnapshot
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
        return DashboardSnapshot(
            generated_at=self._clock(),
            projects=self._recent(projects, "updated_at"),
            artifacts=self._recent(artifacts, "created_at"),
            scope_events=self._recent(events, "created_at"),
            scope_buffers=self._recent(buffers, "updated_at"),
            agent_runs=self._recent(agent_runs, "started_at"),
            readiness=self._readiness(),
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

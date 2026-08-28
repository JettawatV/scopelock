"""Build the reviewed Day 9 follow-up events without persistence side effects."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from collections.abc import Mapping

from scopelock.domain.enums import ScopeEventClassification, ScopeEventStatus
from scopelock.domain.models import EvidenceRef, ModuleQuantity, ScopeVersion
from scopelock.domain.workflow_models import ProjectRecord, ScopeEventRecord
from scopelock.services.identity import stable_id


FollowupPayload = Mapping[str, Mapping[str, str]]


@dataclass(frozen=True)
class GoldenPathEvents:
    clarification: ScopeEventRecord
    expansion: ScopeEventRecord
    closure: ScopeEventRecord


class GoldenPathScenarioBuilder:
    """Translate the reviewed local fixture into typed semantic event records."""

    @classmethod
    def build(
        cls,
        *,
        project: ProjectRecord,
        baseline: ScopeVersion,
        followups: FollowupPayload,
        started_at: datetime,
    ) -> GoldenPathEvents:
        return GoldenPathEvents(
            clarification=cls._event(
                project=project,
                baseline=baseline,
                data=followups["clarification"],
                classification=ScopeEventClassification.NO_CHANGE,
                created_at=started_at + timedelta(minutes=1),
                extra_evidence=(
                    EvidenceRef(
                        source_type="scope_version",
                        source_id=baseline.id,
                        quote_or_rule=(
                            "Operations dashboard naming is presentation-only."
                        ),
                    ),
                ),
            ),
            expansion=cls._event(
                project=project,
                baseline=baseline,
                data=followups["expansion"],
                classification=ScopeEventClassification.EXPANSION,
                created_at=started_at + timedelta(minutes=2),
                additions=(
                    ModuleQuantity(module_key="line_notifications", quantity=1),
                    ModuleQuantity(module_key="line_approval", quantity=1),
                ),
                extra_evidence=(
                    EvidenceRef(
                        source_type="scope_version",
                        source_id=baseline.id,
                        quote_or_rule=(
                            "Accepted integrations include Gmail and email only."
                        ),
                    ),
                    EvidenceRef(
                        source_type="sop",
                        source_id="line_notifications",
                        quote_or_rule=(
                            "LINE notifications are a separate material module."
                        ),
                    ),
                    EvidenceRef(
                        source_type="sop",
                        source_id="line_approval",
                        quote_or_rule="LINE approval is a separate material module.",
                    ),
                ),
            ),
            closure=cls._event(
                project=project,
                baseline=baseline,
                data=followups["closure"],
                classification=ScopeEventClassification.CLOSURE,
                created_at=started_at + timedelta(minutes=3),
            ),
        )

    @staticmethod
    def _event(
        *,
        project: ProjectRecord,
        baseline: ScopeVersion,
        data: Mapping[str, str],
        classification: ScopeEventClassification,
        created_at: datetime,
        additions: tuple[ModuleQuantity, ...] = (),
        extra_evidence: tuple[EvidenceRef, ...] = (),
    ) -> ScopeEventRecord:
        message_id = data["message_id"]
        message_text = data["text"]
        return ScopeEventRecord(
            id=stable_id("event", message_id),
            project_id=project.id,
            gmail_message_id=message_id,
            baseline_scope_version_id=baseline.id,
            classification=classification,
            status=ScopeEventStatus.CLASSIFIED,
            description=message_text,
            additions=additions,
            evidence=(
                EvidenceRef(
                    source_type="gmail",
                    source_id=message_id,
                    quote_or_rule=message_text,
                ),
                EvidenceRef(
                    source_type="scope_version",
                    source_id=baseline.id,
                    quote_or_rule="Accepted scope used as the comparison baseline.",
                ),
                *extra_evidence,
            ),
            correlation_id=stable_id("corr", message_id),
            created_at=created_at,
        )
